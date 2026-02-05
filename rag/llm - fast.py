# rag/llm.py
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from config import CODER_LLM_DIR

# ----------------------------
# Loader with safe fallbacks
# ----------------------------
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_tok = AutoTokenizer.from_pretrained(
    CODER_LLM_DIR,
    use_fast=True,
    clean_up_tokenization_spaces=False,
)


def _load_llm():
    """
    Try (1) GPU fp16, (2) CPU fp32 without accelerate device_map.
    If model still can't load, return None (we'll use a mock generator).
    """
    try:
        if _DEVICE == "cuda":
            return AutoModelForCausalLM.from_pretrained(
                CODER_LLM_DIR,
                torch_dtype=torch.float16,
                device_map={"": 0},          # single GPU, no sharding/offload
            )
        else:
            # CPU: avoid accelerate auto-dispatch which causes disk offload error
            return AutoModelForCausalLM.from_pretrained(
                CODER_LLM_DIR,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
            ).to("cpu")
    except Exception as e:
        print("[llm] Could not load LLM, using mock generator. Reason:", e)
        return None


_lm = _load_llm()

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
Retrieved passages:
{passages}

Return JSON only.
[/USER]
"""

def _passages_block(passages):
    blocks = []
    for i, p in enumerate(passages, 1):
        blocks.append(
            f"{i}) id={p.get('id','')} source={p.get('source','kb')} title={p.get('title','')}\n\n{p.get('text','')}\n"
        )
    return "\n".join(blocks)


def _mock_generate(issue, code):
    suggestion = "Review the suspect lines and add necessary validation."
    patch = ""
    if "Index" in issue or "Bounds" in issue:
        suggestion = "Fix off-by-one / bounds issue. Ensure index < len(array)."
        patch = "--- a/file\n+++ b/file\n@@\n- print(nums[3])\n+ print(nums[2])\n"
    elif "ZeroDivision" in issue:
        suggestion = "Guard against division by zero."
        patch = "--- a/file\n+++ b/file\n@@\n- return a / b\n+ return a / b if b != 0 else None\n"
    elif "Null" in issue or "NoneType" in issue:
        suggestion = "Check for null/None before attribute access."
    return {
        "root_cause": issue or "Possible_Bug",
        "fix_explanation": suggestion,
        "patch_unified_diff": patch,
        "references": ["local_kb: heuristic-fallback"],
        "confidence": 0.35
    }


def generate_fix(lang, path, issue, span, code, passages):
    if _lm is None:
        return _mock_generate(issue, code)

    prompt = PROMPT.format(
        system=SYSTEM,
        lang=lang,
        path=path,
        issue=issue,
        span=span,
        code=code,
        passages=_passages_block(passages)
    )

    inputs = _tok(prompt, return_tensors="pt")
    if _DEVICE == "cuda":
        inputs = {k: v.to(_lm.device) for k, v in inputs.items()}

    outputs = _lm.generate(
        **inputs,
        max_new_tokens=128,
        do_sample=False,
        pad_token_id=_tok.eos_token_id
    )
    # Avoid FutureWarning about clean_up_tokenization_spaces default change.
    text = _tok.decode(outputs[0], skip_special_tokens=True, clean_up_tokenization_spaces=False)

    s, e = text.rfind("{"), text.rfind("}")
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return _mock_generate(issue, code)
