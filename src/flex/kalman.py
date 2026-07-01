"""Kalman Filter — direcao do preco (UP, DOWN, SIDE)"""


class KalmanFilter1D:
    def __init__(self, process_noise=1e-5, measurement_noise=1e-2):
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


def kalman_slope(closes, lookback=12):
    """Retorna a inclinação normalizada do Kalman (valor bruto)."""
    if len(closes) < lookback + 1:
        return 0.0
    kf = KalmanFilter1D()
    smoothed = [kf.update(p) for p in closes]
    recent = smoothed[-lookback:]
    return (recent[-1] - recent[0]) / recent[0]


def _dynamic_threshold(closes, lookback=12, base=0.0015):
    """Threshold adaptativo baseado na volatilidade recente."""
    if len(closes) < lookback + 1:
        return base
    recent_range = (max(closes[-lookback:]) - min(closes[-lookback:])) / closes[-1]
    return max(base, recent_range * 0.15)


def kalman_direction(closes, lookback=12, threshold=None):
    """Retorna 'UP' (subindo), 'DOWN' (descendo), 'SIDE' (lateral).
    
    Usa threshold adaptativo baseado na volatilidade do ativo.
    Threshold fixo de 0.3% era muito alto para timeframes pequenos.
    """
    if len(closes) < lookback + 1:
        return "SIDE"
    kf = KalmanFilter1D()
    smoothed = [kf.update(p) for p in closes]
    recent = smoothed[-lookback:]
    slope = (recent[-1] - recent[0]) / recent[0]
    dyn = _dynamic_threshold(closes, lookback) if threshold is None else threshold
    if slope > dyn:
        return "UP"
    elif slope < -dyn:
        return "DOWN"
    return "SIDE"
