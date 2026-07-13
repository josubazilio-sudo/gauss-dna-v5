import re
from pathlib import Path

# Mapping of hardcoded strings to path variables from ENGINE.common.paths
replacements = {
    r'r"C:\\Users\\josue\\QuantOS\\MEMORY\\trade_history.json"': "TRADE_HISTORY_PATH",
    r'r"C:\\Users\\josue\\QuantOS\\MEMORY\\audit\\evidence"': "EVIDENCE_DIR",
    r'r"C:\\Users\\josue\\QuantOS\\MEMORY\\paper_trading.json"': "PAPER_TRADING_PATH",
    r'r"C:\\Users\\josue\\QuantOS\\MEMORY\\audit\\weights_v7.json"': "WEIGHTS_V7_PATH",
    r'r"C:\\Users\\josue\\QuantOS\\MEMORY\\learning_data.json"': "LEARNING_DATA_PATH",
    r"Path(r'C:\Users\josue\QuantOS\MEMORY\audit\metrics.json')": "METRICS_PATH",
}

import_stmt = "from ENGINE.common.paths import (\n    TRADE_HISTORY_PATH, EVIDENCE_DIR, PAPER_TRADING_PATH,\n    WEIGHTS_V7_PATH, LEARNING_DATA_PATH, METRICS_PATH\n)\n"

# Files to update
files_to_update = [
    r"C:\Users\josue\QuantOS\ENGINE\scanner\scanner_config.py",
    r"C:\Users\josue\QuantOS\ENGINE\scanner\evidence_registry.py",
    r"C:\Users\josue\QuantOS\ENGINE\scanner\auto_calibration.py",
    r"C:\Users\josue\QuantOS\ENGINE\probability\probability_engine.py",
    r"C:\Users\josue\QuantOS\ENGINE\learning\learning_engine.py",
    r"C:\Users\josue\QuantOS\CORE\metrics\validation_metrics.py",
]

for file_path in files_to_update:
    path = Path(file_path)
    if path.exists():
        content = path.read_text(encoding="utf-8")
        
        # Replace paths
        for old, new in replacements.items():
            content = content.replace(old, str(new))
            
        # Add import
        if import_stmt not in content:
            # Simple way to insert import after other imports
            content = re.sub(r'import .*\n', lambda m: m.group(0) + import_stmt if "import" in m.group(0) else m.group(0), content, count=1)
            # Fallback if no import found
            if import_stmt not in content:
                content = import_stmt + "\n" + content

        path.write_text(content, encoding="utf-8")
        print(f"Updated {path}")
