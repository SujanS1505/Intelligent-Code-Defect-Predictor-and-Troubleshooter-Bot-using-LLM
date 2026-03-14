import re

file_path = r'e:\new projects\AI Code Guardian\rag\llm.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_swap_logic = '''    i = 0
    while i < len(lines) - 1:
        curr_stripped = lines[i].strip()
        next_stripped = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if "=" in curr_stripped and "=" in next_stripped and "[j]" in curr_stripped and "[j]" in next_stripped:
            if re.search(r"arr\[j\]\s*=\s*arr\[j\s*\+\s*1\]", curr_stripped) and re.search(r"arr\[j\s*\+\s*1\]\s*=\s*arr\[j\]", next_stripped):
                indent = len(lines[i]) - len(lines[i].lstrip())
                lines[i] = " " * indent + "arr[j], arr[j + 1] = arr[j + 1], arr[j]  # fixed swap"
                lines.pop(i + 1)
                changed = True
        i += 1'''

new_swap_logic = '''    i = 0
    while i < len(lines) - 1:
        curr = lines[i].strip()
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if ("arr[j]" in curr and "arr[j + 1]" in curr and "=" in curr and
            "arr[j + 1]" in next_line and "arr[j]" in next_line and "=" in next_line):
            if curr.startswith("arr[j]") and next_line.startswith("arr[j + 1]"):
                indent = len(lines[i]) - len(lines[i].lstrip())
                lines[i] = " " * indent + "arr[j], arr[j + 1] = arr[j + 1], arr[j]  # fixed swap"
                lines.pop(i + 1)
                changed = True
        i += 1'''

content = content.replace(old_swap_logic, new_swap_logic)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Simplified swap detection')
