# rag/retriever.py
import os, json, numpy as np, torch
import threading
from transformers import AutoTokenizer, AutoModel
from config import EMB_MODEL_DIR, FAISS_INDEX, FAISS_IDS, KB_JSONL

# Try FAISS; keep working if it's missing
_FAISS_OK = False
try:
    import faiss  # type: ignore
    _FAISS_OK = True
except Exception as e:
    print("[retriever] FAISS unavailable, will use NumPy cosine:", e)

_tok = None
_enc = None
_embed_lock = threading.Lock()

_faiss_index = None
_faiss_ids: list[str] | None = None
_faiss_lock = threading.Lock()

_kb_rows = None
_kb_by_id = None
_kb_lock = threading.Lock()


def _ensure_embedder():
    global _tok, _enc
    if _tok is not None and _enc is not None:
        return
    with _embed_lock:
        if _tok is not None and _enc is not None:
            return
        _tok = AutoTokenizer.from_pretrained(
            EMB_MODEL_DIR,
            use_fast=True,
            clean_up_tokenization_spaces=False,
        )
        _enc = AutoModel.from_pretrained(EMB_MODEL_DIR).eval()


def _ensure_kb_loaded():
    global _kb_rows, _kb_by_id
    if _kb_rows is not None and _kb_by_id is not None:
        return
    with _kb_lock:
        if _kb_rows is not None and _kb_by_id is not None:
            return
        rows = []
        with open(KB_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                rows.append(json.loads(line))
        _kb_rows = rows
        _kb_by_id = {r.get("id"): r for r in rows}


def _ensure_faiss_loaded():
    global _faiss_index, _faiss_ids
    if not _FAISS_OK:
        return
    if _faiss_index is not None and _faiss_ids is not None:
        return
    with _faiss_lock:
        if _faiss_index is not None and _faiss_ids is not None:
            return
        _faiss_index = faiss.read_index(FAISS_INDEX)
        _faiss_ids = open(FAISS_IDS, "r", encoding="utf-8").read().splitlines()

def _embed(texts, max_len=256):
    if isinstance(texts, str):
        texts = [texts]
    _ensure_embedder()
    with torch.inference_mode():
        t = _tok(texts, padding=True, truncation=True, max_length=max_len, return_tensors="pt")
        v = _enc(**t).last_hidden_state.mean(1)
        v = torch.nn.functional.normalize(v, p=2, dim=1)
        return v.cpu().numpy().astype("float32")

# ---------- FAISS retrieval ----------
def _retrieve_faiss(query_vec, topk):
    print("[retriever] Using FAISS index")
    _ensure_faiss_loaded()
    _ensure_kb_loaded()
    D, I = _faiss_index.search(query_vec, topk)

    hits, out_ids = [], []
    for pos in I[0]:
        if pos < 0 or _faiss_ids is None or pos >= len(_faiss_ids):
            continue
        hit_id = _faiss_ids[pos]

        # 1) exact id match
        if _kb_by_id is not None and hit_id in _kb_by_id:
            hits.append(_kb_by_id[hit_id]); out_ids.append(hit_id); continue

        # 2) fallback: treat id like a numeric row index
        try:
            idx_int = int(hit_id)
            if _kb_rows is not None and 0 <= idx_int < len(_kb_rows):
                row = _kb_rows[idx_int]
                hits.append(row); out_ids.append(row.get("id", str(idx_int))); continue
        except ValueError:
            pass

        # 3) skip if unmappable
        print(f"[retriever] Warning: FAISS id '{hit_id}' not found in KB; skipping.")
    return hits, out_ids

# ---------- NumPy cosine fallback ----------
_KB_ROWS = None
_KB_EMB  = None

def _ensure_kb_embedded():
    global _KB_ROWS, _KB_EMB
    if _KB_EMB is not None: return
    _ensure_kb_loaded()
    _KB_ROWS = _kb_rows
    texts = [r.get("text","") for r in _KB_ROWS]
    _KB_EMB = _embed(texts)
    print(f"[retriever] Fallback in-memory index built: {len(_KB_ROWS)} passages")

def _retrieve_numpy_cosine(query_vec, topk):
    print("[retriever] Using NumPy cosine fallback")
    _ensure_kb_embedded()
    q = query_vec[0]
    sims = _KB_EMB @ q  # cosine (embeddings are normalized)
    k = min(topk, len(sims))
    top_idx = np.argpartition(-sims, k-1)[:k]
    top_idx = top_idx[np.argsort(-sims[top_idx])]
    hits = [_KB_ROWS[i] for i in top_idx]
    ids  = [h.get("id", str(i)) for i, h in zip(top_idx, hits)]
    return hits, ids

# ---------- Public API ----------
def retrieve(query: str, topk: int = 5):
    qv = _embed(query)
    if _FAISS_OK and os.path.exists(FAISS_INDEX) and os.path.exists(FAISS_IDS):
        try:
            return _retrieve_faiss(qv, topk)
        except Exception as e:
            print("[retriever] FAISS failed, falling back to NumPy:", e)
    return _retrieve_numpy_cosine(qv, topk)
