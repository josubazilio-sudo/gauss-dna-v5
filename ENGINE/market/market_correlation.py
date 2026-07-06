import logging
from typing import List

from .market_types import TrendDirection

log = logging.getLogger(__name__)


def compute_ema(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return values[-1:] if values else [0.0]
    multiplier = 2.0 / (period + 1)
    ema_values = [sum(values[:period]) / period]
    for v in values[period:]:
        ema_values.append((v - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def compute_correlation(series_a: List[float], series_b: List[float]) -> float:
    n = min(len(series_a), len(series_b))
    if n < 5:
        return 0.0
    a = series_a[-n:]
    b = series_b[-n:]
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((ai - mean_a) * (bi - mean_b) for ai, bi in zip(a, b))
    var_a = sum((ai - mean_a) ** 2 for ai in a)
    var_b = sum((bi - mean_b) ** 2 for bi in b)
    if var_a == 0 or var_b == 0:
        return 0.0
    r = cov / ((var_a * var_b) ** 0.5)
    return max(-1.0, min(1.0, r))


def compute_dominance_trend(btc_dominance: float, hist_dominance: List[float]) -> float:
    if not hist_dominance or len(hist_dominance) < 5:
        return 0.0
    avg_dom = sum(hist_dominance) / len(hist_dominance)
    if avg_dom == 0:
        return 0.0
    return round((btc_dominance - avg_dom) / avg_dom, 4)
