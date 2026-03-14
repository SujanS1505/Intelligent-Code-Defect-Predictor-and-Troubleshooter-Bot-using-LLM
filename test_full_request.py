#!/usr/bin/env python
import os
import json
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai

api_key = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=api_key)

# Simulate code analysis request
system_prompt = (
    "You are a strict code troubleshooter. Return ONLY valid JSON with keys: "
    "root_cause, fix_explanation, patch_unified_diff, references, confidence. "
    "Do not include any text outside the JSON block."
)

user_prompt = """Language: python
File: test.py
Detected issue: ZeroDivisionError
Span: 1,10,1,15
Code:
```python
x = 1 / 0
```
Retrieved passages:
(No relevant passages found)
Return JSON only with keys: root_cause, fix_explanation, patch_unified_diff, references, confidence."""

print("Sending request to Gemini API...")
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content(
    f"{system_prompt}\n\n{user_prompt}",
    generation_config=genai.types.GenerationConfig(
        temperature=0.3,
        top_p=0.95,
        top_k=40,
        max_output_tokens=1024,
    ),
)

print(f"Raw response:\n{response.text}\n")

# Try to extract JSON
def _extract_json(text):
    try:
        return json.loads(text)
    except Exception:
        pass
    
    # Try to find JSON block
    s, e = text.rfind('{'), text.rfind('}')
    if 0 <= s < e:
        try:
            return json.loads(text[s : e + 1])
        except Exception:
            return None
    
    return None

result = _extract_json(response.text)
print(f"Extracted JSON: {result}")
print(f"Extraction success: {result is not None}")
