from pathlib import Path
import re

# Regex que captura EntryDetails com 3 argumentos e insere is_valid=True
pattern = re.compile(r'EntryDetails\(\s*entry_zone=(.*?),\s*score=(.*?),\s*approved=(.*?)\)', re.DOTALL)
replacement = r'EntryDetails(entry_zone=\1, score=\2, is_valid=True, approved=\3)'

for path in Path(r"C:\Users\josue\QuantOS\TESTS").rglob("*.py"):
    content = path.read_text(encoding="utf-8")
    if pattern.search(content):
        new_content = pattern.sub(replacement, content)
        path.write_text(new_content, encoding="utf-8")
        print(f"Fixed {path}")
