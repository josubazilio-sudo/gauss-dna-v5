"""Módulo 2: Análise de Tendência — preenche variáveis TENDÊNCIA."""

from kalman import kalman_direction


def ema(data, period):
    if len(data) < period:
        return None
    k = 2 / (period + 1)
    result = [sum(data[:period]) / period]
    for price in data[period:]:
        result.append(price * k + result[-1] * (1 - k))
    return result


def analyze_trend(candles):
    """
    Motor V9.1: Classificação Institucional Ponderada
    """
    closes = [c[4] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]
    mm10 = ema(closes, 10)
    mm21 = ema(closes, 21)
    mm50 = ema(closes, 50)
    mm200 = ema(closes, 200)
    
    if not all([mm10, mm21, mm50]):
        return {"TENDENCIA": "Neutra", "DIRECAO": "lateral", "BONS": 0}

    c, m10, m21, m50 = closes[-1], mm10[-1], mm21[-1], mm50[-1]
    m200 = mm200[-1] if mm200 else m50
    m10_prev = mm10[-4] if len(mm10) >= 4 else mm10[-1]
    m21_prev = mm21[-4] if len(mm21) >= 4 else mm21[-1]
    m50_prev = mm50[-6] if len(mm50) >= 6 else mm50[-1]
    slope10 = (m10 - m10_prev) / m10_prev * 100 if m10_prev else 0
    slope21 = (m21 - m21_prev) / m21_prev * 100 if m21_prev else 0
    slope50 = (m50 - m50_prev) / m50_prev * 100 if m50_prev else 0
    dist_10_21 = abs(m10 - m21) / c * 100 if c else 0
    dist_21_50 = abs(m21 - m50) / c * 100 if c else 0
    recent_range = (max(highs[-20:]) - min(lows[-20:])) / c * 100 if c and len(highs) >= 20 else 0
    net_move = abs(c - closes[-20]) / c * 100 if c and len(closes) >= 20 else 0
    
    # Critérios de Lateralização (Relaxamento V6.9)
    # Aumentamos a tolerância para evitar o bloqueio precoce por "Mercado Neutro"
    medias_comprimidas = abs(m50 - m200) / m200 < 0.008 and abs(m10 - m50) / m50 < 0.008 if mm200 else abs(m10 - m50) / m50 < 0.008
    sem_expansao = dist_10_21 < 0.08 and net_move < max(0.40, recent_range * 0.25)
    is_lateral = medias_comprimidas and sem_expansao

    
    # Pontuação Parcial para bônus de Score
    tendencia_parcial = 0
    if c > m200: tendencia_parcial += 2
    if m10 > m21: tendencia_parcial += 2
    if m21 > m50: tendencia_parcial += 1
    if c > m50: tendencia_parcial += 2
    if slope10 > 0 and slope21 > 0: tendencia_parcial += 1
    
    # Classificação Detalhada
    long_emergente = m10 > m21 and slope10 > 0.02 and slope21 >= 0 and c > m21 and net_move >= 0.25
    short_emergente = m10 < m21 and slope10 < -0.02 and slope21 <= 0 and c < m21 and net_move >= 0.25

    # V11: Classificação forçada para evitar NEUTRA
    if not is_lateral:
        # Tendência forte por EMA e alinhamento
        if c > m200 and m10 > m21 > m50:
            nome = "TENDÊNCIA FORTE"
            direcao = "long"
        elif c > m200 and m10 > m21:
            nome = "TENDÊNCIA MODERADA"
            direcao = "long"
        elif long_emergente:
            nome = "TENDÊNCIA EM DESENVOLVIMENTO"
            direcao = "long"
        # Tendência de Baixa
        elif c < m200 and m10 < m21 < m50:
            nome = "TENDÊNCIA FORTE"
            direcao = "short"
        elif c < m200 and m10 < m21:
            nome = "TENDÊNCIA MODERADA"
            direcao = "short"
        elif short_emergente:
            nome = "TENDÊNCIA EM DESENVOLVIMENTO"
            direcao = "short"
        else:
            # Em vez de NEUTRA, infere direção pelas EMAs
            nome = "TENDÊNCIA FRACA"
            direcao = "long" if c > m50 else "short"
    else:
        # Lateral com forte inclinação vira tendência
        if abs(slope10) > 0.10:
            nome = "TENDÊNCIA EM DESENVOLVIMENTO"
            direcao = "long" if slope10 > 0 else "short"
        else:
            nome = "LATERAL"
            direcao = "lateral"

        tendencia_parcial = 0 if nome == "TRANSIÇÃO" else tendencia_parcial

    return {
        "TENDENCIA": nome,
        "DIRECAO": direcao,
        "TENDENCIA_PARCIAL_SCORE": tendencia_parcial * 2,
        "EMA_10": m10,
        "EMA_21": m21,
        "EMA_50": m50,
        "EMA_200": m200,
        "EMA10_SLOPE": slope10,
        "EMA21_SLOPE": slope21,
        "EMA50_SLOPE": slope50,
        "EMA10_21_DIST": dist_10_21,
        "RANGE_20": recent_range,
        "NET_MOVE_20": net_move,
        "EMA_ALINHADA": (m10 > m21 > m50 and (not mm200 or m50 > m200)) or (m10 < m21 < m50 and (not mm200 or m50 < m200)),
        "KALMAN_DIRECAO": kalman_direction(closes)
    }
