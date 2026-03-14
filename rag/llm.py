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
import difflib
import re
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from config import CODER_LLM_DIR

_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Optional escape hatch for low-resource machines.
# Set DISABLE_LOCAL_LLM=1 to force mock responses.
_DISABLE_LOCAL_LLM = (os.environ.get("DISABLE_LOCAL_LLM") or "").strip().lower() in {"1", "true", "yes"}
_FAST_ANALYSIS_MODE = (os.environ.get("FAST_ANALYSIS_MODE") or "1").strip().lower() in {"1", "true", "yes"}

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

    # Fast mode keeps the app responsive on CPU-only machines.
    if _FAST_ANALYSIS_MODE and _DEVICE != "cuda":
        _lm = None
        _tok = None
        _load_error = "FAST_ANALYSIS_MODE active on CPU"
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


def _simple_optimize_python(code: str) -> str:
    out = code
    # Replace tabs for consistent formatting in rendered output.
    out = out.replace("\t", "    ")
    # Trim trailing spaces line by line.
    out = "\n".join(line.rstrip() for line in out.splitlines())
    if code.endswith("\n"):
        out += "\n"
    return out


def _patch_division_guard(text: str) -> tuple[str, bool]:
    updated = re.sub(
        r"return\s+([^\n#/]+?)\s*/\s*([A-Za-z_]\w*)\s*$",
        r"return \1 / \2 if \2 != 0 else 0",
        text,
        flags=re.MULTILINE,
    )
    return updated, updated != text


def _adjust_index_in_line(line: str) -> tuple[str, bool]:
    m = re.search(r"\[( *)(\d+)( *)\]", line)
    if not m:
        return line, False
    old_idx = int(m.group(2))
    safe_idx = max(0, old_idx - 1)
    if old_idx == safe_idx:
        return line, False
    old_bracket = f"[{m.group(1)}{old_idx}{m.group(3)}]"
    new_bracket = f"[{safe_idx}]"
    return line.replace(old_bracket, new_bracket, 1) + "  # fixed off-by-one", True


def _patch_direct_indexing(text: str) -> tuple[str, bool]:
    lines = text.splitlines()
    changed = False
    for i, line in enumerate(lines):
        if "[" in line and "]" in line:
            new_line, line_changed = _adjust_index_in_line(line)
            if line_changed:
                lines[i] = new_line
                changed = True
    return "\n".join(lines) if changed else text, changed


def _patch_bounds_loops(text: str) -> tuple[str, bool]:
    if "<=" in text and ("for" in text or "while" in text):
        updated = text.replace("<=", "<")
        return updated, updated != text
    
    if "[" in text and "]" in text:
        updated, changed = _patch_direct_indexing(text)
        if changed:
            return updated, True
    
    return text, False


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _find_body_end(lines: list[str], body_start: int, base_indent: int) -> int:
    j = body_start
    while j < len(lines):
        stripped = lines[j].strip()
        if stripped and _line_indent(lines[j]) <= base_indent:
            break
        j += 1
    return j


def _has_counter_increment(lines: list[str], body_start: int, body_end: int, var: str) -> bool:
    pattern = rf"^\s*{re.escape(var)}\s*(\+=|=)\s*"
    for k in range(body_start, body_end):
        if re.search(pattern, lines[k]):
            return True
    return False


def _infer_body_indent(lines: list[str], body_start: int, body_end: int, base_indent: int) -> int:
    for k in range(body_start, body_end):
        if lines[k].strip():
            return _line_indent(lines[k])
    return base_indent + 4


def _patch_missing_loop_increment(text: str) -> tuple[str, bool]:
    lines = text.splitlines()
    changed = False
    i = 0

    while i < len(lines):
        m = re.match(r"^(\s*)while\s+([A-Za-z_]\w*)\s*<\s*len\([^\)]*\)\s*:\s*$", lines[i])
        if not m:
            i += 1
            continue

        base_indent = len(m.group(1))
        var = m.group(2)
        body_start = i + 1
        body_end = _find_body_end(lines, body_start, base_indent)

        if body_start >= body_end or _has_counter_increment(lines, body_start, body_end, var):
            i = body_end
            continue

        body_indent = _infer_body_indent(lines, body_start, body_end, base_indent)
        insert_line = f"{' ' * body_indent}{var} += 1  # auto-fix: avoid infinite loop"
        lines.insert(body_end, insert_line)
        changed = True
        i = body_end + 1

    return "\n".join(lines), changed


def _detect_action(issue: str) -> tuple[str, str]:
    text = issue or ""
    if "ZeroDivision" in text:
        return "division", "Added a division-by-zero guard in return expressions."
    if "Index" in text or "Bounds" in text:
        return "bounds", "Adjusted loop bounds to avoid out-of-range indexing."
    if "None" in text or "Null" in text:
        return "null", "Potential null/None dereference detected. Add guards before attribute or method access."
    return "auto", "Applied safe fallback optimization and retained original logic."


def _try_division_patch(action: str, patched: str, explanation: str) -> tuple[str, str, bool]:
    if action not in {"division", "auto"}:
        return patched, explanation, False
    updated, changed = _patch_division_guard(patched)
    if not changed:
        return patched, explanation, False
    if action == "auto":
        explanation = "Detected unsafe division and added a zero-check guard."
    return updated, explanation, True


def _try_bounds_patch(action: str, patched: str, explanation: str) -> tuple[str, str, bool]:
    if action not in {"bounds", "auto"}:
        return patched, explanation, False
    updated, changed = _patch_bounds_loops(patched)
    if not changed:
        return patched, explanation, False
    
    if action == "bounds":
        explanation = "Applied safe bounds checking for array access and loop conditions."
    else:
        explanation = "Detected potential array bounds issue and applied defensive fix."
    return updated, explanation, True


def _try_iteration_patch(action: str, patched: str, explanation: str) -> tuple[str, str, bool]:
    if action not in {"bounds", "auto"}:
        return patched, explanation, False
    updated, changed = _patch_missing_loop_increment(patched)
    if not changed:
        return patched, explanation, False
    if action == "auto":
        explanation = "Detected missing loop counter update and added an increment step."
    else:
        explanation = "Added missing loop counter increment to prevent infinite loops."
    return updated, explanation, True


def _apply_heuristic_fix(issue: str, code: str) -> tuple[str, str]:
    action, explanation = _detect_action(issue)
    patched = code

    patched, explanation, changed = _try_division_patch(action, patched, explanation)
    if changed:
        return _simple_optimize_python(patched), explanation

    patched, explanation, changed = _try_bounds_patch(action, patched, explanation)
    if changed:
        return _simple_optimize_python(patched), explanation

    patched, explanation, changed = _try_iteration_patch(action, patched, explanation)
    if changed:
        return _simple_optimize_python(patched), explanation

    patched = _simple_optimize_python(patched)
    if patched != code:
        return patched, "Applied safe code cleanup for readability and execution stability."
    
    if "Index" in (issue or "") or "Bounds" in (issue or "") or "ZeroDivision" in (issue or ""):
        return patched, "Potential defect detected. Ensure bounds checks are in place before array access and arithmetic operations."
    
    return patched, explanation


def _mock_generate(issue: str, code: str) -> dict:
    patched_code, explanation = _apply_heuristic_fix(issue, code)
    diff_lines = difflib.unified_diff(
        code.splitlines(),
        patched_code.splitlines(),
        fromfile="a/snippet",
        tofile="b/snippet",
        lineterm="",
    )
    patch = "\n".join(diff_lines)

    return {
        "root_cause": issue or "Possible_Bug",
        "fix_explanation": explanation,
        "explanation": explanation,
        "patched_code": patched_code,
        "patch_unified_diff": patch,
        "unified_diff": patch,
        "references": ["local_kb: heuristic-fallback"],
        "confidence": 0.8,
        "_llm_status": f"Fast heuristic fixer ({_load_error or 'no local LLM'})",
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
