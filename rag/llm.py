"""Local LLM interface used by the RAG pipeline.

Goals:
- Never load the model more than once per process.
- Avoid loading at import time (keeps Flask startup fast and prevents debug
  reloader loops from repeatedly loading huge weights).
- Use torch inference mode and CPU-safe defaults.

Public API:
- generate_fix(lang, path, issue, span, code, passages) -> dict
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from config import CODER_LLM_DIR

_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Optional escape hatch for low-resource machines.
# Set DISABLE_LOCAL_LLM=1 to force mock responses.
_DISABLE_LOCAL_LLM = (os.environ.get("DISABLE_LOCAL_LLM") or "").strip().lower() in {"1", "true", "yes"}

_lm = None
_tok = None
_load_error: str | None = None
_load_lock = threading.Lock()

SYSTEM = (
    "You are a strict code troubleshooter. Use ONLY the provided code and retrieved passages. "
    "Respond in valid JSON with keys: root_cause, fix_explanation, patch_unified_diff, references, confidence."
)

PROMPT = """[SYSTEM]
{system}
[/SYSTEM]
[USER]
Language: {lang}
File: {path}
Detected issue: {issue}
Span: {span}
Code:
```{lang}
{code}
```
Retrieved passages:
{passages}

Return JSON only.
[/USER]
"""


def _passages_block(passages: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for i, p in enumerate(passages or [], 1):
        blocks.append(
            f"{i}) id={p.get('id','')} source={p.get('source','kb')} title={p.get('title','')}\n\n{p.get('text','')}\n"
        )
    return "\n".join(blocks)


def _ensure_loaded() -> None:
    """Loads tokenizer/model exactly once per process."""
    global _lm, _tok, _load_error

    if _DISABLE_LOCAL_LLM:
        _lm = None
        _tok = None
        _load_error = "DISABLE_LOCAL_LLM set"
        return

    if _lm is not None and _tok is not None:
        return

    with _load_lock:
        if _lm is not None and _tok is not None:
            return

        try:
            tok = AutoTokenizer.from_pretrained(
                CODER_LLM_DIR,
                use_fast=True,
                clean_up_tokenization_spaces=False,
            )

            if _DEVICE == "cuda":
                lm = AutoModelForCausalLM.from_pretrained(
                    CODER_LLM_DIR,
                    torch_dtype=torch.float16,
                    device_map={"": 0},
                )
            else:
                lm = AutoModelForCausalLM.from_pretrained(
                    CODER_LLM_DIR,
                    torch_dtype=torch.float32,
                    low_cpu_mem_usage=True,
                ).to("cpu")

            lm.eval()
            _tok = tok
            _lm = lm
            _load_error = None
            print(f"[llm] Loaded local LLM on {_DEVICE} from {CODER_LLM_DIR}")
        except Exception as e:
            _lm = None
            _tok = None
            _load_error = f"{type(e).__name__}: {e}"
            print("[llm] Could not load LLM, using mock generator. Reason:", _load_error)


def _mock_generate(issue: str, code: str) -> dict:
    suggestion = (
        "Fallback: local LLM unavailable. Review suspect lines and apply the most relevant KB passage guidance."
    )
    patch = ""

    if "Index" in (issue or "") or "Bounds" in (issue or ""):
        suggestion = "Fix off-by-one / bounds issue. Ensure index < len(array) and loop uses '<' not '<='." 
        patch = "--- a/file\n+++ b/file\n@@\n- # BUG: out of bounds\n+ # FIX: stay within bounds\n"
    elif "ZeroDivision" in (issue or ""):
        suggestion = "Guard against division by zero." 
        patch = "--- a/file\n+++ b/file\n@@\n- return a / b\n+ return a / b if b != 0 else 0\n"
    elif "Null" in (issue or "") or "None" in (issue or ""):
        suggestion = "Check for null/None before dereferencing." 

    return {
        "root_cause": issue or "Possible_Bug",
        "fix_explanation": suggestion,
        "patch_unified_diff": patch,
        "references": ["local_kb: heuristic-fallback"],
        "confidence": 0.35,
        "_llm_status": f"Mock LLM (Fallback: {_load_error or 'unknown'})",
    }


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass

    s, e = text.rfind("{"), text.rfind("}")
    if 0 <= s < e:
        try:
            return json.loads(text[s : e + 1])
        except Exception:
            return {}
    return {}


def generate_fix(lang: str, path: str, issue: str, span: str, code: str, passages: list[dict[str, Any]]):
    _ensure_loaded()
    if _lm is None or _tok is None:
        return _mock_generate(issue, code)

    prompt = PROMPT.format(
        system=SYSTEM,
        lang=lang,
        path=path,
        issue=issue,
        span=span,
        code=code,
        passages=_passages_block(passages),
    )

    inputs = _tok(prompt, return_tensors="pt")
    if _DEVICE == "cuda":
        inputs = {k: v.to(_lm.device) for k, v in inputs.items()}

    with torch.inference_mode():
        outputs = _lm.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=False,
            temperature=1.0,
            top_p=1.0,
            top_k=0,
            pad_token_id=_tok.eos_token_id,
        )

    text = _tok.decode(outputs[0], skip_special_tokens=True, clean_up_tokenization_spaces=False)
    data = _extract_json(text)
    if data:
        data.setdefault("_llm_status", "Local LLM")
        return data

    return _mock_generate(issue, code)
