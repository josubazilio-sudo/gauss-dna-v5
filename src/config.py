import os

# MEXC API
MEXC_BASE = "https://api.mexc.com/api/v3"
MEXC_CONTRACT = "https://contract.mexc.com/api/v1/contract"

# Timeframes
TIMEFRAMES = {
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "4h": "4h",
}

CLASSIFICATION = {
    "OURO": {"min_score": 95, "alavancagem": 15, "margem": 50},
    "PRATA": {"min_score": 85, "alavancagem": 10, "margem": 30},
    "BRONZE": {"min_score": 75, "alavancagem": 5, "margem": 15},
}

SCORE_WEIGHTS = {
    "tendencia": 20,
    "fluxo": 20,
    "estrutura": 20,
    "liquidez": 15,
    "momentum": 10,
    "volume": 10,
    "volatilidade": 5,
}

# Filtros técnicos
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
ADX_MIN = 20
RVOL_MIN = 1.2

# Risco
RISCO_PERCENTUAL = 0.02
MAX_POSICOES = 3
STOP_SEQUENCE_PAUSE = 2

# Telegram
TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHATID = os.getenv("TG_CHATID", "")
