"""DNA FLEX V8 - Regime Institucional Inteligente.

Camada de contexto: ajusta score/confianca/gestao sem substituir o Architect.
"""

import json
import os
from datetime import datetime, timezone

from trend import ema


REGIME_BULL = "BULL"
REGIME_BEAR = "BEAR"
REGIME_TRANSICAO = "TRANSICAO"
REGIME_LATERAL = "LATERAL"
REGIME_LENTO = "LENTO"
REGIME_ALTA_VOLATILIDADE = "ALTA_VOLATILIDADE"

REGIME_PROFILES = {
    REGIME_BULL: {"min_score": 85, "kalman_penalty": 2, "rvol_mult": 1.0},
    REGIME_BEAR: {"min_score": 85, "kalman_penalty": 2, "rvol_mult": 1.0},
    REGIME_TRANSICAO: {"min_score": 80, "kalman_penalty": 0, "rvol_mult": 1.0},
    REGIME_LATERAL: {"min_score": 75, "kalman_penalty": -5, "rvol_mult": 1.2},
    REGIME_LENTO: {"min_score": 76, "kalman_penalty": -1, "rvol_mult": 0.8},
    REGIME_ALTA_VOLATILIDADE: {"min_score": 80, "kalman_penalty": 0, "rvol_mult": 1.5},
}

def get_regime_profile(regime):
    return REGIME_PROFILES.get(regime, REGIME_PROFILES[REGIME_TRANSICAO])


MAX_SCORE_DELTA = 15
WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "state", "watchlist.json")


def _clamp(value, low, high):
    return max(low, min(high, value))


def _ema200_slope(candles):
    closes = [c[4] for c in candles] if candles else []
    series = ema(closes, 200)
    if not series or len(series) < 6 or series[-6] == 0:
        return 0
    return (series[-1] - series[-6]) / series[-6] * 100


def _price_crossing_ema200(candles, trend_data, direction):
    closes = [c[4] for c in candles] if candles else []
    series = ema(closes, 200)
    ema200 = trend_data.get("EMA_200")
    if not series or len(series) < 2 or len(closes) < 2 or not ema200:
        return False
    if direction == "long":
        return closes[-2] <= series[-2] and closes[-1] > ema200
    return closes[-2] >= series[-2] and closes[-1] < ema200


def _flow_side(flow_data):
    delta = flow_data.get("DELTA", 0)
    if delta > 0:
        return "long"
    if delta < 0:
        return "short"
    return "neutral"


def _kalman_side(kalman_dir):
    if kalman_dir == "UP":
        return "long"
    if kalman_dir == "DOWN":
        return "short"
    return "neutral"


def _aligned(side, direction):
    return side == direction


def _last_body_ratio(candles):
    if not candles:
        return 0
    c = candles[-1]
    candle_range = c[2] - c[3]
    if candle_range <= 0:
        return 0
    return abs(c[4] - c[1]) / candle_range


def classify_regime(trend_data, flow_data, momentum_data, kalman_dir, candles):
    preco = flow_data.get("PRECO", 0)
    ema50 = trend_data.get("EMA_50")
    ema200 = trend_data.get("EMA_200")
    adx = momentum_data.get("ADX", 0)
    slope = _ema200_slope(candles)
    flow = _flow_side(flow_data)
    kalman = _kalman_side(kalman_dir)

    if not preco or not ema50 or not ema200:
        return REGIME_TRANSICAO

    dist_ema200 = abs(preco - ema200) / ema200 * 100 if ema200 else 0
    ema_gap = abs(ema50 - ema200) / ema200 * 100 if ema200 else 0

    if adx < 20 and abs(slope) < 0.05 and dist_ema200 < 1.5 and flow == "neutral":
        return REGIME_LATERAL
    if dist_ema200 <= 0.8 or ema_gap <= 0.3 or kalman == "neutral":
        return REGIME_TRANSICAO
    if preco > ema200 and ema50 > ema200 and slope > 0 and adx >= 25 and flow == "long" and kalman in ("long", "neutral"):
        return REGIME_BULL
    if preco < ema200 and ema50 < ema200 and slope < 0 and adx >= 25 and flow == "short" and kalman == "short":
        return REGIME_BEAR
    return REGIME_TRANSICAO


def _institutional_delta(trend_data, flow_data, momentum_data, kalman_dir, candles, direction):
    preco = flow_data.get("PRECO", 0)
    ema50 = trend_data.get("EMA_50")
    ema200 = trend_data.get("EMA_200")
    adx = momentum_data.get("ADX", 0)
    slope = _ema200_slope(candles)
    flow = _flow_side(flow_data)
    kalman = _kalman_side(kalman_dir)
    delta = 0

    if preco and ema200:
        above = preco > ema200
        delta += 2 if (direction == "long" and above) or (direction == "short" and not above) else -2
        dist = abs(preco - ema200) / ema200 * 100
        if 0.4 <= dist <= 4.0:
            delta += 2
        elif dist > 8.0:
            delta -= 2
    if ema50 and ema200:
        ema_ok = ema50 > ema200 if direction == "long" else ema50 < ema200
        delta += 2 if ema_ok else -2
    if slope != 0:
        slope_ok = slope > 0 if direction == "long" else slope < 0
        delta += 2 if slope_ok else -2
    delta += 2 if _aligned(flow, direction) else (-2 if flow != "neutral" else 0)
    delta += 2 if _aligned(kalman, direction) else (-2 if kalman != "neutral" else 0)
    delta += 2 if adx >= 25 else -2
    return _clamp(delta, -MAX_SCORE_DELTA, MAX_SCORE_DELTA)


def _multi_timeframe_delta(direction, direction_1h, direction_4h):
    dirs = [d for d in (direction, direction_1h, direction_4h) if d]
    aligned = sum(1 for d in dirs if d == direction)
    if len(dirs) >= 3 and aligned == 3:
        return 5, "3/3_alinhado"
    if aligned >= 2:
        return 2, "2/3_alinhado"
    return -3, "conflito"


def _ema200_breakout_delta(candles, trend_data, flow_data, momentum_data, kalman_dir, direction):
    if not _price_crossing_ema200(candles, trend_data, direction):
        return 0, "sem_rompimento_ema200"
    confirmed = (
        flow_data.get("RVOL", 0) >= 1.5 and
        momentum_data.get("ADX", 0) >= 25 and
        _last_body_ratio(candles) > 0.60 and
        _aligned(_flow_side(flow_data), direction) and
        _aligned(_kalman_side(kalman_dir), direction)
    )
    return (4, "rompimento_ema200_confirmado") if confirmed else (-4, "rompimento_ema200_fraco")


def _trap_delta(candles, flow_data, momentum_data, smc_data, direction):
    motivos = []
    if smc_data.get("LIQUIDITY_SWEEP"):
        motivos.append("liquidez_sem_continuacao")
    if flow_data.get("ABSORCAO"):
        motivos.append("absorpcao")
    if flow_data.get("EXAUSTAO"):
        motivos.append("volume_decrescente")
    if candles and _last_body_ratio(candles) > 0.75:
        rsi = momentum_data.get("RSI", 50)
        if (direction == "long" and rsi > 75) or (direction == "short" and rsi < 25):
            motivos.append("candle_exaustao")
    if len(candles or []) >= 3:
        last = candles[-1]
        prev = candles[-2]
        if direction == "long" and last[4] < prev[2] and last[2] > prev[2]:
            motivos.append("fake_breakout")
        if direction == "short" and last[4] > prev[3] and last[3] < prev[3]:
            motivos.append("fake_breakdown")
    motivos = motivos[:5]
    return -2 * len(motivos), motivos


def context_scores(regime, trend_data, flow_data, momentum_data, smc_data, market_data, direction):
    trend_ok = trend_data.get("DIRECAO") == direction
    flow_ok = _aligned(_flow_side(flow_data), direction)
    adx = momentum_data.get("ADX", 0)
    rvol = flow_data.get("RVOL", 0)
    return {
        "trend": 80 if trend_ok else 35,
        "volume": min(100, round(rvol * 40)),
        "momentum": min(100, round(adx * 2.5)),
        "smart_money": 80 if smc_data.get("BOS") else (60 if smc_data.get("CHOCH") else 45),
        "liquidity": 35 if smc_data.get("LIQUIDITY_SWEEP") else 70,
        "macro": 85 if regime in (REGIME_BULL, REGIME_BEAR) else (55 if regime == REGIME_TRANSICAO else 40),
        "risk": 75 if flow_ok and adx >= 25 else 45,
    }


def analyze_institutional_regime(symbol, direction, trend_data, flow_data, momentum_data,
                                 smc_data, market_data, kalman_dir, candles,
                                 direction_1h=None, direction_4h=None):
    regime = classify_regime(trend_data, flow_data, momentum_data, kalman_dir, candles)
    inst_delta = _institutional_delta(trend_data, flow_data, momentum_data, kalman_dir, candles, direction)
    mtf_delta, mtf_status = _multi_timeframe_delta(direction, direction_1h, direction_4h)
    breakout_delta, breakout_status = _ema200_breakout_delta(candles, trend_data, flow_data, momentum_data, kalman_dir, direction)
    trap_penalty, traps = _trap_delta(candles, flow_data, momentum_data, smc_data, direction)
    total_delta = _clamp(inst_delta + mtf_delta + breakout_delta + trap_penalty, -MAX_SCORE_DELTA, MAX_SCORE_DELTA)
    return {
        "symbol": symbol,
        "regime": regime,
        "score_delta": total_delta,
        "institutional_delta": inst_delta,
        "multi_timeframe_delta": mtf_delta,
        "multi_timeframe_status": mtf_status,
        "ema200_breakout_delta": breakout_delta,
        "ema200_breakout_status": breakout_status,
        "trap_penalty": trap_penalty,
        "traps": traps,
        "context_scores": context_scores(regime, trend_data, flow_data, momentum_data, smc_data, market_data, direction),
    }


def adjust_confidence(confidence, regime, direction):
    mult = 1.0
    if regime == REGIME_BULL:
        mult = 1.08 if direction == "long" else 0.92
    elif regime == REGIME_BEAR:
        mult = 1.08 if direction == "short" else 0.92
    elif regime == REGIME_LATERAL:
        mult = 0.95
    return round(_clamp(confidence * mult, 0, 100))


def dynamic_atr_stop_multiplier(atr_pct):
    atr_pct_100 = atr_pct * 100
    if atr_pct_100 < 1.0:
        return 1.5, "ATR_BAIXO"
    if atr_pct_100 < 2.5:
        return 1.8, "ATR_MEDIO"
    return 2.2, "ATR_ALTO"


def classify_priority(categoria, regime_data, flow_data, kalman_dir, direction, adx, rvol):
    regime = regime_data.get("regime")
    traps = regime_data.get("traps", [])
    mtf_ok = regime_data.get("multi_timeframe_status") == "3/3_alinhado"
    flow_strong = _aligned(_flow_side(flow_data), direction) and flow_data.get("VOLUME_CRESCENTE", False)
    kalman_ok = _aligned(_kalman_side(kalman_dir), direction)
    if regime in (REGIME_BULL, REGIME_BEAR) and mtf_ok and flow_strong and kalman_ok and adx >= 35 and rvol >= 1.5 and not traps:
        return "OURO_SUPREMO"
    if categoria in ("OURO_SUPREMO", "OURO"):
        return "OURO"
    if categoria == "PRATA":
        return "PRATA"
    return "BRONZE"


def record_watchlist(symbol, score, reason, pending_confirmation, regime_data):
    if score < 80:
        return False
    item = {
        "symbol": symbol,
        "score": score,
        "time": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "pending_confirmation": pending_confirmation,
        "regime": regime_data.get("regime"),
    }
    data = []
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE) as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    data = loaded
    except Exception:
        data = []
    data = [d for d in data if d.get("symbol") != symbol]
    data.append(item)
    try:
        os.makedirs(os.path.dirname(WATCHLIST_FILE), exist_ok=True)
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(data[-100:], f, indent=2)
        return True
    except Exception:
        return False
