from ..scanner.scanner_config import CONSENSUS_MINIMUM_SCORE, CONSENSUS_TIMEFRAME_ORDER, CONSENSUS_TIMEFRAME_WEIGHTS

CONSENSUS_TIMEFRAME_ORDER = CONSENSUS_TIMEFRAME_ORDER
CONSENSUS_TIMEFRAME_WEIGHTS = CONSENSUS_TIMEFRAME_WEIGHTS
CONSENSUS_MINIMUM_SCORE = CONSENSUS_MINIMUM_SCORE
CONSENSUS_DIRECTION_AGREEMENT_MIN = 0.60

CONSENSUS_CLASSIFICATIONS = {
    "dominant": {"min_agreement": 0.80, "label": "Dominante"},
    "forte": {"min_agreement": 0.70, "label": "Forte"},
    "moderado": {"min_agreement": 0.60, "label": "Moderado"},
    "fraco": {"min_agreement": 0.0, "label": "Fraco"},
}

CONSENSUS_MINIMUM_SCORE = 0.6
