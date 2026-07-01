import os

# ═══════════════════════════════════════════════════════════════
# CONFIGURAÇÃO GERAL
# ═══════════════════════════════════════════════════════════════

TIMEFRAME_OPERACAO    = os.getenv("TIMEFRAME_OPERACAO", "30m")
TIMEFRAME_CONFIRMACAO = os.getenv("TIMEFRAME_CONFIRMACAO", "1h")
TIMEFRAME_MACRO       = os.getenv("TIMEFRAME_MACRO", "4h")

MAX_CRYPTOS = int(os.getenv("MAX_CRYPTOS", "300"))

RISCO_POR_OPERACAO = float(os.getenv("RISCO_POR_OPERACAO", "0.03"))
RISCO_DIARIO       = float(os.getenv("RISCO_DIARIO", "0.06"))

MAX_OPERACOES              = int(os.getenv("MAX_OPERACOES", "5"))
MAX_OPERACOES_SIMULTANEAS  = int(os.getenv("MAX_OPERACOES_SIMULTANEAS", "2"))

MAX_SINAIS_POR_CICLO = int(os.getenv("MAX_SINAIS_POR_CICLO", "5"))

MODO_AUTOMATICO = os.getenv("MODO_AUTOMATICO", "true").lower() == "true"
MODO_OURO       = os.getenv("MODO_OURO", "true").lower() == "true"
MODO_PRATA      = os.getenv("MODO_PRATA", "true").lower() == "true"
MODO_BRONZE     = os.getenv("MODO_BRONZE", "true").lower() == "true"

# ═══════════════════════════════════════════════════════════════
# TENDÊNCIA
# ═══════════════════════════════════════════════════════════════

EMA_PERIODOS = [10, 21, 50, 200]

# ═══════════════════════════════════════════════════════════════
# SMART MONEY
# ═══════════════════════════════════════════════════════════════

SMC_SWEEP_LOOKBACK = 12
SMC_BOS_CONFIRMACAO = 1.001

# ═══════════════════════════════════════════════════════════════
# VOLUME
# ═══════════════════════════════════════════════════════════════

RVOL_MINIMO = float(os.getenv("RVOL_MINIMO", "1.0"))

# ═══════════════════════════════════════════════════════════════
# MOMENTUM
# ═══════════════════════════════════════════════════════════════

RSI_PERIOD = 14
RSI_LONG_MIN = int(os.getenv("RSI_LONG_MIN", "40"))
RSI_LONG_MAX = int(os.getenv("RSI_LONG_MAX", "80"))
RSI_SHORT_MIN = int(os.getenv("RSI_SHORT_MIN", "20"))
RSI_SHORT_MAX = int(os.getenv("RSI_SHORT_MAX", "60"))

ADX_PERIOD = 14
ADX_MINIMO = int(os.getenv("ADX_MINIMO", "20"))

ATR_PERIOD = 14

# ═══════════════════════════════════════════════════════════════
# MACD
# ═══════════════════════════════════════════════════════════════

MACD_FAST = int(os.getenv("MACD_FAST", "12"))
MACD_SLOW = int(os.getenv("MACD_SLOW", "26"))
MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))

# ═══════════════════════════════════════════════════════════════
# VOLATILIDADE
# ═══════════════════════════════════════════════════════════════

VOL_ALTA_THRESHOLD = 1.8
VOL_BAIXA_THRESHOLD = 0.5
ATR_EXPANSAO_THRESHOLD = 1.3
ATR_COMPRESSAO_THRESHOLD = 0.7

# ═══════════════════════════════════════════════════════════════
# FILTROS
# ═══════════════════════════════════════════════════════════════

FILTRO_LATERAL      = os.getenv("FILTRO_LATERAL", "true").lower() == "true"
FILTRO_VOLUME       = os.getenv("FILTRO_VOLUME", "true").lower() == "true"
FILTRO_FLUXO        = os.getenv("FILTRO_FLUXO", "true").lower() == "true"
FILTRO_TENDENCIA    = os.getenv("FILTRO_TENDENCIA", "true").lower() == "true"
FILTRO_LIQUIDEZ     = os.getenv("FILTRO_LIQUIDEZ", "true").lower() == "true"
FILTRO_MOMENTUM     = os.getenv("FILTRO_MOMENTUM", "true").lower() == "true"
FILTRO_VOLATILIDADE = os.getenv("FILTRO_VOLATILIDADE", "true").lower() == "true"
FILTRO_NOTICIAS     = os.getenv("FILTRO_NOTICIAS", "false").lower() == "true"
FILTRO_SPREAD       = os.getenv("FILTRO_SPREAD", "true").lower() == "true"

# ═══════════════════════════════════════════════════════════════
# GESTÃO
# ═══════════════════════════════════════════════════════════════

CAPITAL = float(os.getenv("CAPITAL", "90"))

ALAVANCAGEM_MIN = int(os.getenv("ALAVANCAGEM_MIN", "5"))
ALAVANCAGEM_MAX = int(os.getenv("ALAVANCAGEM_MAX", "20"))

SL_ATR_MULT = float(os.getenv("SL_ATR_MULT", "1.5"))
TP1_ATR_MULT = float(os.getenv("TP1_ATR_MULT", "2.0"))
TP2_ATR_MULT = float(os.getenv("TP2_ATR_MULT", "3.0"))
TP1_PERCENT = float(os.getenv("TP1_PERCENT", "0.5"))

# ═══════════════════════════════════════════════════════════════
# SEGURANÇA
# ═══════════════════════════════════════════════════════════════

STOP_CONSECUTIVO_LIMITE = int(os.getenv("STOP_CONSECUTIVO_LIMITE", "3"))
LIMITE_STOPS = int(os.getenv("LIMITE_STOPS", "3"))
LIMITE_GAIN  = float(os.getenv("LIMITE_GAIN", "0.10"))
LIMITE_LOSS  = float(os.getenv("LIMITE_LOSS", "0.06"))

# ═══════════════════════════════════════════════════════════════
# IA ADAPTATIVA — Pesos iniciais (V7.3: Score por Pesos)
# ═══════════════════════════════════════════════════════════════

PESO_TENDENCIA    = 45
PESO_SMART_MONEY  = 20
PESO_FLUXO        = 15
PESO_ESTRUTURA    = 10
PESO_VOLUME       = 5
PESO_VOLATILIDADE = 5

PESO_MOMENTUM   = 20
PESO_LIQUIDEZ   = 15
PESO_MULTI_TIMEFRAME = 10
PESO_CONFIANCA  = 10
PESO_ATIVO      = 5

TOTAL_PESOS = sum([
    PESO_TENDENCIA, PESO_SMART_MONEY, PESO_FLUXO, 
    PESO_ESTRUTURA, PESO_VOLUME, PESO_VOLATILIDADE
])

# ═══════════════════════════════════════════════════════════════
# REGIME — V8 Institucional
# ═══════════════════════════════════════════════════════════════

REGIME_BULL = "BULL"
REGIME_BEAR = "BEAR"
REGIME_TRANSICAO = "TRANSICAO"
REGIME_LATERAL = "LATERAL"

REGIME_MULTIPLIER_BULL_LONG = float(os.getenv("REGIME_MULTIPLIER_BULL_LONG", "1.08"))
REGIME_MULTIPLIER_BULL_SHORT = float(os.getenv("REGIME_MULTIPLIER_BULL_SHORT", "0.92"))
REGIME_MULTIPLIER_BEAR_LONG = float(os.getenv("REGIME_MULTIPLIER_BEAR_LONG", "0.92"))
REGIME_MULTIPLIER_BEAR_SHORT = float(os.getenv("REGIME_MULTIPLIER_BEAR_SHORT", "1.08"))
REGIME_MULTIPLIER_TRANSICAO = float(os.getenv("REGIME_MULTIPLIER_TRANSICAO", "1.00"))
REGIME_MULTIPLIER_LATERAL = float(os.getenv("REGIME_MULTIPLIER_LATERAL", "0.95"))

# ═══════════════════════════════════════════════════════════════
# SCORE — V7.3 Nova Classificacao
# ═══════════════════════════════════════════════════════════════

SCORE_OURO_SUPREMO_MIN = int(os.getenv("SCORE_OURO_SUPREMO_MIN", "95"))
SCORE_OURO_MIN = int(os.getenv("SCORE_OURO_MIN", "90"))
SCORE_PRATA_MIN = int(os.getenv("SCORE_PRATA_MIN", "82"))
SCORE_BRONZE_MIN = int(os.getenv("SCORE_BRONZE_MIN", "75"))

CONFIANCA_MIN_FORTE = int(os.getenv("CONFIANCA_MIN_FORTE", "60"))
CONFIANCA_MIN_MODERADO = int(os.getenv("CONFIANCA_MIN_MODERADO", "58"))
CONFIANCA_MIN_FRACO = int(os.getenv("CONFIANCA_MIN_FRACO", "55"))

# ═══════════════════════════════════════════════════════════════
# RVOL DINAMICO (V7.3)
# ═══════════════════════════════════════════════════════════════

RVOL_FORTE = float(os.getenv("RVOL_FORTE", "1.20"))
RVOL_MODERADO = float(os.getenv("RVOL_MODERADO", "1.00"))
RVOL_FRACO = float(os.getenv("RVOL_FRACO", "0.80"))

# ═══════════════════════════════════════════════════════════════
# ADX ADAPTATIVO (V7.3)
# ═══════════════════════════════════════════════════════════════

ADX_ALTO = 30
ADX_MEDIO = 25
ADX_BAIXO = 20

# Pesos legados removidos para V9.0

# ═══════════════════════════════════════════════════════════════
# MEXC API
# ═══════════════════════════════════════════════════════════════

MEXC_BASE     = "https://api.mexc.com/api/v3"
MEXC_CONTRACT = "https://contract.mexc.com/api/v1/contract"

# ═══════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════

TG_TOKEN  = os.getenv("TG_TOKEN", "")
TG_CHATID = os.getenv("TG_CHATID", "")
