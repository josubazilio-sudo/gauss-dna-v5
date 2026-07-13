from typing import Dict, Set

BASE_WEIGHT_DEFAULT = 0.5
MAX_WEIGHT_PER_SKILL = 0.5
NORMALIZE_TARGET = 1.0

REGIME_MULTIPLIERS: Dict[str, Dict[str, float]] = {
    "trending": {
        "default": 1.0,
        "smc": 1.5,
        "trend": 1.5,
        "volume": 1.3,
        "momentum": 1.3,
    },
    "ranging": {
        "default": 1.0,
        "liquidity": 1.5,
        "range": 1.5,
        "smc": 1.2,
    },
    "volatile": {
        "default": 1.0,
        "risk": 1.5,
        "volume": 1.3,
        "smc": 0.8,
    },
    "uncertain": {
        "default": 0.7,
    },
}

HEALTH_MULTIPLIERS = {
    "excellent": 1.5,
    "good": 1.2,
    "fair": 1.0,
    "degraded": 0.7,
    "critical": 0.4,
}

PERFORMANCE_MULTIPLIERS = {
    "high": 1.3,
    "medium": 1.0,
    "low": 0.7,
}

CONFIDENCE_MULTIPLIERS = {
    "high": 1.3,
    "medium": 1.0,
    "low": 0.7,
}

SPECIALIZATION_KEYWORDS: Dict[str, Set[str]] = {
    "smc": {"bos", "choch", "order_block", "fvg", "sweep",
            "break", "structure", "estrutura", "liquidity", "liquidez"},
    "volume": {"rvol", "volume", "flow", "fluxo", "delta",
               "adx", "institutional", "institucional"},
    "trend": {"trend", "tendencia", "ema", "moving_average",
              "macd", "media"},
    "momentum": {"rsi", "momentum", "impulso", "macd", "estocastico"},
    "liquidity": {"liquidity", "liquidez", "sweep", "order_block",
                  "supply", "demand", "oferta", "block"},
    "risk": {"risk", "risco", "spread", "volatility", "volatilidade",
             "atr", "drawdown"},
    "macro": {"macro", "btc", "dominance", "dominancia",
              "economic", "economico", "fed"},
    "range": {"range", "lateral", "suporte", "resistencia",
              "support", "resistance"},
}

PERFORMANCE_THRESHOLD_HIGH = 0.8
PERFORMANCE_THRESHOLD_LOW = 0.5

CONFIDENCE_THRESHOLD_HIGH = 0.7
CONFIDENCE_THRESHOLD_LOW = 0.4

from ENGINE.council.health_config import (
    EXCELLENT_MIN as HEALTH_EXCELLENT,
    GOOD_MIN as HEALTH_GOOD,
    FAIR_MIN as HEALTH_FAIR,
    DEGRADED_MIN as HEALTH_DEGRADED,
)

REGIME_CONFIDENCE_MIN = 0.3
