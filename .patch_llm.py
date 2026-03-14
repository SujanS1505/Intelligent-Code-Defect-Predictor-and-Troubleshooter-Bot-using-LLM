import re

file_path = r'e:\new projects\AI Code Guardian\rag\llm.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

insert_pos = None
for i, line in enumerate(lines):
    if 'def _patch_bounds_loops(text: str)' in line:
        insert_pos = i
        break

if insert_pos:
    function_code = '''def _patch_bounds_loops(text: str) -> tuple[str, bool]:
    if "<=" in text and ("for" in text or "while" in text):
        updated = text.replace("<=", "<")
        return updated, updated != text
    
    lines = text.splitlines()
    changed = False
    
    for i, line in enumerate(lines):
        if "range(n - i)" in line or "range(n-i)" in line:
            lines[i] = re.sub(r"range\\(n\\s*-\\s*i\\)", "range(n - i - 1)", line)
            changed = True
    
    if changed:
        return "\\n".join(lines), True
    
    i = 0
    while i < len(lines) - 1:
        if "arr[j] = arr[j + 1]" in lines[i] and i + 1 < len(lines) and "arr[j + 1] = arr[j]" in lines[i + 1]:
            indent = len(lines[i]) - len(lines[i].lstrip())
            lines[i] = " " * indent + "arr[j], arr[j + 1] = arr[j + 1], arr[j]  # fixed swap"
            lines.pop(i + 1)
            changed = True
        i += 1
    
    if changed:
        return "\\n".join(lines), True
    
    if "[" in text and "]" in text:
        updated, changed = _patch_direct_indexing(text)
        if changed:
            return updated, True
    
    return text, False
'''
    
    end_pos = insert_pos + 1
    while end_pos < len(lines) and not (lines[end_pos].startswith('def ') and end_pos > insert_pos + 1):
        end_pos += 1
    
    lines[insert_pos:end_pos] = [function_code + '\n\n']

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Patched _patch_bounds_loops')
