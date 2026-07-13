import os
from pathlib import Path

target_dir = Path(r"C:\Users\josue\QuantOS\TESTS")
old_string = "sys.path.insert(0, 'C:\\Users\\josue\\QuantOS')"
new_string = "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))"

# For variations in quotes
variations = [
    "sys.path.insert(0, 'C:\\Users\\josue\\QuantOS')",
    'sys.path.insert(0, "C:\\Users\\josue\\QuantOS")',
]

for root, dirs, files in os.walk(target_dir):
    for file in files:
        if file.endswith(".py"):
            file_path = Path(root) / file
            content = file_path.read_text(encoding="utf-8")
            
            replaced = False
            for old in variations:
                if old in content:
                    content = content.replace(old, new_string)
                    replaced = True
            
            if replaced:
                file_path.write_text(content, encoding="utf-8")
                print(f"Updated {file_path}")
