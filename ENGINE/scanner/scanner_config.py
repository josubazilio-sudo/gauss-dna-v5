import sys
from ENGINE.common.paths import (
    TRADE_HISTORY_PATH, EVIDENCE_DIR, PAPER_TRADING_PATH,
    WEIGHTS_V7_PATH, LEARNING_DATA_PATH, METRICS_PATH
)
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from CORE.utils.timeframe_manager import TimeframeManager

DEBUG_MODE = os.getenv("QUANTOS_DEBUG", "false").lower() in ("true", "1", "yes")

# RFC V19.3 — Prioridade Dinamica do Scanner: so afeta a ORDEM de varredura,
# nunca gates/thresholds/scoring. Lista VIP totalmente configuravel via .env.
SCANNER_VIP_PAIRS = [
    p.strip().upper() for p in os.getenv("SCANNER_VIP_PAIRS", "").split(",") if p.strip()
]
SCANNER_HOT_RESCAN_ENABLED = os.getenv("SCANNER_HOT_RESCAN_ENABLED", "false").lower() in ("true", "1", "yes")
SCANNER_HOT_RESCAN_TOP_N = int(os.getenv("SCANNER_HOT_RESCAN_TOP_N", "20"))

# RFC_RECALIBRACAO_SINAIS_INSTITUCIONAL.md (2026-07-11): thresholds elevados
# para padrao institucional apos redesenho da formula de quality_score (ver
# QUALITY_COMPONENT_CEILINGS abaixo). Ajuste de 2026-07-11 (segunda rodada):
# com 1567 avaliacoes reais coletadas, o teto real de quality_score entre
# os sinais que sobrevivem a todos os outros gates ficou em 0.692 (nunca
# atinge 0.70) — 0.60 captura 81% desses sinais e ainda fica bem acima do
# piso pre-recalibracao (0.45), restaurando fluxo de sinais sem voltar ao
# padrao antigo.
if DEBUG_MODE:
    QUALITY_GATE_MIN_SCORE = 0.55
    QUALITY_GATE_RISK_MAX = 0.60
    QUALITY_GATE_CONFIDENCE_MIN = 0.70
else:
    QUALITY_GATE_MIN_SCORE = 0.60
    QUALITY_GATE_RISK_MAX = 0.55
    QUALITY_GATE_CONFIDENCE_MIN = 0.70

# Novos gates institucionais (RFC_RECALIBRACAO_SINAIS_INSTITUCIONAL.md)
CONFIDENCE_GATE_MIN_SCORE = 0.75
CONFIDENCE_QUALITY_MAX_DIFF = 0.10
LATERAL_REGIMES = {"ranging"}

HARD_MIN_PATTERNS = 1
HARD_MIN_RVOL = 0.70
HARD_MAX_SPREAD = 0.001
HARD_MIN_ADX = 25
HARD_MIN_STRUCTURE_STRENGTH = 0.30
HARD_MAX_ATR_PCT = 0.05
HARD_MIN_ATR_PCT = 0.001

# V17 balanced gates (0-1 scale): calibrated to the current scanner score
# distribution while preserving consensus, RR, risk, liquidity and self-audit.
HARD_MIN_INSTITUTIONAL = 0.45
HARD_MIN_STRUCTURAL = 0.30
HARD_MIN_FLOW = 0.15
HARD_MIN_LIQUIDITY = 0.65
HARD_MIN_TIMING = 0.45
HARD_MIN_CONVICTION = 0.30
HARD_MIN_RR = 2.0

RANK_MIN_QUALITY = 0.65
RANK_MIN_CONFIDENCE = 0.60
RANK_MIN_CONSENSUS = 0.50
RANK_MIN_ENTRY = 0.55
RANK_MIN_CONVICTION = 0.55

# Discovery modes: "AUTO" (exchange, filtrado), "CUSTOM" (lista fixa), "DEBUG" (mock apenas)
DISCOVERY_MODE = os.getenv("QUANTOS_DISCOVERY_MODE", "AUTO").upper()

# MAX_SCAN_PAIRS aceita um inteiro (ex: "500") ou o literal "ALL" para
# escanear todos os pares elegiveis descobertos (sem corte fixo).
_max_scan_pairs_raw = os.getenv("QUANTOS_MAX_SCAN_PAIRS", "50").strip()
MAX_SCAN_PAIRS = None if _max_scan_pairs_raw.upper() == "ALL" else int(_max_scan_pairs_raw)

# Numero de pares processados em paralelo (fetch de candles + scan) por ciclo.
# I/O-bound (rede domina o tempo), entao threads bastam — nao precisa de
# multiprocessing. Mantido conservador por padrao para VPS com poucos
# recursos; ajustavel via QUANTOS_SCAN_MAX_WORKERS.
SCAN_MAX_WORKERS = int(os.getenv("QUANTOS_SCAN_MAX_WORKERS", "10"))

CUSTOM_PAIRS = os.getenv("QUANTOS_CUSTOM_PAIRS", "").split(",") if os.getenv("QUANTOS_CUSTOM_PAIRS") else []
if CUSTOM_PAIRS == [""]:
    CUSTOM_PAIRS = []

SCORE_THRESHOLD_OURO_SUPREMO = 0.9
SWING_LEFT_RIGHT = 3
BOS_CONFIRMATION_BARS = 3
FVG_MIN_GAP_BPS = 20  # aumentado de 5 para evitar gaps irrelevantes
OB_CONFIRMATION_BARS = 2

# Entry Zone
ENTRY_ZONE_MAX_AGE = 50
ENTRY_ZONE_MAX_ATR_DISTANCE = 1.0
ENTRY_ZONE_SCORE_MIN = 0.40  # revertido em 2026-07-11: 0.70 deixava passar so 15% dos candidatos
LIQUIDITY_SWEEP_RETRACE = 0.01

# V18.3: tabela fixa de classificacao derivada exclusivamente do Indice Geral.
# Nenhum sinal pode ter classificacao que contradiz seu indice numerico.
CLASSIFICATION_RANGES = {
    'DIAMANTE': {'min': 90, 'max': 100},
    'PLATINA': {'min': 80, 'max': 89},
    'OURO': {'min': 70, 'max': 79},
    'PRATA': {'min': 60, 'max': 69},
    'BRONZE': {'min': 50, 'max': 59},
}

# V18.3: requisitos minimos por classificacao, alem do indice geral.
CLASSIFICATION_REQUIREMENTS = {
    'DIAMANTE': {'quality': 0.90, 'rr': 3.5, 'consensus': 0.85, 'confidence': 0.90},
    'PLATINA': {'quality': 0.80, 'rr': 3.0, 'consensus': 0.75, 'confidence': 0.80},
    'OURO': {'quality': 0.70, 'rr': 2.5, 'consensus': 0.65, 'confidence': 0.70},
    'PRATA': {'quality': 0.60, 'rr': 2.0, 'consensus': 0.55, 'confidence': 0.60},
    'BRONZE': {'quality': 0.50, 'rr': 1.8, 'consensus': 0.50, 'confidence': 0.50},
}

QUALITY_TIERS = {
    'DIAMANTE': {'min_score': 92},
    'PLATINA': {'min_score': 82},
    'OURO': {'min_score': 72},
    'PRATA': {'min_score': 62},
    'BRONZE': {'min_score': 52},
}
RR_BASE_SL_MULTIPLIER = 1.5
RR_BASE_TP1_MULTIPLIER = 2.0
RR_BASE_TP2_MULTIPLIER = 4.0
RR_MIN_RR = 2.0
RR_IDEAL_RR = 3.0

# Capital e Alavancagem (QUANTOS V18.1)
ACCOUNT_SIZE = float(os.getenv("QUANTOS_ACCOUNT_SIZE", "200"))
LEVERAGE_MAX_USER = float(os.getenv("QUANTOS_LEVERAGE_MAX", "25"))

LEVERAGE_TABLE = [
    (0.95, 1.01, 25),
    (0.90, 0.95, 22),
    (0.85, 0.90, 20),
    (0.80, 0.85, 18),
    (0.75, 0.80, 15),
    (0.70, 0.75, 12),
    (0.65, 0.70, 10),
    (0.60, 0.65, 8),
]

MAX_CANDIDATES_PER_CYCLE = 20

CONSENSUS_MINIMUM_SCORE = 0.70  # RFC_RECALIBRACAO_SINAIS_INSTITUCIONAL.md: 0.50 -> 0.70
CONSENSUS_TIMEFRAME_WEIGHTS = {'30m': 0.1, '1h': 0.2, '4h': 0.3, '1d': 0.4}

CONFLUENCE_FILTERS = {
    "trend":           {"weight": 20},
    "choch":           {"weight": 15},
    "order_block":     {"weight": 12},
    "liquidity_sweep": {"weight": 10},
    "bos":             {"weight": 10},
    "fvg":             {"weight": 8},
    "volume":          {"weight": 8},
    "adx":             {"weight": 7},
    "momentum":        {"weight": 5},
    "volatility":      {"weight": 5},
}
CONFLUENCE_TOTAL = sum(v["weight"] for v in CONFLUENCE_FILTERS.values())

# Calibracao de teto real (RFC_RECALIBRACAO_SINAIS_INSTITUCIONAL.md, medido em
# 2026-07-11 com 3810 amostras reais / 3 ciclos de ~500 ativos via
# ENGINE/diagnostic/calibration_measurement.py). Estes 4 componentes nunca
# se aproximam de 1.0 mesmo no melhor setup observado (p99 da amostra) —
# sem reescalar, quality_score fica estruturalmente limitado a ~0.65 mesmo
# para o setup mais forte possivel, mascarando setups genuinamente fortes
# como "medianos". Usa o p99 (nao o maximo bruto) para nao deixar um unico
# outlier definir toda a escala.
QUALITY_COMPONENT_CEILINGS = {
    "flow_score": 0.50,
    "structural_score": 0.62,
    "risk_score": 0.57,
    "conviction_score": 0.67,
}

# V19.0 Score Weights — recalibrados para priorizar qualidade real sobre fluxo
SCORE_WEIGHTS = {
    'institutional': {
        'structural': 0.25, 'market': 0.15, 'momentum': 0.15,
        'liquidity': 0.15, 'risk': 0.10, 'confidence': 0.10,
        'flow': 0.10,
    },
    'quality_score': {
        'institutional': 0.15, 'structural': 0.14, 'market': 0.08,
        'momentum': 0.08, 'liquidity': 0.08, 'risk': 0.05,
        'confidence': 0.12, 'flow': 0.08, 'timing': 0.06,
        'conviction': 0.08, 'entry_score': 0.08,
    },
}

SWING_LOOKBACK = 5

DEFAULT_TIMEFRAMES = ['30m', '1h', '4h', '1d']
CONSENSUS_TIMEFRAME_ORDER = ['30m', '1h', '4h', '1d']

def validate_config():
    for tf in DEFAULT_TIMEFRAMES:
        if not TimeframeManager.is_valid(tf):
            raise ValueError(f'Configuracao invalida encontrada: {tf}')
    print('Configuracao de Timeframes validada com sucesso.')

# Probability Engine
PROBABILITY_MIN_SAMPLES = 30
PROBABILITY_DEFAULT_WIN_RATE = 0.40

# Learning Engine
LEARNING_HISTORY_PATH = str(TRADE_HISTORY_PATH)
LEARNING_MIN_TRADES_FOR_UPDATE = 50
LEARNING_WEIGHT_ADJUSTMENT_RATE = 0.05

# V19.1: Pesos da Expectativa (5 niveis)
EXPECTANCY_WEIGHTS = {
    "quality": 0.12,
    "confidence": 0.11,
    "consensus": 0.10,
    "structure": 0.09,
    "liquidity": 0.09,
    "momentum": 0.09,
    "trend_alignment": 0.08,
    "kalman_alignment": 0.07,
    "risk_inverted": 0.07,
    "atr_normalized": 0.04,
    "volatility_normalized": 0.03,
    "rvol_normalized": 0.06,
    "mtf_factor": 0.05,
}

# V19.0: Penalizações
PENALTY_ATR_ELEVADO = {"weight": 0.20, "label": "ATR elevado"}
PENALTY_ESTRUTURA_FRACA = {"weight": 0.25, "label": "Estrutura fraca"}
PENALTY_LIQUIDEZ_INSUFICIENTE = {"weight": 0.20, "label": "Liquidez insuficiente"}
PENALTY_RVOL_BAIXO = {"weight": 0.15, "label": "RVOL baixo"}
PENALTY_CONTRA_TENDENCIA = {"weight": 0.30, "label": "Contra tendência"}
PENALTY_KALMAN_CONTRARIO = {"weight": 0.25, "label": "Kalman contrário"}
PENALTY_PROXIMO_RESISTENCIA = {"weight": 0.15, "label": "Próximo de resistência"}
PENALTY_PROXIMO_SUPORTE = {"weight": 0.15, "label": "Próximo de suporte"}
PENALTY_MERCADO_LATERAL = {"weight": 0.20, "label": "Mercado lateral"}
PENALTY_SPREAD_ELEVADO = {"weight": 0.10, "label": "Spread elevado"}
PENALTY_BAIXO_CONSENSO = {"weight": 0.20, "label": "Baixo consenso"}

# V19.0: Limites de autoaprendizado
LEARNING_MIN_SAMPLES = 100
LEARNING_MIN_SAMPLES_PER_CLASSIFICATION = 20
LEARNING_SOURCES = ["paper_trading"]

# V18.4: Pesos da Votacao Institucional Ponderada
VOTE_WEIGHTS = {
    "kalman": 2.0,
    "estrutura": 2.0,
    "consenso": 1.8,
    "fluxo": 1.8,
    "regime": 1.5,
    "liquidez": 1.3,
    "momentum": 1.2,
    "qualidade": 1.0,
    "confianca": 1.0,
    "padrao": 0.8,
}

VOTE_MIN_CONCORDANCE_PCT = 70.0

# V18.4: Faixas do Institutional Coherence Score
COHERENCE_RANGES = {
    "Excelente": (95, 100),
    "Muito Alta": (85, 94),
    "Boa": (70, 84),
    "Fraca": (60, 69),
    "Rejeitar": (0, 59),
}

# V18.4: Gate de Validacao Final
FINAL_VALIDATION_GATES = {
    "long_kalman_down": "LONG + Kalman DOWN",
    "short_kalman_up": "SHORT + Kalman UP",
    "classificacao_divergente": "Classificacao incompativel com indice",
    "lateral_expectativa_alta": "Mercado lateral com expectativa alta sem rompimento",
}

if __name__ == '__main__':
    validate_config()
