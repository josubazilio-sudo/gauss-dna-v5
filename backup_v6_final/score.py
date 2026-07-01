"""SINAIS TOP V7 — Score Ponderado (0–100)"""

from flex.config import (
    SCORE_OURO_MIN, SCORE_PRATA_MIN, SCORE_BRONZE_MIN, SCORE_OURO_SUPREMO_MIN,
    PESO_TENDENCIA, PESO_SMART_MONEY, PESO_FLUXO, 
    PESO_ESTRUTURA, PESO_VOLUME, PESO_VOLATILIDADE,
    CONFIANCA_BRONZE, CONFIANCA_PRATA, CONFIANCA_OURO, CONFIANCA_OURO_SUPREMO,
    ALLOW_KALMAN_SIDEWAYS_BRONZE, ALLOW_KALMAN_SIDEWAYS_PRATA,
    ALLOW_KALMAN_SIDEWAYS_OURO, ALLOW_KALMAN_SIDEWAYS_SUPREMO,
    HA_CONTRARIO_PENALIDADE,
)
from flex.config import ADX_OURO_SUPREMO, ADX_OURO, ADX_PRATA, ADX_BRONZE
from flex.config import RVOL_OURO_SUPREMO, RVOL_OURO, RVOL_PRATA, RVOL_BRONZE


def _score_kalman_by_direction(kalman_dir, direction):
    k = kalman_dir if isinstance(kalman_dir, str) else "SIDE"
    if direction == "long":
        if k == "UP": return 5
        if k == "SIDE": return -1
        return -5
    else:
        if k == "DOWN": return 5
        if k == "SIDE": return -1
        return -5

def _score_fluxo(flow_data, direction):
    delta = flow_data.get("DELTA", 0)
    if (direction == "long" and delta > 0.05) or (direction == "short" and delta < -0.05): return 6
    if (direction == "long" and delta > 0.01) or (direction == "short" and delta < -0.01): return 3
    if (direction == "long" and delta < -0.05) or (direction == "short" and delta > 0.05): return -3 # Forte contra
    return 0


def _timing_penalty(timing_index):
    if timing_index is None:
        return 0
    if timing_index >= 86:
        return 10
    if timing_index >= 71:
        return 5
    if timing_index >= 61:
        return 0
    if timing_index >= 41:
        return -10
    return -15  # penalidade pesada em vez de bloqueio


def _score_rvol(rvol):
    if rvol < 0.50: return -99 # Bloqueio
    if rvol < 0.70: return -6
    if rvol < 0.80: return -2
    if rvol < 0.90: return 0
    if rvol < 1.00: return 2
    if rvol < 1.20: return 4
    return 6
    return 8

def _score_liquidez(vol_24h):
    if vol_24h < 1_000_000: return -99 # Bloqueio
    if vol_24h < 3_000_000: return -4
    if vol_24h < 5_000_000: return -2
    if vol_24h < 7_000_000: return 1
    if vol_24h < 10_000_000: return 3
    if vol_24h < 15_000_000: return 5
    if vol_24h < 20_000_000: return 6
    return 8


def _score_adx(adx, adx_history=None):
    """Score ADX com detecção de aceleração/enfraquecimento."""
    if adx < 15: return -6
    if adx < 18: return -3
    if adx < 22: return 2
    if adx < 28: return 5
    return 8


def _score_rsi(rsi, direction, rsi_history=None):
    from flex.config import LONG_RSI_MIN, LONG_RSI_MAX, SHORT_RSI_MIN, SHORT_RSI_MAX
    if direction == "long":
        if LONG_RSI_MIN <= rsi <= LONG_RSI_MAX: return 7
        if rsi > 85: return -6
        if rsi > 82: return -4
        if rsi > 75: return -2
        return 0
    else:
        if SHORT_RSI_MIN <= rsi <= SHORT_RSI_MAX: return 7
        if rsi < 15: return -6
        if rsi < 18: return -4
        if rsi < 25: return -2
        return 0


def _score_fluxo(flow_data, direction):
    delta = flow_data.get("DELTA", 0)
    vol_cres = flow_data.get("VOLUME_CRESCENTE", False)
    rvol = flow_data.get("RVOL", 0)
    absorcao = flow_data.get("ABSORCAO", False)

    if absorcao:
        return -5

    contra = (direction == "long" and delta < -0.1) or (direction == "short" and delta > 0.1)
    if contra:
        return -12
    alinhado = (direction == "long" and delta > 0.01) or (direction == "short" and delta < -0.01)
    if not alinhado:
        return 0
    if vol_cres and rvol > 2.0:
        return 12
    if vol_cres:
        return 10
    if rvol > 1.5:
        return 5
    return 0


def _score_velas(velas_fortes):
    if velas_fortes == 0:
        return -5
    if velas_fortes == 1:
        return 2
    if velas_fortes == 2:
        return 6
    if velas_fortes == 3:
        return 9
    return 11


def _score_follow_through(follow_through_pct):
    if follow_through_pct > 8:
        return 8
    if follow_through_pct >= 5:
        return 5
    if follow_through_pct >= 2:
        return 2
    if follow_through_pct >= 0.5:
        return 1
    return -2


def _calcular_bonus_confluencia(adx, flow_data, smc_data, follow_through_pct, direction_1h, direction_4h, direction_30m):
    """Bônus para confluência institucional."""
    bonus = 0
    if smc_data.get("LIQUIDITY_SWEEP"): bonus += 4
    if smc_data.get("BOS") or smc_data.get("CHOCH"): bonus += 4
    if smc_data.get("ORDER_BLOCK"): bonus += 3
    if smc_data.get("FVG"): bonus += 3
    if flow_data.get("VOLUME_CRESCENTE"): bonus += 4
    if follow_through_pct and follow_through_pct > 5: bonus += 5
    if direction_1h and direction_1h == direction_30m: bonus += 2
    if direction_4h and direction_4h == direction_30m: bonus += 2
    return min(bonus, 15)


def _score_atr(market_data):
    if market_data.get("ATR_COMPRESSAO"):
        return -5
    atr_ratio = market_data.get("ATR_RATIO", 1.0)
    if atr_ratio < 0.7:
        return -2
    if atr_ratio < 1.2:
        return 5
    return 8


def _score_alinhamento(trend_data, direction):
    m10 = trend_data.get("EMA_10")
    m21 = trend_data.get("EMA_21")
    m50 = trend_data.get("EMA_50")
    m200 = trend_data.get("EMA_200")
    if None in (m10, m21, m50):
        return 0

    if direction == "long":
        pairs = [m10 > m21, m21 > m50]
        if m200 is not None:
            pairs.append(m50 > m200)
        inv = [m10 < m21, m21 < m50]
        if m200 is not None:
            inv.append(m50 < m200)
        if all(inv):
            return -5
    else:
        pairs = [m10 < m21, m21 < m50]
        if m200 is not None:
            pairs.append(m50 < m200)
        inv = [m10 > m21, m21 > m50]
        if m200 is not None:
            inv.append(m50 > m200)
        if all(inv):
            return -5

    if all(pairs):
        return 15
    if sum(pairs) >= len(pairs) - 1:
        return 8
    return 0


def _score_rompimento(smc_data):
    bos = smc_data.get("BOS", False)
    choch = smc_data.get("CHOCH", False)
    retest = smc_data.get("RETESTE", False)
    if bos and choch:
        return 15
    if bos and retest:
        return 12
    if bos:
        return 8
    if choch:
        return 5
    return 0


def mapear_score_final(raw):
    return max(0, min(100, round(raw)))


def _calcular_score_core(trend_data, flow_data, momentum_data, smc_data,
                          market_data, velas_fortes, follow_through_pct,
                          volume_24h, spread, btc_eth_bonus, direction, kalman_dir):
    score = 0
    score += _score_velas(velas_fortes)
    score += _score_follow_through(follow_through_pct)
    score += _score_atr(market_data)
    score += _score_alinhamento(trend_data, direction)
    score += _score_rompimento(smc_data)

    # Kalman lateral
    if kalman_dir == "SIDE":
        score -= 10
    
    # Fluxo Forte (+8) / Fraco (-8)
    delta = flow_data.get("DELTA", 0)
    if (direction == "long" and delta > 0.05) or (direction == "short" and delta < -0.05):
        score += 8
    elif (direction == "long" and delta < -0.02) or (direction == "short" and delta > 0.02):
        score -= 8

    # MM50 / MM200 alignment
    ema50 = trend_data.get("EMA_50")
    ema200 = trend_data.get("EMA_200")
    if ema50 and ema200:
        if (direction == "long" and ema50 > ema200) or (direction == "short" and ema50 < ema200):
            score += 6
        elif (direction == "long" and ema50 < ema200) or (direction == "short" and ema50 > ema200):
            score -= 6

    if volume_24h is not None:
        if volume_24h >= 50_000_000:
            score += 5
        elif volume_24h >= 10_000_000:
            score += 3
        elif volume_24h >= 5_000_000:
            score += 1
        if volume_24h < 500_000:
            score += 0
    if spread is not None:
        if spread <= 0.05:
            score += 2
        elif spread <= 0.12:
            score += 1
        if spread > 0.35:
            score -= 2
    if btc_eth_bonus:
        score += btc_eth_bonus

    preco = flow_data.get("PRECO", 0)
    ema50 = trend_data.get("EMA_50")
    ema200 = trend_data.get("EMA_200")
    if preco > 0 and ema50 is not None:
        if (direction == "long" and preco < ema50) or (direction == "short" and preco > ema50):
            score -= 8
    if preco > 0 and ema200 is not None:
        if (direction == "long" and preco < ema200) or (direction == "short" and preco > ema200):
            score -= 12

    tend = trend_data.get("TENDENCIA", "neutra")
    if (direction == "long" and tend in ("baixa", "baixa_moderada")) or \
       (direction == "short" and tend in ("alta", "alta_moderada")):
        score -= 8

    # Consolidation bonus: neutra market but strong internal momentum = imminent breakout
    if tend == "neutra":
        adx = momentum_data.get("ADX", 0)
        rvol = flow_data.get("RVOL", 0)
        if adx >= 25 and rvol >= 1.2:
            score += 20
        elif adx >= 20:
            score += 12
        elif rvol >= 1.2:
            score += 8
        elif adx >= 15:
            score += 4

    return max(0, score)


def _verificar_multi_timeframe(direction_30m, direction_1h, direction_4h=None):
    """Multi-timeframe: penaliza em vez de bloquear.
    Nunca bloqueia sozinho — o score final decide.
    """
    penalidade = 0
    if direction_30m is None or direction_1h is None:
        return {"penalidade": 0, "bloquear": False}
    if direction_30m != direction_1h:
        penalidade -= 10
    if direction_4h is not None and direction_4h != direction_30m:
        penalidade -= 8
    return {"penalidade": penalidade, "bloquear": False}


def calcular_confianca(score, classificacao):
    if classificacao == "OURO_SUPREMO":
        return max(score, CONFIANCA_OURO_SUPREMO)
    if classificacao == "OURO":
        return max(score, CONFIANCA_OURO)
    if classificacao == "PRATA":
        return max(score, CONFIANCA_PRATA)
    return max(score, CONFIANCA_BRONZE)


def validar_sinal_matematico(symbol, direction, entry, stop, tp1, tp2, tp3, r_pct, funding):
    """Auditoria automática antes do envio."""
    try:
        if any(v is None or v <= 0 for v in [entry, stop, tp1]):
            return False, "Valores zerados ou None"
        if direction == "LONG":
            if not (stop < entry < tp1 < tp2): return False, "Consistência Long inválida"
        else:
            if not (tp2 < tp1 < entry < stop): return False, "Consistência Short inválida"
        
        if abs(funding) > 0.05: return False, f"Funding extremo: {funding}"
        if r_pct > 0.10: return False, "Risco percentual excede limite 10%"
        
        return True, "OK"
    except Exception as e:
        return False, str(e)

def calcular_conviction_score(flow_data, adx, rvol, smc_data, momentum_data, kalman_dir):
    """Calcula score de convicção independente (0-100)."""
    score = 0
    # Fluxo
    if flow_data.get("FLUXO_TIPO") == "forte": score += 20
    # ADX
    if adx >= 35: score += 15
    # RVOL
    if rvol >= 1.3: score += 15
    # Estrutura (SMC)
    if smc_data.get("BOS") or smc_data.get("CHOCH"): score += 15
    # Momentum (HA/Velas)
    if momentum_data.get("HA_BULL") or momentum_data.get("HA_BEAR"): score += 15
    # Kalman
    if kalman_dir in ("UP", "DOWN"): score += 10
    # Liquidez
    if smc_data.get("LIQUIDITY_SWEEP"): score += 10
    return min(score, 100)


def _calc_rsi_series(closes, period=14):
    """Retorna série de RSI para os closes disponíveis."""
    if len(closes) < period + 1:
        return []
    vals = []
    for i in range(period, len(closes)):
        gains, losses = [], []
        for j in range(i - period + 1, i + 1):
            diff = closes[j] - closes[j - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_g = sum(gains) / period
        avg_l = sum(losses) / period
        vals.append(100 - (100 / (1 + avg_g / avg_l)) if avg_l > 0 else 100)
    return vals


def _calc_adx_series(highs, lows, closes, period=14):
    """Retorna série de ADX para detectar aceleração/enfraquecimento."""
    if len(highs) < period * 2:
        return []
    vals = []
    for end in range(period * 2, len(closes) + 1):
        h_slice = highs[end - period:end]
        l_slice = lows[end - period:end]
        c_slice = closes[end - period:end]
        tr_list, plus_dm, minus_dm = [], [], []
        for i in range(1, len(c_slice)):
            tr = max(h_slice[i] - l_slice[i], abs(h_slice[i] - c_slice[i - 1]), abs(l_slice[i] - c_slice[i - 1]))
            tr_list.append(tr)
            up_move = h_slice[i] - h_slice[i - 1]
            down_move = l_slice[i - 1] - l_slice[i]
            plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
            minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)
        atr = sum(tr_list[-period:]) / period if tr_list else 1
        apd = sum(plus_dm[-period:]) / period
        amd = sum(minus_dm[-period:]) / period
        pdi = (apd / atr) * 100 if atr > 0 else 0
        mdi = (amd / atr) * 100 if atr > 0 else 0
        dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
        vals.append(dx)
    return vals


def _calcular_bonus_setups(trend_data, flow_data, candles_op, direction, kalman_dir):
    """Bônus de pontuação para setups fortes (Pullback, MACD Recovery, EMA10/21, Volume, Kalman)."""
    total = 0
    bonuses = []
    closes = [c[4] for c in candles_op] if candles_op else []
    preco = closes[-1] if closes else 0

    # 1. Kalman alinhado
    if _kalman_alinhado(kalman_dir, direction):
        total += 5
        bonuses.append("kalman_alinhado")

    # 2. Volume crescente
    if flow_data.get("VOLUME_CRESCENTE", False):
        total += 5
        bonuses.append("volume_crescente")

    # 3. Cruzamento EMA10/21
    ema10 = trend_data.get("EMA_10")
    ema21 = trend_data.get("EMA_21")
    if ema10 and ema21 and len(closes) >= 3:
        if (direction == "long" and ema10 > ema21) or (direction == "short" and ema10 < ema21):
            total += 5
            bonuses.append("cruzamento_ema10_21")

    # 4. MACD Recovery
    if len(closes) >= 35:
        macd_line, sig_line = _calc_macd_array(closes)
        if len(macd_line) >= 3 and len(sig_line) >= 3:
            macd_curr = macd_line[-1]
            macd_prev = macd_line[-2]
            sig_curr = sig_line[-1]
            if (direction == "long" and macd_prev <= sig_curr and macd_curr > sig_curr) or \
               (direction == "short" and macd_prev >= sig_curr and macd_curr < sig_curr):
                total += 5
                bonuses.append("macd_recovery")

    # 5. Pullback confirmado (preço retraiu pra EMA21 e rebateu)
    if preco > 0 and ema21 and ema21 > 0 and len(closes) >= 5:
        dists = [abs(c - ema21) / ema21 for c in closes[-5:]]
        dist_min = min(dists)
        dist_atual = dists[-1]
        if dist_min < 0.02 and dist_atual > dist_min * 1.2:
            total += 5
            bonuses.append("pullback_confirmado")

    return total, bonuses


def calcular_score(trend_data, flow_data, momentum_data, smc_data,
                   market_data, kalman_dir, direction, velas_fortes,
                   follow_through_pct=0, volume_24h=None, spread=None,
                   timing_index=None, btc_eth_bonus=0,
                   direction_1h=None, direction_4h=None,
                   candles_op=None, regime_name="TRANSICAO"):
    
    from flex.institutional_regime import get_regime_profile
    profile = get_regime_profile(regime_name)
    rvol = flow_data.get("RVOL", 1.0)
    adx = momentum_data.get("ADX", 0)
    rsi = momentum_data.get("RSI", 50)
    delta = flow_data.get("DELTA", 0)
    fluxo_a_favor = (direction == "long" and delta > 0) or (direction == "short" and delta < 0)
    kalman_alinhado = (direction == "long" and kalman_dir == "UP") or (direction == "short" and kalman_dir == "DOWN")
    kalman_side = kalman_dir == "SIDE"

    trend_score = 0
    if trend_data.get("DIRECAO") == direction:
        trend_score += 10
    tendencia_nome = trend_data.get("TENDENCIA", "").lower()
    if "muito forte" in tendencia_nome:
        trend_score += 6
    elif "moderada" in tendencia_nome or "emergente" in tendencia_nome:
        trend_score += 4
    if trend_data.get("EMA10_SLOPE", 0) > 0 and direction == "long" or trend_data.get("EMA10_SLOPE", 0) < 0 and direction == "short":
        trend_score += 2
    if direction_1h == direction:
        trend_score += 2
    trend_score = min(trend_score, 20)

    momentum_score = 0
    if adx >= 35:
        momentum_score += 8
    elif adx >= 28:
        momentum_score += 6
    elif adx >= 22:
        momentum_score += 4
    elif adx >= 18:
        momentum_score += 2
    if (direction == "long" and 45 <= rsi <= 68) or (direction == "short" and 32 <= rsi <= 55):
        momentum_score += 5
    elif 30 <= rsi <= 72:
        momentum_score += 2
    if timing_index and timing_index >= 70:
        momentum_score += 2
    momentum_score = min(momentum_score, 15)

    smc_score = 0
    if smc_data.get("LIQUIDITY_SWEEP"):
        smc_score += 6
    if smc_data.get("BOS"):
        smc_score += 5
    if smc_data.get("CHOCH"):
        smc_score += 4
    if smc_data.get("ORDER_BLOCK"):
        smc_score += 4
    if smc_data.get("FVG"):
        smc_score += 3
    if smc_data.get("RETESTE"):
        smc_score += 3
    if smc_data.get("ESTRUTURA_OK"):
        smc_score += 3
    smc_score = min(smc_score, 25)

    flow_score = 0
    if fluxo_a_favor:
        flow_score += 5
    if flow_data.get("VOLUME_CRESCENTE"):
        flow_score += 4
    rvol_min = 1.0 * profile["rvol_mult"]
    if rvol >= max(1.5, rvol_min):
        flow_score += 4
    elif rvol >= max(1.0, rvol_min * 0.9):
        flow_score += 3
    elif rvol >= 0.75:
        flow_score += 1
    if abs(delta) >= 0.05:
        flow_score += 2
    flow_score = min(flow_score, 15)

    entry_score = 0
    if timing_index is not None:
        if 65 <= timing_index <= 85:
            entry_score += 8
        elif 55 <= timing_index <= 90:
            entry_score += 5
        elif timing_index > 90:
            entry_score += 1
    if smc_data.get("RETESTE") or smc_data.get("ORDER_BLOCK") or smc_data.get("FVG"):
        entry_score += 4
    if velas_fortes in (1, 2):
        entry_score += 3
    elif velas_fortes >= 3:
        entry_score += 1
    entry_score = min(entry_score, 15)

    risk_score = 0
    if volume_24h is None or volume_24h >= 5_000_000:
        risk_score += 3
    if spread is None or spread <= 0.30:
        risk_score += 2
    if not market_data.get("ATR_COMPRESSAO"):
        risk_score += 2
    if kalman_alinhado:
        risk_score += 3
    elif kalman_side:
        risk_score += 1
    risk_score = min(risk_score, 10)

    score_final = trend_score + momentum_score + smc_score + flow_score + entry_score + risk_score + btc_eth_bonus

    if smc_score < 8:
        score_final = min(score_final, 69)
    if trend_score < 8 and momentum_score < 8:
        score_final = min(score_final, 69)
    if not fluxo_a_favor:
        score_final = min(score_final, 69)
    if timing_index is not None and timing_index > 90:
        score_final = min(score_final, 84)

    score_final = max(0, min(100, round(score_final)))
    atr = momentum_data.get("ATR", 0)
    preco = flow_data.get("PRECO", 0)
    atr_pct = atr / preco if atr and preco else 0
    
    return {
        "score_total": score_final,
        "motivos": [],
        "aprovado": score_final >= 70,
        "rsi": rsi,
        "adx": adx,
        "rvol": rvol,
        "atr_pct": atr_pct,
        "rsi_raw": rsi,
        "fluxo_raw": flow_score,
        "kalman_raw": 1 if kalman_alinhado else 0,
        "timing_raw": timing_index or 0,
        "kalman_penalty": 0,
        "componentes": {
            "trend": trend_score,
            "momentum": momentum_score,
            "smart_money": smc_score,
            "flow_volume": flow_score,
            "entry_timing": entry_score,
            "risk": risk_score,
        },
        "bonus": [],
        "debug": {
            "detalhes": {"Trend": trend_score, "Momentum": momentum_score, "SMC": smc_score, "Flow": flow_score, "Entry": entry_score, "Risk": risk_score},
            "missing_points": 70 - score_final if score_final < 70 else 0
        }
    }


def calcular_timing_index(trend_data, flow_data, momentum_data, smc_data, candles_op, direction):
    closes = [c[4] for c in candles_op]
    highs = [c[2] for c in candles_op]
    lows = [c[3] for c in candles_op]
    volumes = [c[5] for c in candles_op]
    preco = closes[-1] if closes else 0

    score = 0

    ema21 = trend_data.get("EMA_21")
    if ema21 and ema21 > 0 and preco > 0:
        dist_ema21 = abs(preco - ema21) / preco * 100
        if dist_ema21 < 0.5:
            score += 25
        elif dist_ema21 < 1.0:
            score += 20
        elif dist_ema21 < 2.0:
            score += 12
        elif dist_ema21 < 3.0:
            score += 6
        else:
            score += 2

    rsi = momentum_data.get("RSI", 50)
    if 45 <= rsi <= 55:
        score += 20
    elif 40 <= rsi <= 60:
        score += 15
    elif 35 <= rsi <= 65:
        score += 10
    elif 30 <= rsi <= 70:
        score += 5
    else:
        score += 1

    atr = momentum_data.get("ATR", 0)
    if atr > 0 and len(highs) >= 1 and len(lows) >= 1:
        candle_range = highs[-1] - lows[-1]
        extension = candle_range / atr
        if 0.5 <= extension <= 1.5:
            score += 20
        elif extension < 0.5:
            score += 8
        elif extension <= 2.0:
            score += 12
        elif extension <= 3.0:
            score += 5
        else:
            score += 1

    if len(highs) >= 10 and len(lows) >= 10 and preco > 0:
        recent_high = max(highs[-10:])
        recent_low = min(lows[-10:])
        dist_to_high = (recent_high - preco) / preco * 100
        dist_to_low = (preco - recent_low) / preco * 100
        if direction == "long":
            if dist_to_low < 0.5:
                score += 15
            elif dist_to_high < 0.5:
                score += 5
            else:
                score += 10
        else:
            if dist_to_high < 0.5:
                score += 15
            elif dist_to_low < 0.5:
                score += 5
            else:
                score += 10

    if len(closes) >= 14 and len(volumes) >= 14 and preco > 0:
        vwap_num = 0
        vwap_den = 0
        for j in range(-14, 0):
            tp = (highs[j] + lows[j] + closes[j]) / 3
            vwap_num += tp * volumes[j]
            vwap_den += volumes[j]
        vwap = vwap_num / vwap_den if vwap_den > 0 else preco
        if direction == "long":
            if preco > vwap:
                score += 15
            elif preco > vwap * 0.98:
                score += 8
            else:
                score += 3
        else:
            if preco < vwap:
                score += 15
            elif preco < vwap * 1.02:
                score += 8
            else:
                score += 3

    return min(score, 100)


def calcular_exaustao(trend_data, flow_data, momentum_data, candles_op, direction):
    return calcular_exaustao_v7(trend_data, flow_data, momentum_data, candles_op, direction)


def _calc_rsi_series(closes, period=14):
    """Retorna série de RSI para os closes disponíveis."""
    if len(closes) < period + 1:
        return []
    vals = []
    for i in range(period, len(closes)):
        gains, losses = [], []
        for j in range(i - period + 1, i + 1):
            diff = closes[j] - closes[j - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_g = sum(gains) / period
        avg_l = sum(losses) / period
        vals.append(100 - (100 / (1 + avg_g / avg_l)) if avg_l > 0 else 100)
    return vals

_calc_rsi_array = _calc_rsi_series


def _calc_macd_array(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return [], []
    ema_f = _ema_series(closes, fast)
    ema_s = _ema_series(closes, slow)
    macd_line = [ema_f[i] - ema_s[i] for i in range(min(len(ema_f), len(ema_s)))]
    sig_line = _ema_series(macd_line, signal) if len(macd_line) >= signal else []
    return macd_line, sig_line


def _ema_series(data, period):
    if len(data) < period:
        return []
    k = 2 / (period + 1)
    result = [sum(data[:period]) / period]
    for price in data[period:]:
        result.append(price * k + result[-1] * (1 - k))
    return result


def _find_divergence(prices, indicator, direction):
    if len(prices) < 14 or len(indicator) < 14:
        return False
    offset = len(indicator) - len(prices)
    if offset < 0:
        return False
    ind = indicator[offset:]

    # Find swing highs (peaks) in last 14 candles
    peaks_price, peaks_ind = [], []
    valleys_price, valleys_ind = [], []
    lookback = min(14, len(prices) - 2)
    start = len(prices) - lookback
    for i in range(start, len(prices)):
        if i < 1 or i >= len(prices) - 1:
            continue
        if prices[i] > prices[i - 1] and prices[i] > prices[i + 1]:
            peaks_price.append((i, prices[i]))
            peaks_ind.append((i, ind[i]))
        if prices[i] < prices[i - 1] and prices[i] < prices[i + 1]:
            valleys_price.append((i, prices[i]))
            valleys_ind.append((i, ind[i]))

    if direction == "long":
        # Bearish divergence: price higher high, RSI/MACD lower high
        if len(peaks_price) >= 2:
            p2, p1 = peaks_price[-2], peaks_price[-1]
            i2, i1 = peaks_ind[-2], peaks_ind[-1]
            if p1[1] > p2[1] and i1[1] < i2[1]:
                return True
    else:
        # Bullish divergence: price lower low, RSI/MACD higher low
        if len(valleys_price) >= 2:
            v2, v1 = valleys_price[-2], valleys_price[-1]
            i2, i1 = valleys_ind[-2], valleys_ind[-1]
            if v1[1] < v2[1] and i1[1] > i2[1]:
                return True
    return False


def calcular_exaustao_v7(trend_data, flow_data, momentum_data, candles_op, direction):
    closes = [c[4] for c in candles_op]
    highs = [c[2] for c in candles_op]
    lows = [c[3] for c in candles_op]
    volumes = [c[5] for c in candles_op]
    opens = [c[1] for c in candles_op]
    preco = closes[-1] if closes else 0

    ex = 0
    rsi = momentum_data.get("RSI", 50)
    atr = momentum_data.get("ATR", 0)
    ema21 = trend_data.get("EMA_21")
    fundos = []

    # RSI extremo
    if direction == "long":
        if rsi > 78:
            ex += 25
            fundos.append("rsi_extremo_long")
        elif rsi > 72:
            ex += 15
            fundos.append("rsi_alto")
    else:
        if rsi < 22:
            ex += 25
            fundos.append("rsi_extremo_short")
        elif rsi < 28:
            ex += 15
            fundos.append("rsi_baixo")

    # Distância da EMA21
    if ema21 and ema21 > 0 and preco > 0:
        dist_pct = abs(preco - ema21) / ema21 * 100
        if dist_pct > 3.0:
            ex += 15
            fundos.append("ema21_distante")
        elif dist_pct > 2.0:
            ex += 8
            fundos.append("ema21_afastado")

    # Distância da VWAP
    if len(closes) >= 14 and preco > 0:
        vwap_num = sum((highs[j] + lows[j] + closes[j]) / 3 * volumes[j] for j in range(-14, 0) if j < 0)
        vwap_den = sum(volumes[j] for j in range(-14, 0) if j < 0)
        if vwap_den > 0:
            vwap = vwap_num / vwap_den
            dist_vwap = abs(preco - vwap) / vwap * 100
            if dist_vwap > 5.0:
                ex += 10
                fundos.append("vwap_distante")

    # ATR expandido
    if atr > 0 and len(highs) >= 1 and len(lows) >= 1:
        candle_range = highs[-1] - lows[-1]
        extension = candle_range / atr
        if extension > 2.5:
            ex += 10
            fundos.append("atr_expandido")

    # Sequência de velas consecutivas
    cons = 0
    for i in range(-1, -min(len(closes), 8), -1):
        if direction == "long" and closes[i] > closes[i - 1]:
            cons += 1
        elif direction == "short" and closes[i] < closes[i - 1]:
            cons += 1
        else:
            break
    if cons >= 5:
        ex += 15
        fundos.append("sequencia_longa")
    elif cons >= 3:
        ex += 8
        fundos.append("sequencia_media")

    # Divergência RSI
    if len(closes) >= 20:
        rsi_arr = _calc_rsi_array(closes, 14)
        if _find_divergence(closes, rsi_arr, direction):
            ex += 15
            fundos.append("divergencia_rsi")

    # Divergência MACD
    if len(closes) >= 35:
        macd_line, _ = _calc_macd_array(closes, 12, 26, 9)
        if _find_divergence(closes, macd_line, direction):
            ex += 15
            fundos.append("divergencia_macd")

    # Exaustão: penalidade progressiva, nunca bloqueio
    if ex >= 60:
        return {"penalidade": -40, "bloquear": False, "motivos": fundos, "ex_score": ex}
    if ex >= 50:
        return {"penalidade": -30, "bloquear": False, "motivos": fundos, "ex_score": ex}
    if ex >= 40:
        return {"penalidade": -20, "bloquear": False, "motivos": fundos, "ex_score": ex}
    if ex >= 20:
        return {"penalidade": -15, "bloquear": False, "motivos": fundos, "ex_score": ex}
    return {"penalidade": 0, "bloquear": False, "motivos": fundos, "ex_score": ex}


def calcular_mult_entrada(score, classificacao):
    if classificacao == "OURO_SUPREMO":
        return 2.0 + (score - SCORE_OURO_SUPREMO_MIN) / (100 - SCORE_OURO_SUPREMO_MIN)
    if classificacao == "OURO":
        return 1.5 + (score - SCORE_OURO_MIN) / (SCORE_OURO_SUPREMO_MIN - SCORE_OURO_MIN) * 0.5
    if classificacao == "PRATA":
        return 1.0 + (score - SCORE_PRATA_MIN) / (SCORE_OURO_MIN - SCORE_PRATA_MIN) * 0.5
    return 0.5 + (score - SCORE_BRONZE_MIN) / (SCORE_PRATA_MIN - SCORE_BRONZE_MIN) * 0.5


LEVERAGE_TIERS = [5, 7, 9, 11, 13, 15, 18, 20]


def _nivel_para_alavancagem(nivel):
    return LEVERAGE_TIERS[max(0, min(7, nivel))]


def _nivel_base_por_score(score):
    if score >= 98: return 7
    if score >= 95: return 6
    if score >= 90: return 5
    if score >= 85: return 4
    if score >= 80: return 3
    if score >= 75: return 2
    if score >= 70: return 1
    return 0


def _ajuste_por_stop(stop_pct):
    if stop_pct < 1.00:
        return 1
    if stop_pct > 2.00:
        return -2
    return 0


def _ajuste_por_adx(adx):
    if adx >= 40:
        return 1
    if adx < 25:
        return -2
    return 0


def _ajuste_por_rvol(rvol):
    if rvol >= 1.50:
        return 1
    if rvol < 1.00:
        return -1
    return 0


def calcular_alavancagem_dinamica(score, stop_pct, adx, rvol):
    nivel = _nivel_base_por_score(score)
    ajustes = 0
    ajustes += _ajuste_por_stop(stop_pct)
    ajustes += _ajuste_por_adx(adx)
    ajustes += _ajuste_por_rvol(rvol)
    return round(_nivel_para_alavancagem(nivel + ajustes))


def calcular_alavancagem(score, classificacao, stop_pct=0, adx=0, rvol=0):
    return calcular_alavancagem_dinamica(score, stop_pct, adx, rvol)


def _leverage_from_score(score):
    return calcular_alavancagem_dinamica(score, stop_pct=0, adx=0, rvol=0)


def _calcular_rr_implied(stop_pct):
    """Calcula RR implícito: TP1 = 2x ATR, SL = 1x ATR → RR = 2:1."""
    from flex.config import TP1_ATR_MULT, SL_ATR_MULT
    if stop_pct <= 0 or SL_ATR_MULT <= 0:
        return 0
    return (TP1_ATR_MULT / SL_ATR_MULT)


def adjust_confidence(confianca, regime, direction):
    """Ajusta a confiança baseada no regime institucional."""
    if regime == "TENDENCIA_FORTE":
        return min(100, confianca + 5)
    if regime == "LATERAL_RUIDOSO":
        return max(0, confianca - 10)
    return confianca

def calcular_gestao_operacao(score, classificacao, adx, rvol, timing_index,
                             flow_data, direction, kalman_dir, stop_pct=0):
    timing = timing_index or 0
    kalman_alinhado = _kalman_alinhado(kalman_dir, direction.lower())
    fluxo_forte = _fluxo_forte(flow_data, direction.lower())
    alavancagem = calcular_alavancagem_dinamica(score, stop_pct, adx, rvol)

    # RR check: TP1/SL mínimo exigido
    rr_implied = _calcular_rr_implied(stop_pct)
    if rr_implied < 1.5:
        return {
            "perfil": "RR_INSUFICIENTE",
            "risco_pct": 0,
            "alavancagem": 1,
            "mult_entrada": 0,
            "rr": rr_implied,
        }

    if classificacao == "OURO_SUPREMO":
        return {
            "perfil": "OURO SUPREMO",
            "risco_pct": 0.09,
            "alavancagem": alavancagem,
            "mult_entrada": 1.0,
            "rr": rr_implied,
        }

    if classificacao == "OURO":
        return {
            "perfil": "OURO",
            "risco_pct": 0.07,
            "alavancagem": alavancagem,
            "mult_entrada": 1.0,
            "rr": rr_implied,
        }

    if classificacao == "PRATA":
        return {
            "perfil": "PRATA",
            "risco_pct": 0.05,
            "alavancagem": alavancagem,
            "mult_entrada": 1.0,
            "rr": rr_implied,
        }

    return {
        "perfil": "BRONZE",
        "risco_pct": 0.03,
        "alavancagem": alavancagem,
        "mult_entrada": 1.0,
        "rr": rr_implied,
    }


REQUISITOS_CATEGORIA = {
    "OURO_SUPREMO": {"score": SCORE_OURO_SUPREMO_MIN, "adx": ADX_OURO_SUPREMO, "rvol": RVOL_OURO_SUPREMO, "timing": 75},
    "OURO":         {"score": SCORE_OURO_MIN,         "adx": ADX_OURO,         "rvol": RVOL_OURO,         "timing": 65},
    "PRATA":        {"score": SCORE_PRATA_MIN,        "adx": ADX_PRATA,        "rvol": RVOL_PRATA,        "timing": 50},
    "BRONZE":       {"score": SCORE_BRONZE_MIN,       "adx": ADX_BRONZE,       "rvol": RVOL_BRONZE,       "timing": 60},
}


def _kalman_alinhado(kalman_dir, direction):
    k = kalman_dir if isinstance(kalman_dir, str) else "SIDE"
    return (direction == "long" and k == "UP") or (direction == "short" and k == "DOWN")


def _fluxo_forte(flow_data, direction):
    delta = flow_data.get("DELTA", 0)
    vol_cres = flow_data.get("VOLUME_CRESCENTE", False)
    return vol_cres and ((direction == "long" and delta > 0) or (direction == "short" and delta < 0))


def _fluxo_a_favor(flow_data, direction):
    delta = flow_data.get("DELTA", 0)
    return (direction == "long" and delta > 0) or (direction == "short" and delta < 0)


def _tendencia_confirmada(trend_data, direction):
    t = trend_data.get("TENDENCIA", "").lower()
    return (direction == "long" and "alta" in t) or (direction == "short" and "baixa" in t)


def calcular_penalidades(score, rsi, flow_data, direction, kalman_dir, trend_data):
    from flex.config import LONG_RSI_MIN, LONG_RSI_MAX, SHORT_RSI_MIN, SHORT_RSI_MAX
    kalman_str = kalman_dir if isinstance(kalman_dir, str) else "SIDE"
    total = 0
    motivos = []

    if direction == "long":
        faixa = (LONG_RSI_MIN, LONG_RSI_MAX)
    else:
        faixa = (SHORT_RSI_MIN, SHORT_RSI_MAX)

    if not (faixa[0] <= rsi <= faixa[1]):
        total += 8
        motivos.append("rsi_fora_faixa")

    return total, motivos


def _pode_tendencia_neutra(score, adx, rvol, fluxo_forte, kalman_alinhado, timing):
    return score >= 75 and adx >= 35 and rvol >= 1.50 and fluxo_forte and kalman_alinhado and (timing or 0) >= 75


def _pode_kalman_side(score, adx, rvol, timing):
    return score >= 75 and adx >= 35 and rvol >= 1.40 and (timing or 0) >= 75


def _ajustar_por_regime(r, follow_through_pct, nome):
    if follow_through_pct is None:
        return r
    if follow_through_pct < 2:
        ajuste_score = 10
        ajuste_timing = 10
    elif follow_through_pct < 5:
        ajuste_score = 5
        ajuste_timing = 5
    elif follow_through_pct < 8 and nome in ("OURO_SUPREMO", "OURO"):
        ajuste_score = 3
        ajuste_timing = 3
    else:
        ajuste_score = 0
        ajuste_timing = 0
    return {
        **r,
        "score": min(100, r["score"] + ajuste_score),
        "timing": min(100, r["timing"] + ajuste_timing),
    }


def is_structurally_valid(trend_data, flow_data, kalman_dir, direction):
    tendencia = trend_data.get("TENDENCIA", "").lower()
    if "neutra" in tendencia or "lateral" in tendencia:
        return False, "Tendencia Neutra"

    if (direction == "long" and "baixa" in tendencia) or (direction == "short" and "alta" in tendencia):
        return False, "Tendencia Contraria"

    if (direction == "long" and kalman_dir == "DOWN") or (direction == "short" and kalman_dir == "UP"):
        return False, "Kalman Divergente"

    delta = flow_data.get("DELTA", 0)
    if (direction == "long" and delta < 0) or (direction == "short" and delta > 0):
        return False, "Fluxo Contrario"
        
    return True, None

def classificar_por_requisitos(score, adx, rvol, timing, flow_data, direction,
                                kalman_dir, trend_data, velas_fortes, conviccao,
                                direction_1h=None, direction_4h=None,
                                follow_through_pct=None):
    valid, reason = is_structurally_valid(trend_data, flow_data, kalman_dir, direction)
    if not valid:
        return None, f"bloqueio_estrutural_{reason}"

    if score < 70:
        return None, f"score_baixo_{score}"

    fluxo_ok = _fluxo_a_favor(flow_data, direction)
    timing = timing or 0
    if not fluxo_ok:
        return None, "fluxo_sem_confirmacao"
    if timing < 55:
        return None, f"timing_baixo_{timing}"
    if adx < 18:
        return None, f"adx_baixo_{adx}"

    # Trava de Integridade do Arquiteto (Regras V6.6)
    # Se a convicção é baixa ou RVOL é crítico, a categoria nunca pode ser superior a Bronze
    if (conviccao < 60 or rvol < 0.8):
        return "BRONZE", "Rebaixado por inconsistência (Convicção/RVOL)"
    
    if score >= 90 and adx >= 25 and timing >= 65:
        return "OURO", None
    if score >= 80 and adx >= 20 and timing >= 60:
        return "PRATA", None
    if score >= 65 and adx >= 15 and timing >= 50:
        return "BRONZE", None
    return None, "requisitos_categoria"



def classificar(score_total, confianca=None):
    if confianca is None:
        confianca = score_total
    if score_total >= SCORE_OURO_MIN:
        return {"classificacao": "OURO", "emoji": "🥇", "qualidade": "EXCELENTE", "confianca": max(confianca, CONFIANCA_OURO)}
    if score_total >= SCORE_PRATA_MIN:
        return {"classificacao": "PRATA", "emoji": "🥈", "qualidade": "MUITO BOA", "confianca": max(confianca, CONFIANCA_PRATA)}
    if score_total >= SCORE_BRONZE_MIN:
        return {"classificacao": "BRONZE", "emoji": "🥉", "qualidade": "BOA", "confianca": max(confianca, CONFIANCA_BRONZE)}
    return None
