import logging
import random
import math
from typing import List, Dict

from .backtest_types import Trade, RobustnessResult, BacktestResult
from .backtest_config import ROBUSTNESS_PARAMETER_NOISE, ROBUSTNESS_SENSITIVITY_THRESHOLD

log = logging.getLogger(__name__)


class RobustnessEngine:
    def __init__(self, noise_level: float = ROBUSTNESS_PARAMETER_NOISE):
        self._noise = noise_level

    def evaluate(self, trades: List[Trade]) -> RobustnessResult:
        if len(trades) < 20:
            return RobustnessResult()

        base_pnls = [t.pnl for t in trades]
        base_r = [t.r_multiple for t in trades]

        split_ratios = [0.6, 0.7, 0.8]
        split_scores = []
        for ratio in split_ratios:
            split_idx = int(len(trades) * ratio)
            first_half = trades[:split_idx]
            second_half = trades[split_idx:]
            if len(first_half) < 5 or len(second_half) < 5:
                continue
            pf1 = _profit_factor(first_half)
            pf2 = _profit_factor(second_half)
            if pf1 > 0:
                split_scores.append(min(pf2 / pf1, 1.0))

        wfa_score = sum(split_scores) / len(split_scores) if split_scores else 0.0

        noise_scores = []
        for _ in range(100):
            noisy = [p * (1 + random.uniform(-self._noise, self._noise)) for p in base_pnls]
            pos = sum(p for p in noisy if p > 0)
            neg = abs(sum(p for p in noisy if p < 0))
            noise_scores.append(pos / neg if neg > 0 else 10.0)

        base_pf = _profit_factor(trades)
        noise_avg = sum(noise_scores) / len(noise_scores) if noise_scores else 0
        noise_stability = 1.0 - min(abs(base_pf - noise_avg) / base_pf, 1.0) if base_pf > 0 else 0.0

        edge_decay = _compute_edge_decay(trades)

        robustness = wfa_score * 0.4 + noise_stability * 0.3 + (1.0 - edge_decay) * 0.3

        return RobustnessResult(
            robustness_score=round(robustness, 4),
            parameter_sensitivity={"wfa_consistency": round(wfa_score, 4),
                                    "noise_stability": round(noise_stability, 4)},
            overfitting_score=round(1.0 - min(wfa_score * 2, 1.0), 4) if wfa_score < 0.5 else round(1.0 - wfa_score, 4),
            underfitting_score=round(max(0, 1.0 - robustness * 1.5), 4),
            edge_decay_rate=round(edge_decay, 4),
        )


def _profit_factor(trades: List[Trade]) -> float:
    pos = sum(t.pnl for t in trades if t.pnl > 0)
    neg = abs(sum(t.pnl for t in trades if t.pnl < 0))
    return pos / neg if neg > 0 else (pos if pos > 0 else 1.0)


def _compute_edge_decay(trades: List[Trade]) -> float:
    if len(trades) < 20:
        return 0.0
    n = len(trades)
    first_half = trades[:n // 2]
    second_half = trades[n // 2:]
    pf1 = _profit_factor(first_half)
    pf2 = _profit_factor(second_half)
    if pf1 <= 0:
        return 1.0
    return max(0.0, 1.0 - pf2 / pf1)
