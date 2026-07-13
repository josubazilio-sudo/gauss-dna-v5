import logging

log = logging.getLogger(__name__)


class KalmanFilter1D:
    def __init__(self, process_noise=3e-4, measurement_noise=1e-2):
        self.Q = process_noise
        self.R = measurement_noise
        self.x = None
        self.P = 1.0
        self.initialized = False

    def update(self, measurement):
        if not self.initialized:
            self.x = measurement
            self.initialized = True
            return self.x
        x_pred = self.x
        P_pred = self.P + self.Q
        K = P_pred / (P_pred + self.R)
        self.x = x_pred + K * (measurement - x_pred)
        self.P = (1 - K) * P_pred
        return self.x


def _atr(highs, lows, closes, period=14):
    if len(closes) < period + 1 or len(highs) < period + 1 or len(lows) < period + 1:
        return 0
    tr_values = []
    for i in range(-period, 0):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr_values.append(max(hl, hc, lc))
    return sum(tr_values) / len(tr_values)


def _ema_init(closes, period=5):
    if len(closes) < period:
        return closes[-1] if closes else 0
    k = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period
    for p in closes[period:]:
        ema = p * k + ema * (1 - k)
    return ema


def _dynamic_threshold(closes, highs=None, lows=None, lookback=6, base=0.0003):
    if len(closes) < lookback + 1:
        return base
    if highs is not None and lows is not None and len(highs) >= lookback + 1 and len(lows) >= lookback + 1:
        atr_val = _atr(highs, lows, closes, lookback)
    else:
        ranges = [abs(closes[i] - closes[i - 1]) for i in range(-lookback, 0)]
        atr_val = sum(ranges) / len(ranges) if ranges else 0
    if atr_val and closes[-1] > 0:
        atr_pct = atr_val / closes[-1]
        return max(base, atr_pct * 0.12)
    recent_range = (max(closes[-lookback:]) - min(closes[-lookback:])) / closes[-1]
    return max(base, recent_range * 0.04)


def _smooth(closes):
    if not closes:
        return [], 0
    initial = _ema_init(closes, 5)
    kf = KalmanFilter1D()
    kf.x = initial
    kf.initialized = True
    smoothed = [kf.update(p) for p in closes]
    return smoothed, initial


def kalman_direction(closes, lookback=6, threshold=None):
    if not closes or len(closes) < 3:
        return "ERRO"
    try:
        smoothed, _ = _smooth(closes)
        if not smoothed or len(smoothed) < 2:
            return "ERRO"
        if len(smoothed) < lookback + 1:
            lb = max(2, len(smoothed) - 1)
            recent = smoothed[-lb:]
        else:
            recent = smoothed[-lookback:]
        if len(recent) < 2:
            return "ERRO"
        slope = (recent[-1] - recent[0]) / recent[0] if recent[0] != 0 else 0
        dyn = _dynamic_threshold(closes, lookback) if threshold is None else threshold
        if slope > dyn:
            return "UP"
        elif slope < -dyn:
            return "DOWN"
        return "SIDE"
    except Exception:
        return "ERRO"


def kalman_trend_state(closes, lookback=10):
    if len(closes) < lookback + 2:
        return "ranging"
    smoothed, _ = _smooth(closes)
    if len(smoothed) < lookback + 1:
        return "ranging"
    short_lb = 3
    denominator_short = smoothed[-1 - short_lb] if smoothed[-1 - short_lb] != 0 else 1
    short_slope = (smoothed[-1] - smoothed[-1 - short_lb]) / denominator_short
    denominator_long = smoothed[-1 - lookback] if smoothed[-1 - lookback] != 0 else 1
    long_slope = (smoothed[-1] - smoothed[-1 - lookback]) / denominator_long
    dyn = _dynamic_threshold(closes, lookback)
    short_active = abs(short_slope) > dyn
    long_active = abs(long_slope) > dyn
    if not short_active and not long_active:
        return "ranging"
    if short_active and not long_active:
        return "starting"
    if short_active and long_active:
        if (short_slope > 0 and long_slope > 0) or (short_slope < 0 and long_slope < 0):
            return "continuing"
        else:
            return "reversing"
    if not short_active and long_active:
        return "continuing"
    return "ranging"


def kalman_confidence(closes, lookback=6):
    if len(closes) < lookback + 2:
        return 0.0
    smoothed, _ = _smooth(closes)
    if len(smoothed) < lookback + 1:
        return 0.0
    recent = smoothed[-lookback:]
    denominator = recent[0] if recent[0] != 0 else 1
    slope = (recent[-1] - recent[0]) / denominator
    dyn = _dynamic_threshold(closes, lookback)
    if dyn == 0:
        return 0.0

    mag_conf = min(1.0, abs(slope) / (dyn * 2.5))

    half = lookback // 2
    consistency = 0.0
    if len(recent) >= half * 2:
        first_half = (recent[half] - recent[0]) / recent[0] if recent[0] != 0 else 0
        second_half = (recent[-1] - recent[half]) / recent[half] if recent[half] != 0 else 0
        if (first_half > 0 and second_half > 0) or (first_half < 0 and second_half < 0):
            consistency = min(1.0, abs(second_half) / (dyn * 1.5))
        elif (first_half > 0 and second_half < 0) or (first_half < 0 and second_half > 0):
            consistency = max(0.0, 1.0 - abs(second_half - first_half) / (dyn * 3))

    noise = 0.5
    if len(closes) >= len(smoothed):
        residuals = [abs(closes[i] - (smoothed[i] if i < len(smoothed) else closes[i])) for i in range(-lookback, 0)]
        if residuals and max(residuals) > 0:
            avg_res = sum(residuals) / len(residuals)
            noise = max(0.0, 1.0 - avg_res / (dyn * 3)) if dyn > 0 else 0.5

    kf = KalmanFilter1D()
    kf.x = _ema_init(closes, 5)
    kf.initialized = True
    for p in closes:
        kf.update(p)
    stability = max(0.0, 1.0 - kf.P / 2.0)

    raw = mag_conf * 0.40 + consistency * 0.30 + noise * 0.20 + stability * 0.10
    return round(max(0.0, min(1.0, raw)), 2)


def kalman_slope(closes, lookback=6):
    if len(closes) < lookback + 1:
        return 0.0
    smoothed, _ = _smooth(closes)
    if len(smoothed) < lookback + 1:
        return 0.0
    recent = smoothed[-lookback:]
    raw = (recent[-1] - recent[0]) / recent[0] if recent[0] != 0 else 0
    return raw


def kalman_tendency(closes, lookback=6):
    if len(closes) < lookback + 1:
        return 0.0
    smoothed, _ = _smooth(closes)
    if len(smoothed) < lookback + 1:
        return 0.0
    recent = smoothed[-lookback:]
    slope_val = (recent[-1] - recent[0]) / recent[0] if recent[0] != 0 else 0
    dyn = _dynamic_threshold(closes, lookback)
    if dyn == 0:
        return 0.0
    return max(-1.0, min(1.0, slope_val / (dyn * 2.5)))
