import os

# ═══════════════════════════════════════════════════════════════
# CONFIGURAÇÃO GERAL
# ═══════════════════════════════════════════════════════════════

TIMEFRAME_OPERACAO    = os.getenv("TIMEFRAME_OPERACAO", "15m")
TIMEFRAME_CONFIRMACAO = os.getenv("TIMEFRAME_CONFIRMACAO", "1h")
TIMEFRAME_MACRO       = os.getenv("TIMEFRAME_MACRO", "4h")

MAX_CRYPTOS = int(os.getenv("MAX_CRYPTOS", "300"))

RISCO_POR_OPERACAO = float(os.getenv("RISCO_POR_OPERACAO", "0.02"))
RISCO_DIARIO       = float(os.getenv("RISCO_DIARIO", "0.06"))

MAX_OPERACOES              = int(os.getenv("MAX_OPERACOES", "5"))
MAX_OPERACOES_SIMULTANEAS  = int(os.getenv("MAX_OPERACOES_SIMULTANEAS", "2"))

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

RVOL_MINIMO = float(os.getenv("RVOL_MINIMO", "1.2"))

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

CAPITAL = float(os.getenv("CAPITAL", "100"))

# ═══════════════════════════════════════════════════════════════
# SEGURANÇA
# ═══════════════════════════════════════════════════════════════

STOP_CONSECUTIVO_LIMITE = int(os.getenv("STOP_CONSECUTIVO_LIMITE", "3"))
LIMITE_STOPS = int(os.getenv("LIMITE_STOPS", "3"))
LIMITE_GAIN  = float(os.getenv("LIMITE_GAIN", "0.10"))
LIMITE_LOSS  = float(os.getenv("LIMITE_LOSS", "0.06"))

# ═══════════════════════════════════════════════════════════════
# IA ADAPTATIVA — Pesos iniciais
# ═══════════════════════════════════════════════════════════════

PESO_TENDENCIA    = 20
PESO_FLUXO        = 20
PESO_VOLUME       = 10
PESO_LIQUIDEZ     = 15
PESO_ESTRUTURA    = 20
PESO_MOMENTUM     = 10
PESO_VOLATILIDADE = 5
PESO_MULTI_TIMEFRAME = 5
PESO_CONFIANCA    = 10
PESO_ATIVO        = 5

TOTAL_PESOS = sum([
    PESO_TENDENCIA, PESO_FLUXO, PESO_VOLUME, PESO_LIQUIDEZ,
    PESO_ESTRUTURA, PESO_MOMENTUM, PESO_VOLATILIDADE,
    PESO_MULTI_TIMEFRAME, PESO_CONFIANCA, PESO_ATIVO
])

# ═══════════════════════════════════════════════════════════════
# SCORE
# ═══════════════════════════════════════════════════════════════

SCORE_OURO_MIN  = 95
SCORE_PRATA_MIN = 85
SCORE_BRONZE_MIN = 75

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
