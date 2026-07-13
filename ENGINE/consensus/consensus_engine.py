import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..scanner.scanner_types import SignalDirection

from .consensus_config import (
    CONSENSUS_TIMEFRAME_ORDER, CONSENSUS_TIMEFRAME_WEIGHTS,
    CONSENSUS_MINIMUM_SCORE, CONSENSUS_DIRECTION_AGREEMENT_MIN,
    CONSENSUS_CLASSIFICATIONS,
)

log = logging.getLogger(__name__)


@dataclass
class TimeframeVote:
    timeframe: str
    direction: Optional[SignalDirection]
    score: float
    confidence: float
    weight: float


@dataclass
class ConsensusResult:
    final_direction: Optional[SignalDirection]
    consensus_score: float
    agreement_pct: float
    votes: List[TimeframeVote]
    classification: str
    dissenting_timeframes: List[str]
    dominant_timeframe: str

    def meets_minimum(self, min_score: float = CONSENSUS_MINIMUM_SCORE) -> bool:
        return self.consensus_score >= min_score and self.final_direction is not None


class ConsensusEngine:
    def __init__(self):
        self._tf_order = CONSENSUS_TIMEFRAME_ORDER

    def compute(
        self,
        timeframe_directions: Dict[str, SignalDirection],
        timeframe_scores: Dict[str, float],
        timeframe_confidence: Optional[Dict[str, float]] = None,
        entry_score: float = 0.0,
        quality_score: float = 0.0,
    ) -> ConsensusResult:
        votes: List[TimeframeVote] = []
        total_weight = 0.0
        weighted_long = 0.0
        weighted_short = 0.0

        for tf in self._tf_order:
            if tf not in timeframe_directions:
                continue
            direction = timeframe_directions[tf]
            score = timeframe_scores.get(tf, 0.0)
            confidence = timeframe_confidence.get(tf, 0.5) if timeframe_confidence else 0.5

            hierarchy_multipliers = {'1d': 2.0, '4h': 1.5, '1h': 1.0, '30m': 0.5}
            base_weight = CONSENSUS_TIMEFRAME_WEIGHTS.get(tf, 0.0)
            weight = base_weight * hierarchy_multipliers.get(tf, 1.0)

            if weight > 0:
                total_weight += weight
                if direction == SignalDirection.LONG:
                    weighted_long += weight * confidence
                elif direction == SignalDirection.SHORT:
                    weighted_short += weight * confidence

            votes.append(TimeframeVote(
                timeframe=tf,
                direction=direction,
                score=score,
                confidence=confidence,
                weight=weight,
            ))

        num_timeframes = len(votes)

        # Adaptive consensus:
        # 3+ TFs: institutional confirmation (current behavior)
        # 2 TFs: weighted average
        # 1 TF: quality + entry based
        if num_timeframes == 0:
            return ConsensusResult(
                final_direction=None,
                consensus_score=0.0,
                agreement_pct=0.0,
                votes=votes,
                classification="Sem dados",
                dissenting_timeframes=[],
                dominant_timeframe="",
            )

        if num_timeframes == 1:
            vote = votes[0]
            base = max(0.30, entry_score * 0.40 + quality_score * 0.30)
            confidence_boost = vote.confidence * 0.30
            consensus_score = round(min(base + confidence_boost, 1.0), 2)
            return ConsensusResult(
                final_direction=vote.direction,
                consensus_score=consensus_score,
                agreement_pct=1.0,
                votes=votes,
                classification=self._classify_single(consensus_score, entry_score),
                dissenting_timeframes=[],
                dominant_timeframe=vote.timeframe,
            )

        if num_timeframes == 2:
            long_pct = weighted_long / total_weight if total_weight > 0 else 0.0
            short_pct = weighted_short / total_weight if total_weight > 0 else 0.0
            agreement_pct = max(long_pct, short_pct)

            if long_pct > short_pct:
                final_direction = SignalDirection.LONG
                consensus_raw = long_pct
            else:
                final_direction = SignalDirection.SHORT
                consensus_raw = short_pct

            # Quando ha 2 TFs, o consenso e a media ponderada, mas com boost
            # do entry_score se estiver baixo
            consensus_score = round(max(consensus_raw, entry_score * 0.50), 2)

            dissenting = []
            for v in votes:
                if v.direction is not None and v.direction != final_direction and v.weight > 0:
                    dissenting.append(v.timeframe)

            classification = self._classify(consensus_score, agreement_pct)
            dominant_tf = self._dominant_timeframe(votes, final_direction)

            return ConsensusResult(
                final_direction=final_direction,
                consensus_score=consensus_score,
                agreement_pct=round(agreement_pct, 2),
                votes=votes,
                classification=classification,
                dissenting_timeframes=dissenting,
                dominant_timeframe=dominant_tf,
            )

        # 3+ TFs: institutional confirmation
        if total_weight == 0:
            return ConsensusResult(
                final_direction=None,
                consensus_score=0.0,
                agreement_pct=0.0,
                votes=votes,
                classification="Sem dados",
                dissenting_timeframes=[],
                dominant_timeframe="",
            )

        long_pct = weighted_long / total_weight
        short_pct = weighted_short / total_weight
        agreement_pct = max(long_pct, short_pct)

        if long_pct > short_pct:
            final_direction = SignalDirection.LONG
            consensus_raw = long_pct
        else:
            final_direction = SignalDirection.SHORT
            consensus_raw = short_pct

        consensus_score = round(consensus_raw, 2)

        dissenting = []
        for v in votes:
            if v.direction is not None and v.direction != final_direction and v.weight > 0:
                dissenting.append(v.timeframe)

        classification = self._classify(consensus_score, agreement_pct)
        dominant_tf = self._dominant_timeframe(votes, final_direction)

        return ConsensusResult(
            final_direction=final_direction,
            consensus_score=consensus_score,
            agreement_pct=round(agreement_pct, 2),
            votes=votes,
            classification=classification,
            dissenting_timeframes=dissenting,
            dominant_timeframe=dominant_tf,
        )

    def _classify(self, score: float, agreement: float) -> str:
        if score >= 0.80 and agreement >= 0.80:
            return "Dominante"
        if score >= 0.70 and agreement >= 0.70:
            return "Forte"
        if score >= 0.60 and agreement >= 0.60:
            return "Moderado"
        return "Fraco"

    def _classify_single(self, score: float, entry_score: float) -> str:
        if score >= 0.80 and entry_score >= 0.70:
            return "Forte"
        if score >= 0.65 and entry_score >= 0.55:
            return "Moderado"
        return "Fraco"

    @staticmethod
    def _dominant_timeframe(
        votes: List[TimeframeVote], direction: Optional[SignalDirection],
    ) -> str:
        for v in votes:
            if v.direction == direction and v.weight > 0 and v.confidence >= 0.6:
                return v.timeframe
        return votes[0].timeframe if votes else ""
