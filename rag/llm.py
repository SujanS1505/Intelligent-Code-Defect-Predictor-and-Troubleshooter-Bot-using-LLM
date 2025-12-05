# rag/llm.py
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from config import CODER_LLM_DIR

# ----------------------------
# Loader with safe fallbacks
# ----------------------------
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Initialize global variables to None. They will be set by _load_llm().
_lm = None
_tok = None


def _load_llm():
    """
    Try (1) GPU fp16, (2) CPU fp32 without accelerate device_map.
    If model still can't load, the global _lm and _tok are set to None.
    """
    global _lm
    global _tok
    
    try:
        # 1. Load tokenizer first
        _tok = AutoTokenizer.from_pretrained(CODER_LLM_DIR, use_fast=True)
        
        # 2. Load model
        if _DEVICE == "cuda":
            _lm = AutoModelForCausalLM.from_pretrained(
                CODER_LLM_DIR,
                torch_dtype=torch.float16,
                device_map={"": 0},          # single GPU, no sharding/offload
            )
        else:
            # CPU: avoid accelerate auto-dispatch which causes disk offload error
            _lm = AutoModelForCausalLM.from_pretrained(
                CODER_LLM_DIR,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
            ).to("cpu")
            
    except Exception as e:
        print("[llm] Could not load LLM, using mock generator. Reason:", e)
        # Ensure both global variables are explicitly None on failure
        _lm = None
        _tok = None
        # No return value needed, as the function sets global state

# Call the loader function once globally to set _lm and _tok
_load_llm()

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


# rag/llm.py (The complete, exhaustive _mock_generate function)

import os # Required for Hardcoded_Credential mock (os.environ)

def _mock_generate(issue, code):
    # Default fallback patch/suggestion if no specific issue is matched
    suggestion = "Fallback: Code analysis suggests a defect not specifically mocked. Please consult the retrieved RAG passages for the most relevant fix guidance."
    patch = "--- a/file\n+++ b/file\n@@\n- # Fallback Buggy Code Line\n+ # Fallback Corrected Code Line\n"
    
    # --- 1. Runtime / Type Errors ---
    if "IndexError" in issue or "Bounds" in issue:
        suggestion = "Fix the off-by-one error by correcting the array index to be strictly within the bounds of the collection's length."
        patch = "--- a/file\n+++ b/file\n@@\n- print(nums[N])\n+ print(nums[N - 1]) # Correcting off-by-one\n"
        
    elif "ZeroDivision" in issue:
        suggestion = "Guard against division by zero to prevent a runtime exception. Implement a check for the divisor value."
        patch = "--- a/file\n+++ b/file\n@@\n- return a / b\n+ return a / b if b != 0 else 0\n"
        
    elif "Null" in issue or "NoneType" in issue:
        suggestion = "Check for null/None before attempting to access methods or attributes on the object to prevent a Null Pointer Exception."
        patch = "--- a/file\n+++ b/file\n@@\n- user.get_name()\n+ if user is not None: user.get_name()\n"

    elif "TypeError" in issue:
        suggestion = "A type mismatch is occurring. Ensure all operands in the expression are explicitly cast or converted to the expected type."
        patch = "--- a/file\n+++ b/file\n@@\n- total = sum + '50'\n+ total = sum + int('50')\n"

    elif "KeyError" in issue or "AttributeError" in issue:
        suggestion = "A dictionary key or object attribute is missing. Use dict.get() with a default value or check for existence before accessing."
        patch = "--- a/file\n+++ b/file\n@@\n- value = data['missing_key']\n+ value = data.get('missing_key', 'default')\n"

    # --- 2. Resource / Concurrency Errors ---
    elif "File_Leak" in issue or "Resource_Leak" in issue:
        suggestion = "The file or resource handle is not being closed. Use a context manager (e.g., Python's `with open`) to ensure guaranteed cleanup."
        patch = "--- a/file\n+++ b/file\n@@\n- f = open(path, 'r')\n- data = f.read()\n- # f.close() is missing\n+ with open(path, 'r') as f:\n+     data = f.read()\n"
        
    elif "Memory_Leak" in issue or "New_without_Delete" in issue:
        suggestion = "Dynamically allocated memory is not being deallocated. In C/C++, use RAII principles, such as `std::unique_ptr` or `std::shared_ptr`."
        patch = "--- a/file\n+++ b/file\n@@\n- int* data = new int[100];\n+ std::unique_ptr<int[]> data(new int[100]);\n"

    elif "Race_Condition" in issue or "Concurrency" in issue:
        suggestion = "Multiple threads are accessing a shared resource without synchronization. Introduce a lock (mutex) to protect the shared state."
        patch = "--- a/file\n+++ b/file\n@@\n- balance += amount\n+ with lock:\n+     balance += amount\n"

    elif "Deadlock" in issue:
        suggestion = "A deadlock is present due to inconsistent lock ordering. Enforce a global, consistent order for acquiring multiple locks."
        patch = "--- a/file\n+++ b/file\n@@\n- acquire(lock_b);\n- acquire(lock_a);\n+ acquire(lock_a);\n+ acquire(lock_b); // Enforce lock order\n"
        
    elif "Infinite_Loop" in issue:
        suggestion = "The loop condition is never met due to a missing or incorrect update to the control variable. Ensure the counter changes value."
        patch = "--- a/file\n+++ b/file\n@@\n- while i < 10:\n+ while i < 10:\n+     i += 1 # Added increment\n"

    # --- 3. Logic Errors ---
    elif "OffByOne" in issue or "Bad_Loop_Bound" in issue:
        suggestion = "The loop boundary is incorrect. Use `< length` instead of `<= length` to match 0-indexing and prevent out-of-bounds access."
        patch = "--- a/file\n+++ b/file\n@@\n- for (i=0; i <= length; i++)\n+ for (i=0; i < length; i++) // Corrected loop bound\n"

    elif "Floating_Point_Imprecision" in issue:
        suggestion = "Standard floating-point types (`float`, `double`) are unsuitable for financial calculations. Use a decimal-based library (e.g., Python's `Decimal` or Java's `BigDecimal`)."
        patch = "--- a/file\n+++ b/file\n@@\n- total = a + b\n+ total = Decimal(a) + Decimal(b)\n"
        
    elif "Missing_Break_in_Switch" in issue:
        suggestion = "A `break` statement is missing from a `case` block, causing control flow to unintentionally 'fall through' to the next case."
        patch = "--- a/file\n+++ b/file\n@@\n  case 1:\n-   do_action_1();\n+   do_action_1();\n+   break; // Added missing break\n  case 2:\n"
    
    # --- 4. Security Errors (OWASP) ---
    elif "SQL_Injection" in issue:
        suggestion = "Prevent SQL injection by using parameterized queries (Prepared Statements) to separate SQL command structure from user data."
        patch = "--- a/file\n+++ b/file\n@@\n- query = 'SELECT * FROM users WHERE id = ' + user_id\n+ query = 'SELECT * FROM users WHERE id = %s'\n+ cursor.execute(query, (user_id,))\n"

    elif "XSS" in issue or "Cross_Site_Scripting" in issue:
        suggestion = "User-controlled input is not being escaped before rendering to the client-side, enabling Cross-Site Scripting (XSS). Sanitize or escape the input."
        patch = "--- a/file\n+++ b/file\n@@\n- print(f'<h1>Welcome, {user_input}</h1>')\n+ print(f'<h1>Welcome, {html_escape(user_input)}</h1>')\n"

    elif "Hardcoded_Credential" in issue:
        suggestion = "Secrets (API keys, passwords) must never be hardcoded. Load them from a secure source like environment variables or a secret vault service."
        patch = "--- a/file\n+++ b/file\n@@\n- API_KEY = \"sk-1234567890\"\n+ API_KEY = os.environ.get(\"MY_API_KEY\")\n"

    elif "Path_Traversal" in issue or "Input_Validation" in issue:
        suggestion = "User input is used directly in a file path without sanitation. Sanitize the input (e.g., using `os.path.basename`) or canonicalize the path to prevent directory traversal attacks."
        patch = "--- a/file\n+++ b/file\n@@\n- with open(user_file_path)\n+ safe_path = os.path.basename(user_file_path)\n+ with open(safe_path)\n"

    elif "Unsafe_Deserialization" in issue:
        suggestion = "Deserializing untrusted data (e.g., using Python's `pickle`) can lead to remote code execution. Switch to a safe format like JSON or XML with a schema validator."
        patch = "--- a/file\n+++ b/file\n@@\n- data = pickle.loads(untrusted_bytes)\n+ # data = pickle.loads(untrusted_bytes)  # REMOVED\n+ # Use JSON/schema validation instead\n"
        
    elif "Insecure_Cookie_Flag" in issue:
        suggestion = "A sensitive cookie is missing the `Secure` flag. This flag must be set to ensure the cookie is only transmitted over HTTPS."
        patch = "--- a/file\n+++ b/file\n@@\n- set_cookie('session', data, secure=False)\n+ set_cookie('session', data, secure=True)\n"

    elif "LFI" in issue or "File_Inclusion" in issue:
        suggestion = "Local File Inclusion (LFI) is possible. Strictly whitelist or sanitize user input before loading any templates or file contents."
        patch = "--- a/file\n+++ b/file\n@@\n- load_template(user_template_name)\n+ if user_template_name in WHITELIST:\n+     load_template(user_template_name)\n"


    # --- Final Mock Return ---
    return {
        "root_cause": issue or "Possible_Bug",
        "fix_explanation": suggestion,
        "patch_unified_diff": patch,
        "references": [f"local_kb: mock-for-{issue.lower().replace('_', '-')}"] ,
        "confidence": 0.50, # Increased confidence for robust mock
        "_llm_status": "Mock LLM (Fallback)" # NEW        
    }


def generate_fix(lang, path, issue, span, code, passages):
    # This check now relies on the global _lm being set by _load_llm()
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
        # --- FIX: Explicitly set sampling params to their 'off' state ---
        do_sample=False,
        temperature=1.0, # Will be ignored but satisfies warning checks
        top_p=1.0,       # Will be ignored but satisfies warning checks
        top_k=0,         # Setting top_k=0 disables it
        # ---------------------------------------------------------------
        pad_token_id=_tok.eos_token_id
    )
    text = _tok.decode(outputs[0], skip_special_tokens=True)

    s, e = text.rfind("{"), text.rfind("}")
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return _mock_generate(issue, code)