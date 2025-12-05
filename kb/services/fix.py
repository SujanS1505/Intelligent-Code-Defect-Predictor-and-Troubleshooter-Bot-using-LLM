import json, re, difflib
import google.generativeai as genai
from google.api_core.exceptions import NotFound, FailedPrecondition

# NOTE: Replace the placeholder with your *actual* Gemini API key.
GEMINI_API_KEY = "AIzaSyA2hxNsJqertLt-tdtV4vTOmckxbD9ZhDs"    # <-- your Gemini key

# FIX 1: Use standard, stable, and current model identifiers.
PREFERRED_MODELS = [
    "gemini-2.5-flash",  # Current, fast model
    "gemini-2.5-pro",    # Current, high-quality model
    "gemini-1.5-flash",  # Fallback
    "gemini-1.5-pro",    # Fallback
]

genai.configure(api_key=GEMINI_API_KEY)

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

def _pick_model():
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

_MODEL_ID = _pick_model()

def analyze_and_fix(code: str, lang: str = "python") -> dict:
    # Capture the full prompt to return as 'query'
    prompt = PROMPT_TMPL.format(lang=lang, code=code)

    # Try the chosen model; if it 404s, cascade through the list
    tried = []
    data = None
    for mid in ([_MODEL_ID] + [m for m in PREFERRED_MODELS if m != _MODEL_ID]):
        tried.append(mid)
        try:
            model = genai.GenerativeModel(mid)
            resp = model.generate_content(prompt)
            raw = (resp.text or "").strip()
            if not raw:
                raise RuntimeError("Empty response from Gemini.")
            data = _extract_json(raw)
            if data:
                break
        except (NotFound, FailedPrecondition):
            continue
        except RuntimeError:
            continue
    
    # If all models failed or parsing failed
    if data is None:
        return {
            "_llm_status": f"Failed (Tried: {', '.join(tried)})",
            "root_cause": "Analyzer failed to get a response or parse JSON from the LLM.",
            "issue_type": "Analyzer Error",
            "confidence": 0.0,
            "patched_code": code,
            "unified_diff": "",
            "query": prompt,
            "suspect_span": "N/A",
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
        "_llm_status": f"Success ({tried[-1]})",
        "query": prompt,                       
        "suspect_span": suspect_span,         
        "model_used": tried[-1],
    }