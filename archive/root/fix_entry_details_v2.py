import re
from pathlib import Path

target_dir = Path(r"C:\Users\josue\QuantOS\TESTS")

# Padrão: EntryDetails(entry_zone=..., score=..., approved=...)
# Precisa virar: EntryDetails(entry_zone=..., score=..., is_valid=True, approved=...)
# Vou assumir is_valid=True para os testes.

# Regex to find: EntryDetails(entry_zone=([^,]+),\s*score=([^,]+),\s*approved=([^)]+)\)
# Substituir por: EntryDetails(entry_zone=\1, score=\2, is_valid=True, approved=\3)
pattern = re.compile(r"EntryDetails\(\s*entry_zone=([^,]+),\s*score=([^,]+),\s*approved=([^)]+)\)")
new_string = r"EntryDetails(entry_zone=\1, score=\2, is_valid=True, approved=\3)"

for root, dirs, files in os.walk(target_dir):
    for file in files:
        if file.endswith(".py"):
            file_path = Path(root) / file
            content = file_path.read_text(encoding="utf-8")
            
            if pattern.search(content):
                content = pattern.sub(new_string, content)
                file_path.write_text(content, encoding="utf-8")
                print(f"Updated {file_path}")
