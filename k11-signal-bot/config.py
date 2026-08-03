import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
_raw = os.getenv("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS = [int(x.strip()) for x in _raw.split(",") if x.strip()] if _raw else []

EXCHANGE = "mexc"
BANCA    = float(os.getenv("BANCA", "90.0"))
RISCO_PCT = float(os.getenv("RISCO_PCT", "3.0"))

ALAVANCAGEM_POR_REGIME = {
    "Bull Trend": 25, "Bear Trend": 25,
    "Transição": 15, "Range": 10,
    "Alta Volatilidade": 8, "Baixa Volatilidade": 12,
}
