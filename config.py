import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---- MODELS (local only) ----
DEFECT_PREDICTOR_DIR = os.path.join(BASE_DIR, "models", "defect_predictor", "codet5p-220m")
# If you fine-tuned, point to span model dir instead:
# DEFECT_PREDICTOR_DIR = os.path.join(BASE_DIR, "models", "defect_predictor", "span")

EMB_MODEL_DIR = os.path.join(BASE_DIR, "models", "defect_predictor", "emb-codebert-base")
CODER_LLM_DIR = os.path.join(BASE_DIR, "models", "coder_llm", "Qwen2.5-Coder-1.5B-Instruct")

# ---- KB / FAISS ----
KB_JSONL = os.path.join(BASE_DIR, "kb", "clean_passages.jsonl")
FAISS_INDEX = os.path.join(BASE_DIR, "index", "faiss", "kb.faiss")
FAISS_IDS = os.path.join(BASE_DIR, "index", "faiss", "kb.ids")

# ---- App ----
SECRET_KEY = "change-me"
MAX_CODE_LEN = 20000  # characters
