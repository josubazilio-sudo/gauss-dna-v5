"""DNA FLEX v7.1 — ÚLTIMO AJUSTE"""

import os

TIMEFRAME_OPERACAO = os.getenv("FLEX_TIMEFRAME_OPERACAO", "30m")
TIMEFRAME_CONFIRMACAO = os.getenv("FLEX_TIMEFRAME_CONFIRMACAO", "1h")
TIMEFRAME_MACRO = os.getenv("FLEX_TIMEFRAME_MACRO", "4h")
TIMEFRAMES = [TIMEFRAME_OPERACAO, TIMEFRAME_CONFIRMACAO, TIMEFRAME_MACRO]

MAX_CRYPTOS = int(os.getenv("FLEX_MAX_CRYPTOS", "300"))
CAPITAL = float(os.getenv("CAPITAL", "100"))
RISCO_POR_OPERACAO = float(os.getenv("RISCO_POR_OPERACAO", "0.02"))

# =========================
# BLACKLIST
# =========================
BLACKLIST = {
    "USDCUSDT", "FDUSDUSDT", "TUSDUSDT",
    "USDPUSDT", "USDSUSDT", "USD1USDT"
}

# =========================
# SCORE (V12: Novas faixas de classificação)
# =========================
SCORE_BRONZE_MIN = 75
SCORE_PRATA_MIN = 82
SCORE_OURO_MIN = 88
SCORE_OURO_SUPREMO_MIN = 93

# Confianca por categoria
CONFIANCA_BRONZE = 75
CONFIANCA_PRATA = 82
CONFIANCA_OURO = 88
CONFIANCA_OURO_SUPREMO = 93

MIN_INST_SCORE = 40
MIN_CONFIANCA = 60

# =========================
# ADX (Mais rigoroso)
# =========================
MIN_ADX = 22
ADX_BRONZE = 25
ADX_PRATA = 30
ADX_OURO = 35
ADX_OURO_SUPREMO = 40

# =========================
# RVOL (Mais rigoroso)
# =========================
MIN_RVOL = 1.0
RVOL_BRONZE = 1.0
RVOL_PRATA = 1.2
RVOL_OURO = 1.5
RVOL_OURO_SUPREMO = 2.0

# =========================
# RSI
# =========================
LONG_RSI_MIN = 45
LONG_RSI_MAX = 72
SHORT_RSI_MIN = 28
SHORT_RSI_MAX = 55

# =========================
# EMA 50 / EMA 200
# =========================
USE_EMA50_FILTER = True
USE_EMA200_FILTER = True

LONG_REQUIRE_PRICE_ABOVE_EMA50 = True
LONG_REQUIRE_PRICE_ABOVE_EMA200 = True
LONG_REQUIRE_EMA50_ABOVE_EMA200 = True

SHORT_REQUIRE_PRICE_BELOW_EMA50 = True
SHORT_REQUIRE_PRICE_BELOW_EMA200 = True
SHORT_REQUIRE_EMA50_BELOW_EMA200 = True

MIN_EMA50_EMA200_DISTANCE = 0.40

ALLOW_PULLBACK_EMA50 = True
MAX_PULLBACK_DISTANCE = 0.80

PENALTY_IF_AGAINST_EMA50 = -12
PENALTY_IF_AGAINST_EMA200 = -20

BLOCK_IF_MAIN_TREND_OPPOSITE = True

# =========================
# KALMAN
# =========================
ALLOW_KALMAN_SIDEWAYS_BRONZE = True
ALLOW_KALMAN_SIDEWAYS_PRATA = True
ALLOW_KALMAN_SIDEWAYS_OURO = True
ALLOW_KALMAN_SIDEWAYS_SUPREMO = True

KALMAN_UP_BONUS = 6
KALMAN_DOWN_BONUS = 6
KALMAN_SIDE_PENALIDADE = -4

# =========================
# FOLLOW THROUGH
# =========================
FOLLOW_THROUGH_MIN = 0.15

# =========================
# ATR
# =========================
ATR_MIN_PERCENT = 0.25
ATR_MAX_PERCENT = 5.00

ATR_MAX_BRONZE = 5.0
ATR_MAX_PRATA = 4.0
ATR_MAX_OURO = 3.0
ATR_MAX_OURO_SUPREMO = 2.5

# =========================
# Pesos dos filtros (%) - V9.1
# =========================
PESO_TENDENCIA    = 45
PESO_SMART_MONEY  = 20
PESO_FLUXO        = 15
PESO_ESTRUTURA    = 10
PESO_VOLUME       = 5
PESO_VOLATILIDADE = 5

# Novos Limiares e Pesos
MIN_RVOL_BLOQUEIO = 0.50
MIN_VOLUME_BLOQUEIO = 1_000_000
MAX_PENALIDADE_TOTAL = -8

# Fluxo Inteligente
FLUXO_FORTE = 6
FLUXO_MODERADO = 3
FLUXO_NEUTRO = 0
FLUXO_FRACO = -3

# Kalman Inteligente
KALMAN_UP = 5
KALMAN_SIDE = -1
KALMAN_DOWN = -5

SPREAD_MAXIMO = 0.30

# =========================
# VOLUME
# =========================
MIN_VOLUME_24H = 5_000_000
VOLUME_DINAMICO_ATIVO = True
VOLUME_MULTIPLICADOR = 1.5
VOLUME_MINIMO_ABSOLUTO = 5_000_000
VOLUME_MAXIMO_ABSOLUTO = 10_000_000

# =========================
# EXAUSTAO
# =========================
EXAUSTAO_BLOQUEIO_THRESHOLD = 45
EXAUSTAO_PENALIDADE_THRESHOLD = 20
EXAUSTAO_PENALIDADE = -15

# =========================
# GESTAO
# =========================
SL_ATR_MULT = float(os.getenv("SL_ATR_MULT", "1.0"))
TP1_ATR_MULT = float(os.getenv("TP1_ATR_MULT", "2.0"))
TP2_ATR_MULT = float(os.getenv("TP2_ATR_MULT", "3.0"))
TP1_PERCENT = float(os.getenv("TP1_PERCENT", "0.5"))

MOVE_STOP_TO_BE_AFTER_TP1 = True
TRAIL_AFTER_TP1 = True
TRAIL_PERCENT = 0.50

# =========================
# HORARIOS
# =========================
AVOID_LOW_VOLUME_SESSION = True
LOW_VOLUME_HOURS = (1, 2, 3, 4)

# =========================
# REENTRADA
# =========================
BLOCK_REENTRY_SAME_COIN = 4

# =========================
# FUNDING
# =========================
IGNORE_EXTREME_FUNDING = True

# =========================
# NEWS
# =========================
BLOCK_HIGH_IMPACT_NEWS = True

# =========================
# XAUT / GOLD
# =========================
MIN_ADX_XAUT = 25
MIN_RVOL_XAUT = 1.30

# =========================
# SCORE BONUS / PENALTY
# =========================
BONUS_PRICE_ABOVE_EMA50 = 6
BONUS_PRICE_ABOVE_EMA200 = 8
BONUS_EMA50_ABOVE_EMA200 = 10
BONUS_PULLBACK_EMA50 = 5

PENALTY_PRICE_BELOW_EMA50 = -12
PENALTY_PRICE_BELOW_EMA200 = -20

# =========================
# FINAL
# =========================
STRICT_TREND_MODE = True
INSTITUTIONAL_MODE = True

# RVOL dinâmico
RVOL_DINAMICO_ENABLED = True
RVOL_DINAMICO_WINDOW = 50

# Heikin Ashi
HA_CONTRARIO_PENALIDADE = -5

# API
MEXC_BASE = "https://api.mexc.com/api/v3"
MEXC_CONTRACT = "https://contract.mexc.com/api/v1/contract"

# Telegram
TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHATID = os.getenv("TG_CHATID", "")
