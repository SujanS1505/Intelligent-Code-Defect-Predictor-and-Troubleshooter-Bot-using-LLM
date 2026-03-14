import re

file_path = r'e:\new projects\AI Code Guardian\rag\llm.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_bounds = '''    for i, line in enumerate(lines):
        if "range(n - i)" in line or "range(n-i)" in line:
            lines[i] = re.sub(r"range\\(n\\s*-\\s*i\\)", "range(n - i - 1)", line)
            changed = True'''

new_bounds = '''    for i, line in enumerate(lines):
        if "range(" in line and "- i)" in line:
            lines[i] = re.sub(r"range\\(([a-zA-Z0-9_]+)\\s*-\\s*i\\)", r"range(\\1 - i - 1)", line)
            if lines[i] != line:
                changed = True'''

content = content.replace(old_bounds, new_bounds)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Enhanced nested bounds detection to handle any variable')
