# rag/retriever.py
import os, json, numpy as np, torch
from transformers import AutoTokenizer, AutoModel
from config import EMB_MODEL_DIR, FAISS_INDEX, FAISS_IDS, KB_JSONL

# Try FAISS; keep working if it's missing
_FAISS_OK = False
try:
    import faiss  # type: ignore
    _FAISS_OK = True
except Exception as e:
    print("[retriever] FAISS unavailable, will use NumPy cosine:", e)

_tok = AutoTokenizer.from_pretrained(
    EMB_MODEL_DIR,
    use_fast=True,
    clean_up_tokenization_spaces=False,
)
_enc = AutoModel.from_pretrained(EMB_MODEL_DIR).eval()

def _embed(texts, max_len=256):
    if isinstance(texts, str):
        texts = [texts]
    with torch.no_grad():
        t = _tok(texts, padding=True, truncation=True, max_length=max_len, return_tensors="pt")
        v = _enc(**t).last_hidden_state.mean(1)
        v = torch.nn.functional.normalize(v, p=2, dim=1)
        return v.cpu().numpy().astype("float32")

def _load_kb_rows():
    rows = []
    with open(KB_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows

def _id_map(rows):
    return {r.get("id"): r for r in rows}

# ---------- FAISS retrieval ----------
def _retrieve_faiss(query_vec, topk):
    print("[retriever] Using FAISS index")
    idx = faiss.read_index(FAISS_INDEX)
    ids = open(FAISS_IDS, "r", encoding="utf-8").read().splitlines()
    D, I = idx.search(query_vec, topk)

    rows = _load_kb_rows()
    by_id = _id_map(rows)

    hits, out_ids = [], []
    for pos in I[0]:
        if pos < 0 or pos >= len(ids):
            continue
        hit_id = ids[pos]

        # 1) exact id match
        if hit_id in by_id:
            hits.append(by_id[hit_id]); out_ids.append(hit_id); continue

        # 2) fallback: treat id like a numeric row index
        try:
            idx_int = int(hit_id)
            if 0 <= idx_int < len(rows):
                row = rows[idx_int]
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
    _KB_ROWS = _load_kb_rows()
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
