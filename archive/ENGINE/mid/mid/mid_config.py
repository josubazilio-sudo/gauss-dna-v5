import os

MID_ENABLED = os.getenv("QUANTOS_MID_ENABLED", "true").lower() in ("true", "1", "yes")
MID_INTERVAL_SECONDS = int(os.getenv("QUANTOS_MID_INTERVAL", "1800"))
MID_TELEGRAM_ENABLED = os.getenv("QUANTOS_MID_TELEGRAM", "true").lower() in ("true", "1", "yes")
MID_ALERT_COOLDOWN_SECONDS = int(os.getenv("QUANTOS_MID_ALERT_COOLDOWN", "300"))
MID_HISTORY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "MEMORY", "mid",
)
MID_MAX_HISTORY = 100

ALERT_TREND_THRESHOLD = 0.70
ALERT_RANGE_THRESHOLD = 0.70
ALERT_RVOL_SPIKE = 3.0
ALERT_VOLATILITY_SPIKE = 0.05
ALERT_CONSENSUS_SURGE = 0.15
ALERT_ELITE_COUNT = 3

HEATMAP_BINS = [
    ("Forte Tendencia", 0.7, 1.0, "\U0001f7e2"),
    ("Transicao", 0.3, 0.7, "\U0001f7e1"),
    ("Lateralizacao", 0.0, 0.3, "\U0001f534"),
]
