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


def kalman_direction(closes, lookback=12):
    """Retorna 'UP' (subindo), 'DOWN' (descendo), 'SIDE' (lateral).

    Regra: Nunca permite que o Kalman elimine sozinho um excelente sinal.
           A penalização ocorre por fora, no score.
    """
    if len(closes) < lookback + 1:
        return "SIDE"
    kf = KalmanFilter1D()
    smoothed = [kf.update(p) for p in closes]
    recent = smoothed[-lookback:]
    slope = (recent[-1] - recent[0]) / recent[0]
    if slope > 0.003:
        return "UP"
    elif slope < -0.003:
        return "DOWN"
    return "SIDE"
