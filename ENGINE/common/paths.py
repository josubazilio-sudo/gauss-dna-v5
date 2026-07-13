from pathlib import Path

# Base directory for the project (resolved to the root of the QuantOS folder)
# Assuming paths.py is in ENGINE/common/paths.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]

MEMORY_DIR = PROJECT_ROOT / "MEMORY"
AUDIT_DIR = MEMORY_DIR / "audit"
EVIDENCE_DIR = AUDIT_DIR / "evidence"

# Specific file paths
TRADE_HISTORY_PATH = MEMORY_DIR / "trade_history.json"
LEARNING_DATA_PATH = MEMORY_DIR / "learning_data.json"
PAPER_TRADING_PATH = MEMORY_DIR / "paper_trading.json"
WEIGHTS_V7_PATH = AUDIT_DIR / "weights_v7.json"
METRICS_PATH = AUDIT_DIR / "metrics.json"
