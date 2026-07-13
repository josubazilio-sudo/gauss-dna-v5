import logging

log = logging.getLogger(__name__)

SETUP_HIERARCHY = {
    "Pullback Institucional": {"quality": 5, "priority": 100, "prob": 0.82},
    "Liquidity Sweep": {"quality": 5, "priority": 95, "prob": 0.79},
    "Rompimento Confirmado": {"quality": 4, "priority": 90, "prob": 0.67},
    "Reversao CHoCH": {"quality": 4, "priority": 88, "prob": 0.72},
    "Tendencia Momentum": {"quality": 3, "priority": 75, "prob": 0.58},
    "Price Action EMA": {"quality": 2, "priority": 65, "prob": 0.52},
    "Direcional": {"quality": 2, "priority": 60, "prob": 0.50},
}


def detect_setup(candles, structure, patterns, flow_data, momentum, direction=None):
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]

    has_bos = any(p.type.value == "bos" for p in patterns)
    has_choch = any(p.type.value == "choch" for p in patterns)
    has_fvg = any(p.type.value == "fvg" for p in patterns)
    has_ob = any(p.type.value == "order_block" for p in patterns)
    has_sweep = any(p.type.value == "liquidity_sweep" for p in patterns)

    estrutura_ok = structure.structure_strength >= 0.3
    tendencia = structure.structure_type.value

    if direction is None:
        direction = "long" if tendencia == "uptrend" else "short" if tendencia == "downtrend" else "lateral"

    rsi = momentum.get("rsi", 50)
    adx = momentum.get("adx", 0)
    atr = momentum.get("atr", 0)
    ema21 = momentum.get("ema_21", 0)
    delta = flow_data.get("delta", 0)
    rvol = flow_data.get("rvol", 1.0)
    vol_cres = flow_data.get("volume_crescente", False)
    fluxo_a_favor = (direction == "long" and delta > 0) or (direction == "short" and delta < 0)

    ob_valido = has_ob and (estrutura_ok or has_bos or has_choch)
    fvg_valido = has_fvg and (tendencia == direction)

    current_price = candles[-1].close if candles else 0
    pullback_saudavel = False
    if ema21 and atr and current_price > 0 and len(closes) >= 5:
        dist_ema21 = abs(current_price - ema21) / current_price * 100
        retracao = 0.0
        if direction == "long" and highs:
            retracao = (max(highs[-8:]) - current_price) / max(highs[-8:]) * 100 if max(highs[-8:]) > 0 else 0
        elif direction == "short" and lows:
            retracao = (current_price - min(lows[-8:])) / current_price * 100 if current_price > 0 else 0
        corpo_rejeicao = True
        pullback_saudavel = 0.10 <= dist_ema21 <= 1.80 and retracao <= 3.50 and corpo_rejeicao

    if direction in ("long", "short") and tendencia in ("uptrend", "downtrend") and (ob_valido or fvg_valido) and (has_sweep or pullback_saudavel) and fluxo_a_favor and adx >= 18:
        return {"name": "Pullback Institucional", "quality": 5, "priority": 100, "prob": 0.82}

    if has_bos and vol_cres and fluxo_a_favor and adx >= 18:
        return {"name": "Rompimento Confirmado", "quality": 4, "priority": 90, "prob": 0.67}

    if has_sweep and (has_choch or has_bos or fluxo_a_favor) and 30 <= rsi <= 70:
        return {"name": "Liquidity Sweep", "quality": 5, "priority": 95, "prob": 0.79}

    if has_choch and fluxo_a_favor and adx >= 18:
        return {"name": "Reversao CHoCH", "quality": 4, "priority": 88, "prob": 0.72}

    if direction in ("long", "short") and adx >= 18 and 30 < rsi < 70:
        if fluxo_a_favor or vol_cres:
            return {"name": "Tendencia Momentum", "quality": 3, "priority": 75, "prob": 0.58}

    if direction in ("long", "short") and not pullback_saudavel and adx >= 15:
        return {"name": "Price Action EMA", "quality": 2, "priority": 65, "prob": 0.52}

    if direction in ("long", "short") and adx >= 20 and fluxo_a_favor:
        return {"name": "Direcional", "quality": 2, "priority": 60, "prob": 0.50}

    return None
