# rag/orchestrator.py
import os

from rag.predictor import predict_defect
from rag.retriever import retrieve
from rag.llm import generate_fix


_FAST_ANALYSIS_MODE = (os.environ.get("FAST_ANALYSIS_MODE") or "1").strip().lower() in {"1", "true", "yes"}

def build_query(code: str, issue_type: str, lang="python"):
    # simple query; you can enhance with AST tokens, filenames, etc.
    return f"{lang} {issue_type} {code[:200]}"

def analyze(code: str, path: str = "snippet.py", lang: str = "python"):
    det = predict_defect(code, lang=lang)
    query = build_query(code, det["issue_type"], lang=lang)
    if _FAST_ANALYSIS_MODE:
        passages, ids = [], []
    else:
        passages, ids = retrieve(query, topk=5)
    result = generate_fix(lang, path, det["issue_type"], det["span_lines"], code, passages)
    result["_detector"] = det
    result["_retrieval_ids"] = ids
    return result, passages, det, query
