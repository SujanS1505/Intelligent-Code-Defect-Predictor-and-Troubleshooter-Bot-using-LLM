import os, json, torch
import numpy as np
import faiss
from transformers import AutoTokenizer, AutoModel
from config import EMB_MODEL_DIR, KB_JSONL, FAISS_INDEX, FAISS_IDS

os.makedirs(os.path.dirname(FAISS_INDEX), exist_ok=True)

# Load embedder model (CodeBERT etc.)
tok = AutoTokenizer.from_pretrained(EMB_MODEL_DIR, use_fast=True)
enc = AutoModel.from_pretrained(EMB_MODEL_DIR).eval()

# Load KB
rows = [json.loads(l) for l in open(KB_JSONL, "r", encoding="utf-8")]
texts = [r["text"] for r in rows]
ids   = [r["id"] for r in rows]

# Create embeddings
with torch.no_grad():
    t = tok(texts, padding=True, truncation=True, max_length=256, return_tensors="pt")
    v = enc(**t).last_hidden_state.mean(1)
    v = torch.nn.functional.normalize(v, p=2, dim=1)
    embs = v.cpu().numpy().astype("float32")

# Build FAISS index
index = faiss.IndexFlatIP(embs.shape[1])
index.add(embs)
faiss.write_index(index, FAISS_INDEX)

# Save IDs
with open(FAISS_IDS, "w", encoding="utf-8") as f:
    f.write("\n".join(ids))

print(f"✅ FAISS index created with {len(ids)} entries")
print(f"Saved to: {FAISS_INDEX}")
