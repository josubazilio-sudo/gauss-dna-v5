import logging
from typing import List

from .scanner_types import Signal, SignalClassification
from .scanner_config import QUALITY_GATE_MIN_SCORE, MAX_CANDIDATES_PER_CYCLE

log = logging.getLogger(__name__)


def rank_signals(signals: List[Signal]) -> List[Signal]:
    return sorted(signals, key=lambda s: s.scores.quality_score, reverse=True)


def filter_by_threshold(signals: List[Signal], min_score: float = QUALITY_GATE_MIN_SCORE) -> List[Signal]:
    return [s for s in signals if s.scores.quality_score >= min_score]


def filter_top(signals: List[Signal], max_count: int = MAX_CANDIDATES_PER_CYCLE) -> List[Signal]:
    ranked = rank_signals(signals)
    return ranked[:max_count]


def pipeline(signals: List[Signal]) -> List[Signal]:
    filtered = filter_by_threshold(signals)
    ranked = rank_signals(filtered)
    return filter_top(ranked)
