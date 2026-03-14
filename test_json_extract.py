#!/usr/bin/env python
import json

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

# Test with markdown code block
text = '''```json
{"test": "value", "root_cause": "test issue"}
```'''

result = _extract_json(text)
print('Result:', result)
print('Success:', result is not None)
