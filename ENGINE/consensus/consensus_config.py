from ..scanner.scanner_config import (
    CONSENSUS_MINIMUM_SCORE as _CMS,
    CONSENSUS_TIMEFRAME_ORDER as _CTFO,
    CONSENSUS_TIMEFRAME_WEIGHTS as _CTFW,
)

CONSENSUS_TIMEFRAME_ORDER = _CTFO
CONSENSUS_TIMEFRAME_WEIGHTS = _CTFW
CONSENSUS_MINIMUM_SCORE = _CMS
CONSENSUS_DIRECTION_AGREEMENT_MIN = 0.50

CONSENSUS_CLASSIFICATIONS = {
    "dominante": {"min_agreement": 0.75, "label": "Dominante"},
    "forte": {"min_agreement": 0.65, "label": "Forte"},
    "moderado": {"min_agreement": 0.55, "label": "Moderado"},
    "fraco": {"min_agreement": 0.0, "label": "Fraco"},
}
