import json, re, difflib, os

# Use standard, stable, and current model identifiers.
PREFERRED_MODELS = [
    "gemini-2.5-flash",  # Current, fast model
    "gemini-2.5-pro",    # Current, high-quality model
    "gemini-1.5-flash",  # Fallback
    "gemini-1.5-pro",    # Fallback
]

# FIX 2: Added 'suspect_span' to the required JSON keys for the frontend
PROMPT_TMPL = """You are a senior software engineer. Find bugs and return FIXED code.

Return a strict JSON object with these keys:
- issue_type: string
- root_cause: string
- confidence: number between 0 and 1
- patched_code: string (the full corrected code)
- unified_diff: string (unified diff between original and patched; if you can't compute it, leave empty)
- explanation: string (optional extra notes)
- suspect_span: string (The line number or line range where the bug is, e.g., "Line 4" or "Lines 10-12")

Language: {lang}

Constraints:
- Keep original style; change only what is required to fix.
- If multiple issues exist, fix the most critical first.
- If nothing needs fixing, set patched_code equal to the input.

CODE:
{code}
"""

def _diff(a: str, b: str) -> str:
    return "".join(difflib.unified_diff(
        a.splitlines(keepends=True),
        b.splitlines(keepends=True),
        fromfile="original", tofile="patched"
    ))

def _extract_json(text: str) -> dict:
    try:
        # 1. Try to load the whole text as JSON (fastest method)
        return json.loads(text)
    except Exception:
        pass
    
    # FIX 3: Replaced the unsupported (?R) regex with a simple, standard one.
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}

def _try_import_gemini():
    """Import Gemini SDK lazily so app startup doesn't fail if deps are broken."""
    try:
        import google.generativeai as genai  # type: ignore
        from google.api_core.exceptions import NotFound, FailedPrecondition  # type: ignore
        return genai, NotFound, FailedPrecondition
    except Exception:
        return None, None, None


def _pick_model(genai):
    # Ask API which models are available to this key
    try:
        available = {m.name.split("/")[-1]: m for m in genai.list_models()}
    except Exception:
        available = {}

    # Return first preferred that exists & supports generateContent
    for mid in PREFERRED_MODELS:
        m = available.get(mid)
        if m and "generateContent" in getattr(m, "supported_generation_methods", []):
            return mid

    # If list_models failed or none matched, try preferred order anyway
    return PREFERRED_MODELS[0]


def _gemini_analyze(prompt: str):
    # Support both env var names people commonly use.
    # - GEMINI_API_KEY: project-specific
    # - GOOGLE_API_KEY: common default
    api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) to use the Google/Gemini API")

    genai, NotFound, FailedPrecondition = _try_import_gemini()
    if genai is None:
        raise ImportError("google.generativeai could not be imported (check protobuf/google packages)")

    genai.configure(api_key=api_key)

    model_id = _pick_model(genai)
    tried = []
    data = None
    for mid in ([model_id] + [m for m in PREFERRED_MODELS if m != model_id]):
        tried.append(mid)
        try:
            model = genai.GenerativeModel(mid)
            resp = model.generate_content(prompt)
            raw = (getattr(resp, "text", "") or "").strip()
            if not raw:
                raise RuntimeError("Empty response from Gemini.")
            data = _extract_json(raw)
            if data:
                break
        except Exception as e:
            if (NotFound is not None and isinstance(e, NotFound)) or (
                FailedPrecondition is not None and isinstance(e, FailedPrecondition)
            ):
                continue
            if isinstance(e, RuntimeError):
                continue
            continue

    return data, tried

def analyze_and_fix(code: str, lang: str = "python") -> dict:
    # Capture the full prompt to return as 'query'
    prompt = PROMPT_TMPL.format(lang=lang, code=code)

    # 1) Prefer Gemini if available; 2) fallback to local RAG stack.
    tried = []
    data = None
    gemini_error = None
    try:
        data, tried = _gemini_analyze(prompt)
    except Exception as e:
        gemini_error = e
        data = None
    
    # If Gemini didn't work, try local RAG pipeline (doesn't require Google SDK).
    if not data:
        try:
            from rag.orchestrator import analyze as rag_analyze

            rag_result, _passages, det, rag_query = rag_analyze(code, path="snippet", lang=lang)
            unified = rag_result.get("patch_unified_diff") or ""

            return {
                "issue_type": det.get("issue_type", "Unknown"),
                "root_cause": str(rag_result.get("root_cause", "No root cause generated.")),
                "explanation": str(rag_result.get("fix_explanation", rag_result.get("root_cause", ""))),
                "confidence": float(rag_result.get("confidence", 0.0) or 0.0),
                "patched_code": code,
                "unified_diff": unified,
                "query": rag_query,
                "suspect_span": str(det.get("span_lines", "N/A")),
                "_llm_status": rag_result.get("_llm_status", "Local RAG"),
                "model_used": "local-rag",
                "_fallback_reason": f"Gemini unavailable: {type(gemini_error).__name__}: {gemini_error}" if gemini_error else "Gemini unavailable",
            }
        except Exception as rag_e:
            return {
                "_llm_status": "Failed",
                "root_cause": "Analyzer failed to run Gemini and local fallback.",
                "issue_type": "Analyzer Error",
                "confidence": 0.0,
                "patched_code": code,
                "unified_diff": "",
                "query": prompt,
                "suspect_span": "N/A",
                "explanation": f"Gemini error: {type(gemini_error).__name__}: {gemini_error}; Local error: {type(rag_e).__name__}: {rag_e}",
            }

    # --- Extract required fields ---
    issue_type  = str(data.get("issue_type", "Unknown"))
    root_cause  = str(data.get("root_cause", "No root cause generated."))
    explanation = str(data.get("explanation", root_cause))
    suspect_span= str(data.get("suspect_span", "N/A")) 
    
    try:
        confidence = float(data.get("confidence", 0.0))
    except Exception:
        confidence = 0.0

    patched = data.get("patched_code") or code
    
    # FIX 4: Ensure unified diff is generated if a patch exists
    unified = data.get("unified_diff")
    if not unified and patched.strip() != code.strip():
        unified = _diff(code, patched)
    elif not unified:
        unified = "" 

    return {
        "issue_type": issue_type,
        "root_cause": root_cause,
        "explanation": explanation,
        "confidence": confidence,
        "patched_code": patched,
        "unified_diff": unified,
        
        # Keys required by result.html template
        "_llm_status": f"Success ({tried[-1]})" if tried else "Success",
        "query": prompt,                       
        "suspect_span": suspect_span,         
        "model_used": tried[-1] if tried else "gemini",
    }