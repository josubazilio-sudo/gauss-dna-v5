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

# Gate Entry Quality (EQ) — bloquear late entry
ENTRY_QUALITY_BLOCK = os.getenv("ENTRY_QUALITY_BLOCK", "True").strip().lower() in ("1", "true", "yes", "on")
ENTRY_QUALITY_MIN   = float(os.getenv("ENTRY_QUALITY_MIN", "75"))
K11_OURO_MIN_EQ     = float(os.getenv("K11_OURO_MIN_EQ", "85"))


# ==== GATE 10/10 (qualidade sobre quantidade) ====
MODO_10_10         = os.getenv("MODO_10_10", "False").strip().lower() in ("1", "true", "yes", "on")
RVOL_MIN_10        = float(os.getenv("RVOL_MIN_10", "1.80"))
SCORE_OURO_10      = float(os.getenv("SCORE_OURO_10", "90"))
SCORE_PRATA_10     = float(os.getenv("SCORE_PRATA_10", "80"))
RR_MIN_10          = float(os.getenv("RR_MIN_10", "2.50"))
EXIGE_ESTRUTURA_10 = os.getenv("EXIGE_ESTRUTURA_10", "True").strip().lower() in ("1", "true", "yes", "on")
EXIGE_TENDENCIA_10 = os.getenv("EXIGE_TENDENCIA_10", "True").strip().lower() in ("1", "true", "yes", "on")
EXIGE_FLOW_10      = os.getenv("EXIGE_FLOW_10", "True").strip().lower() in ("1", "true", "yes", "on")
EXIGE_MOMENTUM_10  = os.getenv("EXIGE_MOMENTUM_10", "True").strip().lower() in ("1", "true", "yes", "on")
EXIGE_ENTRY_50_10  = os.getenv("EXIGE_ENTRY_50_10", "True").strip().lower() in ("1", "true", "yes", "on")
ENTRY_50_PCT_10    = float(os.getenv("ENTRY_50_PCT_10", "0.50"))
