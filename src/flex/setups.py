"""
Módulo 3: Detector de Setup V9.0
Hierarquia: Setup Identificado -> Score -> Gestão de Risco
"""

def detect_setup(candles, trend, smc, flow, momentum, direction=None):
    """
    Classifica o setup institucional com base na hierarquia V9.0
    """
    # Dados básicos
    c = candles[-1][4]
    closes = [x[4] for x in candles]
    highs = [x[2] for x in candles]
    lows = [x[3] for x in candles]
    bos = smc.get("BOS", False)
    choch = smc.get("CHOCH", False)
    fvg = smc.get("FVG", False)
    ob = smc.get("ORDER_BLOCK", False)
    sweep = smc.get("LIQUIDITY_SWEEP", False)
    reteste = smc.get("RETESTE", False)
    tendencia = trend.get("TENDENCIA", "").lower()
    if direction is None:
        direction = trend.get("DIRECAO", "lateral")
    rsi = momentum.get("RSI", 50)
    adx = momentum.get("ADX", 0)
    atr = momentum.get("ATR", 0)
    ema21 = trend.get("EMA_21")
    delta = flow.get("DELTA", 0)
    fluxo_a_favor = (direction == "long" and delta > 0) or (direction == "short" and delta < 0)

    pullback_saudavel = False
    if ema21 and atr and c > 0 and len(closes) >= 5:
        dist_ema21 = abs(c - ema21) / c * 100
        retracao = (max(highs[-8:]) - c) / max(highs[-8:]) * 100 if direction == "long" else (c - min(lows[-8:])) / c * 100
        corpo_rejeicao = abs(closes[-1] - candles[-1][1]) >= (highs[-1] - lows[-1]) * 0.35 if highs[-1] > lows[-1] else False
        pullback_saudavel = 0.10 <= dist_ema21 <= 1.80 and retracao <= 3.50 and corpo_rejeicao
    
    # Setup 1: Pullback Institucional
    if direction in ("long", "short") and ("alta" in tendencia or "baixa" in tendencia) and (ob or fvg) and (reteste or pullback_saudavel) and fluxo_a_favor and adx >= 18:
        return {"name": "Pullback Institucional", "quality": 5, "priority": 100, "prob": 0.82}
        
    # Setup 2: Rompimento Confirmado
    if bos and flow.get("VOLUME_CRESCENTE", False) and fluxo_a_favor and adx >= 18:
        return {"name": "Rompimento Confirmado", "quality": 4, "priority": 90, "prob": 0.67}
        
    # Setup 4: Liquidity Sweep
    if sweep and (choch or bos or fluxo_a_favor) and 30 <= rsi <= 70:
        return {"name": "Liquidity Sweep", "quality": 5, "priority": 95, "prob": 0.79}
        
    # Setup 6: Reversão CHoCH
    if choch and fluxo_a_favor and adx >= 18:
        return {"name": "Reversão CHoCH", "quality": 4, "priority": 88, "prob": 0.72}

    return None
