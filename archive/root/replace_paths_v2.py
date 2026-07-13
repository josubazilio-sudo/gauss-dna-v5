import os
import re
from pathlib import Path

target_dir = Path(r"C:\Users\josue\QuantOS\TESTS")

# Regex to find: sys.path.insert(0, ['"]C:\\Users\\josue\\QuantOS['"])
pattern = re.compile(r"sys\.path\.insert\(0,\s*['\"]C:\\\\Users\\\\josue\\\\QuantOS['\"]\)")
new_string = "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))"

for root, dirs, files in os.walk(target_dir):
    for file in files:
        if file.endswith(".py"):
            file_path = Path(root) / file
            content = file_path.read_text(encoding="utf-8")
            
            if pattern.search(content):
                content = pattern.sub(new_string, content)
                file_path.write_text(content, encoding="utf-8")
                print(f"Updated {file_path}")
