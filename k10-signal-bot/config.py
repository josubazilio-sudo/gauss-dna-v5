"""
Configurações do K10 Bot
Edite este arquivo ou use variáveis de ambiente via .env
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Chat IDs autorizados (deixar vazio para permitir todos)
# Ex: ALLOWED_CHAT_IDS = [123456789, -987654321]
_raw = os.getenv("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS = [int(x.strip()) for x in _raw.split(",") if x.strip()] if _raw else []

# ── Exchange ──────────────────────────────────────────────────────────────────
EXCHANGE = os.getenv("EXCHANGE", "binance")

# ── Watchlist para /scan ──────────────────────────────────────────────────────
WATCHLIST = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "AVAX/USDT",
    "MATIC/USDT",
    "DOT/USDT",
]

# ── Parâmetros do Quality Gate ────────────────────────────────────────────────
RR_MINIMO = float(os.getenv("RR_MINIMO", "2.0"))
ADX_MINIMO_TENDENCIA = float(os.getenv("ADX_MINIMO_TENDENCIA", "25.0"))
RVOL_MINIMO = float(os.getenv("RVOL_MINIMO", "1.0"))
SCORE_MINIMO = int(os.getenv("SCORE_MINIMO", "55"))

# ── Gestão de Banca ───────────────────────────────────────────────────────────
BANCA = float(os.getenv("BANCA", "90.0"))         # USDT
RISCO_PCT = float(os.getenv("RISCO_PCT", "3.0"))  # % da banca por trade

# ── Alavancagem dinâmica por Regime (range 8x–25x) ───────────────────────────
ALAVANCAGEM_POR_REGIME = {
    "Bull Trend":        25,
    "Bear Trend":        25,
    "Transição":         15,
    "Range":             10,
    "Alta Volatilidade":  8,
    "Baixa Volatilidade": 12,
}
