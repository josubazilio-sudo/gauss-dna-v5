import os
import re
from pathlib import Path

target_dir = Path(r"C:\Users\josue\QuantOS\TESTS")

# Padrão: EntryDetails(zone=...
# Substituir por: EntryDetails(entry_zone=...
pattern = re.compile(r"EntryDetails\(\s*zone=")
new_string = "EntryDetails(entry_zone="

for root, dirs, files in os.walk(target_dir):
    for file in files:
        if file.endswith(".py"):
            file_path = Path(root) / file
            content = file_path.read_text(encoding="utf-8")
            
            if pattern.search(content):
                content = pattern.sub(new_string, content)
                file_path.write_text(content, encoding="utf-8")
                print(f"Updated {file_path}")
