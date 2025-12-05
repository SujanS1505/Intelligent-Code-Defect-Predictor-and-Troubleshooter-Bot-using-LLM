import json, random, os
from faker import Faker

faker = Faker()

langs = ["Python", "Java", "C++", "JavaScript", "C#", "PHP", "Go", "Rust"]
error_types = [
    "NullPointerException", "IndexError", "ValueError", "SyntaxError",
    "ZeroDivisionError", "TypeError", "KeyError", "MemoryLeak",
    "Deadlock", "RaceCondition", "FileNotFound", "ConnectionTimeout",
    "SegmentationFault", "StackOverflow", "InvalidCast"
]

fix_templates = [
    "Add proper validation before performing this operation.",
    "Use try-except or equivalent error-handling structure.",
    "Check variable initialization before usage.",
    "Guard against division by zero.",
    "Ensure file exists before opening.",
    "Synchronize threads or use locks to prevent race conditions.",
    "Free allocated memory or close file handles after use.",
    "Replace deprecated function with modern equivalent.",
    "Use default value when key missing in dictionary/map.",
    "Validate user input to prevent runtime exceptions."
]

# Where to save
output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "kb", "clean_passages.jsonl")
os.makedirs(os.path.dirname(output_path), exist_ok=True)

records = []
for i in range(1, 2001):   # 2 000 examples
    lang = random.choice(langs)
    err = random.choice(error_types)
    fix = random.choice(fix_templates)
    code_snippet = faker.sentence(nb_words=6) + " ... " + faker.sentence(nb_words=6)

    text = (
        f"In {lang}, the error '{err}' often occurs when {faker.sentence(nb_words=12)} "
        f"Typical fix: {fix} Example code: {code_snippet}"
    )
    record = {
        "id": f"kb_{i}",
        "title": f"{lang} {err} Fix Pattern",
        "text": text
    }
    records.append(record)

# Write to JSONL
with open(output_path, "w", encoding="utf-8") as f:
    for r in records:
        json.dump(r, f, ensure_ascii=False)
        f.write("\n")

print(f"✅ Generated {len(records)} bug-fix examples → {output_path}")
