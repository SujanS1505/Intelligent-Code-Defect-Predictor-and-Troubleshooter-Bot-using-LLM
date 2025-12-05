# rag/predictor.py
import os
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification

from config import DEFECT_PREDICTOR_DIR

_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_model = None
_tok = None

def _load_or_none():
    global _model, _tok
    try:
        # For CodeT5p, sentencepiece slow tokenizer avoids Windows issues
        use_fast = False
        _tok = AutoTokenizer.from_pretrained(DEFECT_PREDICTOR_DIR, use_fast=use_fast)
        if _tok.pad_token is None:
            _tok.pad_token = _tok.eos_token
        _model = AutoModelForTokenClassification.from_pretrained(DEFECT_PREDICTOR_DIR)
        if getattr(_model.config, "pad_token_id", None) is None:
            _model.config.pad_token_id = _tok.pad_token_id
        _model.to(_DEVICE).eval()
    except Exception as e:
        print("[predictor] fallback mode:", e)
        _model = None
        _tok = None

_load_or_none()

# ---------- public API ----------
def predict_defect(code: str, lang: str = "python"):
    """
    Returns: dict(issue_type, span_lines, confidence)
    """

# If trained span model exists:
    if _model and _tok:
        # ----------------------------------------------------------------------
        # TEMPORARY FIX: COMMENT OUT THIS ENTIRE AI PREDICTION BLOCK (start)
        # The AI model is loaded but UNTRAINED, giving junk results.
        # We must skip it to use the reliable heuristic below.
        # enc = _tok(code, truncation=True, max_length=1024, return_tensors="pt")
        # with torch.no_grad():
        #     out = _model(**{k: v.to(_DEVICE) for k, v in enc.items()}).logits[0]
        # # simple: if any non-zero tag predicted → bug exists
        # labels = out.argmax(-1).cpu().tolist()
        # has_bug = any(x != 0 for x in labels)
        # # crude mapping to lines:
        # span_lines = "?"
        # if has_bug:
        #     span_lines = "suspected"  # you can add token→line mapping later
        # return {
        #     "issue_type": "Suspected_Defect" if has_bug else "No_Defect",
        #     "span_lines": span_lines,
        #     "confidence": 0.65 if has_bug else 0.3,
        # }
        # TEMPORARY FIX: COMMENT OUT THIS ENTIRE AI PREDICTION BLOCK (end)
        pass # Explicitly fall through to the heuristic.

    # --------- heuristic fallback (works now, replace later) ----------
    issue = "Possible_Bug"
    conf = 0.5
    lines = code.splitlines()
    # common Python runtime mistakes
    for i, L in enumerate(lines, 1):
        if "IndexError" in L or "]" in L and "[" in L and ".append(" not in L and ".extend(" not in L:
            issue = "IndexError_or_Bounds"
            conf = 0.8
            return {"issue_type": issue, "span_lines": f"{i}-{i}", "confidence": conf}
        if ".strip(" in L and "None" in code:
            issue = "NoneType_Attribute"
            conf = 0.7
            return {"issue_type": issue, "span_lines": f"{i}-{i}", "confidence": conf}
    return {"issue_type": issue, "span_lines": "?", "confidence": conf}
