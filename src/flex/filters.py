"""SINAIS TOP V9.3 — Filtros e Bloqueios Institucionais"""

import logging

logger = logging.getLogger(__name__)


def check_alignment(trend_data, momentum_data, flow_data, kalman_dir, direction, adx):
    """
    Validação obrigatória de alinhamento.
    Retorna (True, None) se ok, (False, "MOTIVO") se bloqueado.
    """
    # 1. ADX (Força)
    if adx < 18:
        return False, "BLOQUEADO: ADX insuficiente"

    # Tendência neutra/lateral e Kalman contra são avaliados no score.
    # Eles não devem bloquear sozinhos um setup institucional com liquidez.

    # 2. Fluxo (Divergência)
    delta = flow_data.get("DELTA", 0)
    if (direction == "long" and delta < -0.05) or (direction == "short" and delta > 0.05):
        return False, "BLOQUEADO: Fluxo divergente"

    return True, None


def run_all(symbol, direction, trend_data, flow_data, momentum_data,
            smc_data, market_data, candles, kalman_dir,
            volume_24h=None, spread=None):
    
    motivos = []
    
    # Validar Liquidez
    if volume_24h is not None and volume_24h < 2_000_000:
        motivos.append("volume_muito_baixo")
        
    # Validar Alinhamento Institucional (Regras V9.1)
    adx = momentum_data.get("ADX", 0)
    ok, block_msg = check_alignment(trend_data, momentum_data, flow_data, kalman_dir, direction, adx)
    if not ok:
        motivos.append(block_msg)
        
    aprovado = len(motivos) == 0
    return aprovado, motivos, 0, 0


def validar_filtros_rigorosos(symbol, direction, trend, flow, momentum, smc,
                               candles_op, kalman_dir, volume_24h, timing_index,
                               conviction_score, score, preco,
                               market_quality_index=70):
    """
    V9.2: Filtros rigorosos de qualidade.
    Retorna (aprovado: bool, info: dict).
    info = {
        "resultados": {nome_filtro: bool, ...},
        "reprovados": [nomes_dos_filtros_reprovados],
        "detalhes": {nome_filtro: {"valor": x, "minimo": y}},
        "modo_desc": "RIGOROSO" | "MODERADO" | "PERMISSIVO"
    }
    """
    resultados = {}
    detalhes = {}

    closes = [c[4] for c in candles_op] if candles_op else []
    highs = [c[2] for c in candles_op] if candles_op else []
    lows = [c[3] for c in candles_op] if candles_op else []

    rvol = flow.get("RVOL", 0)
    adx = momentum.get("ADX", 0)
    rsi = momentum.get("RSI", 50)
    delta = flow.get("DELTA", 0)
    vol_cres = flow.get("VOLUME_CRESCENTE", False)

    # Modo baseado no Market Quality Index
    if market_quality_index >= 70:
        modo_desc = "RIGOROSO"
    elif market_quality_index >= 50:
        modo_desc = "MODERADO"
    else:
        modo_desc = "PERMISSIVO"

    # 1. RVOL mínimo
    rvol_min = 0.80 if modo_desc == "RIGOROSO" else (0.70 if modo_desc == "MODERADO" else 0.60)
    rvol_ok = rvol >= rvol_min
    resultados["rvol_minimo"] = rvol_ok
    detalhes["rvol_minimo"] = {"valor": round(rvol, 2), "minimo": rvol_min}

    # 2. ADX mínimo
    adx_min = 20 if modo_desc == "RIGOROSO" else (18 if modo_desc == "MODERADO" else 15)
    adx_ok = adx >= adx_min
    resultados["adx_minimo"] = adx_ok
    detalhes["adx_minimo"] = {"valor": round(adx, 1), "minimo": adx_min}

    # 3. Timing mínimo
    timing_min = 50 if modo_desc == "RIGOROSO" else (45 if modo_desc == "MODERADO" else 40)
    timing_ok = timing_index is not None and timing_index >= timing_min
    resultados["timing_minimo"] = timing_ok
    detalhes["timing_minimo"] = {"valor": timing_index or 0, "minimo": timing_min}

    # 4. Fluxo a favor (delta não pode ser fortemente contra)
    fluxo_contra = (direction == "long" and delta < -0.03) or (direction == "short" and delta > 0.03)
    fluxo_ok = not fluxo_contra
    resultados["fluxo_nao_contra"] = fluxo_ok
    detalhes["fluxo_nao_contra"] = {"valor": round(delta, 4), "minimo": -0.03 if direction == "long" else 0.03}

    # 5. Volume 24h mínimo
    vol_min = 2_000_000 if modo_desc == "RIGOROSO" else 1_000_000
    volume_ok = volume_24h is not None and volume_24h >= vol_min
    resultados["volume_24h_minimo"] = volume_ok
    detalhes["volume_24h_minimo"] = {"valor": volume_24h or 0, "minimo": vol_min}

    # 6. SMC Estrutural (pelo menos BOS ou CHoCH no modo rigoroso)
    smc_ok = True
    if modo_desc == "RIGOROSO":
        smc_ok = smc.get("BOS") or smc.get("CHOCH")
        resultados["smc_estrutural"] = smc_ok
        detalhes["smc_estrutural"] = {"valor": 1 if smc_ok else 0, "minimo": 1}

    # 7. RSI dentro de faixa aceitável (não extremo)
    if direction == "long":
        rsi_extremo = rsi > 80 or rsi < 30
    else:
        rsi_extremo = rsi < 20 or rsi > 70
    rsi_ok = not rsi_extremo
    resultados["rsi_nao_extremo"] = rsi_ok
    detalhes["rsi_nao_extremo"] = {"valor": round(rsi, 1), "minimo": 20, "maximo": 80 if direction == "long" else 70}

    # 8. Kalman não pode ser contra a direção
    kalman_contra = (direction == "long" and kalman_dir == "DOWN") or (direction == "short" and kalman_dir == "UP")
    kalman_ok = not kalman_contra
    resultados["kalman_nao_contra"] = kalman_ok
    detalhes["kalman_nao_contra"] = {"valor": kalman_dir or "NONE", "minimo": "qualquer exceto contra"}

    # Decisão final: contar reprovações conforme o modo
    reprovados = [k for k, v in resultados.items() if not v]

    if modo_desc == "RIGOROSO":
        aprovado = len(reprovados) == 0
    elif modo_desc == "MODERADO":
        aprovado = len(reprovados) <= 1
    else:
        aprovado = len(reprovados) <= 2

    return aprovado, {
        "resultados": resultados,
        "reprovados": reprovados,
        "detalhes": detalhes,
        "modo_desc": modo_desc,
    }


def detectar_zona_transicao(trend, momentum, flow, kalman_dir, candles_op, direction):
    """
    Detecta zona de transição (mercado indeciso entre tendências).
    Retorna (em_transicao, motivos, gravidade).
    gravidade: "leve" | "moderada" | "critica"
    """
    motivos = []
    gravidade = "leve"

    tendencia = trend.get("TENDENCIA", "").upper()
    rsi = momentum.get("RSI", 50)
    adx = momentum.get("ADX", 0)
    rvol = flow.get("RVOL", 0)
    delta = flow.get("DELTA", 0)
    ha_bull = momentum.get("HA_BULL", False)
    ha_bear = momentum.get("HA_BEAR", False)
    closes = [c[4] for c in candles_op] if candles_op else []
    highs = [c[2] for c in candles_op] if candles_op else []
    lows = [c[3] for c in candles_op] if candles_op else []

    peso = 0

    # Tendência lateral ou fraca
    if "LATERAL" in tendencia:
        peso += 20
        motivos.append("tendencia_lateral")
    elif "FRACA" in tendencia:
        peso += 15
        motivos.append("tendencia_fraca")
    elif "DESENVOLVIMENTO" in tendencia:
        peso += 10
        motivos.append("tendencia_emergente")

    # ADX baixo = sem direção definida
    if adx < 22:
        peso += 10
        motivos.append(f"adx_baixo_{adx:.0f}")

    # Kalman lateral
    if kalman_dir == "SIDE":
        peso += 15
        motivos.append("kalman_lateral")

    # RSI neutro com fluxo misto
    if 40 <= rsi <= 60:
        delta_abs = abs(delta)
        if delta_abs < 0.02:
            peso += 10
            motivos.append("rsi_neutro_sem_delta")
        elif delta_abs < 0.05:
            peso += 5
            motivos.append("rsi_neutro_delta_baixo")

    # Heikin Ashi neutro
    if not ha_bull and not ha_bear:
        peso += 5
        motivos.append("ha_neutro")

    # Range estreito (volatilidade comprimida)
    if len(highs) >= 14 and len(lows) >= 14 and len(closes) >= 14:
        preco = closes[-1]
        if preco > 0:
            range_pct = (max(highs[-14:]) - min(lows[-14:])) / preco * 100
            if range_pct < 0.8:
                peso += 10
                motivos.append(f"range_estreito_{range_pct:.1f}%")
            elif range_pct < 1.5:
                peso += 5
                motivos.append(f"range_moderado_{range_pct:.1f}%")

    # Consecutive doji-like candles (indecisão)
    if len(candles_op) >= 3:
        doji_count = 0
        for c in candles_op[-5:]:
            body = abs(c[4] - c[1])
            range_c = c[2] - c[3]
            if range_c > 0 and body / range_c < 0.2:
                doji_count += 1
        if doji_count >= 3:
            peso += 10
            motivos.append("velas_indecisas")

    # Classificar gravidade
    if peso >= 40:
        gravidade = "critica"
    elif peso >= 25:
        gravidade = "moderada"
    elif peso >= 15:
        gravidade = "leve"
    else:
        return False, [], "leve"

    em_transicao = gravidade in ("moderada", "critica")
    return em_transicao, motivos, gravidade


def detectar_movimento_esticado(trend, momentum, flow, candles_op, direction):
    """
    Detecta movimento esticado (preço muito distante da média, overextended).
    Retorna (esticado, motivos, gravidade).
    gravidade: "leve" | "moderada" | "critica"
    """
    motivos = []
    gravidade = "leve"

    closes = [c[4] for c in candles_op] if candles_op else []
    highs = [c[2] for c in candles_op] if candles_op else []
    lows = [c[3] for c in candles_op] if candles_op else []
    preco = closes[-1] if closes else 0

    rsi = momentum.get("RSI", 50)
    atr = momentum.get("ATR", 0)
    rvol = flow.get("RVOL", 0)
    ema21 = trend.get("EMA_21")

    peso = 0

    # RSI extremo
    if direction == "long":
        if rsi > 80:
            peso += 25
            motivos.append(f"rsi_muito_alto_{rsi:.0f}")
        elif rsi > 75:
            peso += 15
            motivos.append(f"rsi_elevado_{rsi:.0f}")
        elif rsi > 70:
            peso += 8
            motivos.append(f"rsi_limiar_{rsi:.0f}")
    else:
        if rsi < 20:
            peso += 25
            motivos.append(f"rsi_muito_baixo_{rsi:.0f}")
        elif rsi < 25:
            peso += 15
            motivos.append(f"rsi_baixo_{rsi:.0f}")
        elif rsi < 30:
            peso += 8
            motivos.append(f"rsi_limiar_{rsi:.0f}")

    # Distância da EMA21
    if ema21 and ema21 > 0 and preco > 0:
        dist_ema21 = abs(preco - ema21) / ema21 * 100
        if dist_ema21 > 4.0:
            peso += 20
            motivos.append(f"ema21_muito_distante_{dist_ema21:.1f}%")
        elif dist_ema21 > 2.5:
            peso += 12
            motivos.append(f"ema21_distante_{dist_ema21:.1f}%")
        elif dist_ema21 > 1.5:
            peso += 6
            motivos.append(f"ema21_afastado_{dist_ema21:.1f}%")

    # ATR expandido (candle grande)
    if atr > 0 and len(highs) >= 1 and len(lows) >= 1 and preco > 0:
        candle_range = highs[-1] - lows[-1]
        extension = candle_range / atr
        if extension > 3.0:
            peso += 20
            motivos.append(f"atr_muito_expandido_{extension:.1f}x")
        elif extension > 2.0:
            peso += 10
            motivos.append(f"atr_expandido_{extension:.1f}x")

    # Sequência de velas consecutivas na direção
    if len(closes) >= 5:
        cons = 0
        for i in range(-1, -min(len(closes), 8), -1):
            if direction == "long" and closes[i] > closes[i - 1]:
                cons += 1
            elif direction == "short" and closes[i] < closes[i - 1]:
                cons += 1
            else:
                break
        if cons >= 6:
            peso += 20
            motivos.append(f"sequencia_longa_{cons}")
        elif cons >= 4:
            peso += 10
            motivos.append(f"sequencia_media_{cons}")

    # RVOL muito alto sem continuação (exaustão de volume)
    if rvol > 2.5:
        if len(closes) >= 3:
            gap_reversal = (direction == "long" and closes[-1] < closes[-2]) or \
                           (direction == "short" and closes[-1] > closes[-2])
            if gap_reversal:
                peso += 10
                motivos.append(f"rvol_alto_reversao_{rvol:.1f}x")

    # Classificar gravidade
    if peso >= 40:
        gravidade = "critica"
    elif peso >= 25:
        gravidade = "moderada"
    elif peso >= 12:
        gravidade = "leve"
    else:
        return False, [], "leve"

    esticado = gravidade in ("moderada", "critica")
    return esticado, motivos, gravidade


def detectar_sr_proximo(smc, candles_op, direction, preco, atr):
    """
    Detecta suporte/resistência próximo ao preço atual.
    Retorna (sr_proximo, motivos).
    Apenas alerta — não bloqueia.
    """
    motivos = []

    if not candles_op or len(candles_op) < 20 or not preco or not atr:
        return False, motivos

    closes = [c[4] for c in candles_op]
    highs = [c[2] for c in candles_op]
    lows = [c[3] for c in candles_op]
    opens = [c[1] for c in candles_op]

    # Distância relativa do ATR para considerar "próximo"
    atr_dist = atr * 1.5

    sr_proximo = False

    # 1. Verificar OB (Order Block) próximo
    if smc.get("ORDER_BLOCK"):
        for i in range(-15, -1):
            if abs(i) >= len(candles_op):
                continue
            ob_high = highs[i]
            ob_low = lows[i]
            if direction == "long":
                dist_to_ob = preco - ob_low
                if 0 < dist_to_ob <= atr_dist:
                    motivos.append(f"OB_proximo_{dist_to_ob / atr:.1f}ATR")
                    sr_proximo = True
                    break
                if 0 < ob_high - preco <= atr_dist:
                    motivos.append(f"OB_acima_{abs(ob_high - preco) / atr:.1f}ATR")
                    sr_proximo = True
                    break
            else:
                dist_to_ob = ob_high - preco
                if 0 < dist_to_ob <= atr_dist:
                    motivos.append(f"OB_proximo_{dist_to_ob / atr:.1f}ATR")
                    sr_proximo = True
                    break
                if 0 < preco - ob_low <= atr_dist:
                    motivos.append(f"OB_abaixo_{abs(preco - ob_low) / atr:.1f}ATR")
                    sr_proximo = True
                    break

    # 2. Verificar FVG (Fair Value Gap) próximo
    if not sr_proximo and smc.get("FVG"):
        for i in range(-15, -1):
            if abs(i + 1) >= len(candles_op):
                continue
            gap_top = min(highs[i], highs[i + 1])
            gap_bottom = max(lows[i], lows[i + 1])
            if gap_top > gap_bottom:
                if direction == "long":
                    if gap_bottom - atr_dist <= preco <= gap_top + atr_dist:
                        motivos.append(f"FVG_proximo")
                        sr_proximo = True
                        break
                else:
                    if gap_top - atr_dist <= preco <= gap_bottom + atr_dist:
                        motivos.append(f"FVG_proximo")
                        sr_proximo = True
                        break

    # 3. Verificar pivot swing recente (topo/fundo)
    if not sr_proximo and len(highs) >= 10:
        if direction == "long":
            swing_low = min(lows[-10:])
            dist_swing = preco - swing_low
            if 0 < dist_swing <= atr_dist:
                motivos.append(f"swing_low_proximo_{dist_swing / atr:.1f}ATR")
                sr_proximo = True
        else:
            swing_high = max(highs[-10:])
            dist_swing = swing_high - preco
            if 0 < dist_swing <= atr_dist:
                motivos.append(f"swing_high_proximo_{dist_swing / atr:.1f}ATR")
                sr_proximo = True

    # 4. Verificar liquidez sweep recente (zona varrida)
    if not sr_proximo and smc.get("LIQUIDITY_SWEEP"):
        for i in range(-10, -1):
            if abs(i) >= len(lows) or abs(i) >= len(highs):
                continue
            if direction == "long":
                if lows[i] == min(lows[-(10):]):
                    dist_sweep = preco - lows[i]
                    if 0 < dist_sweep <= atr_dist * 2:
                        motivos.append(f"sweep_proximo_{dist_sweep / atr:.1f}ATR")
                        sr_proximo = True
                        break
            else:
                if highs[i] == max(highs[-(10):]):
                    dist_sweep = highs[i] - preco
                    if 0 < dist_sweep <= atr_dist * 2:
                        motivos.append(f"sweep_proximo_{dist_sweep / atr:.1f}ATR")
                        sr_proximo = True
                        break

    # 5. S/R de EMA (EMA50/200 como zonas)
    if not sr_proximo:
        ema50 = trend.get("EMA_50")
        ema200 = trend.get("EMA_200")
        if ema50 and ema50 > 0:
            dist_ema50 = abs(preco - ema50)
            if dist_ema50 <= atr_dist * 0.8:
                ema_side = "acima" if preco > ema50 else "abaixo"
                motivos.append(f"ema50_{ema_side}_{dist_ema50 / atr:.1f}ATR")
                sr_proximo = True
        if not sr_proximo and ema200 and ema200 > 0:
            dist_ema200 = abs(preco - ema200)
            if dist_ema200 <= atr_dist:
                ema_side = "acima" if preco > ema200 else "abaixo"
                motivos.append(f"ema200_{ema_side}_{dist_ema200 / atr:.1f}ATR")
                sr_proximo = True

    return sr_proximo, motivos
