"""SINAIS TOP V2 — Orquestrador"""

import asyncio
import json
import logging
import os
import time
import aiohttp
from datetime import datetime, timezone

# Estado global para controle de sinais (Event-Driven)
SYMBOL_STATES = {}
SENT_SIGNALS = {}

from flex.setups import detect_setup
from modules.scanner import scan_market, fetch
from market import classify_market
from trend import analyze_trend
from smart_money import detect_smc
from flow import analyze_flow
from momentum import analyze_momentum
from flex.config import (
    TIMEFRAMES, TIMEFRAME_OPERACAO, MAX_CRYPTOS, CAPITAL,
    SL_ATR_MULT, TP1_ATR_MULT, TP2_ATR_MULT, TP1_PERCENT,
    BLACKLIST, TG_TOKEN, TG_CHATID, MEXC_CONTRACT,
    MIN_CONFIANCA, ATR_MAX_BRONZE, ATR_MAX_PRATA,
    ATR_MAX_OURO, ATR_MAX_OURO_SUPREMO,
)
import flex.config as flex_config
from flex.kalman import kalman_direction
from flex.audit import auditar_sinal
from flex.score import (
    calcular_score, classificar_por_requisitos,
    mapear_score_final, calcular_timing_index,
    calcular_conviction_score, calcular_exaustao,
    calcular_penalidades, calcular_confianca,
    calcular_gestao_operacao, validar_sinal_matematico,
    adjust_confidence,
)
from flex.institutional_regime import (
    analyze_institutional_regime, classify_priority,
    dynamic_atr_stop_multiplier,
)
from flex.filters import run_all
from flex.notify import send_signal, send_diagnostic, Diagnostics
from flex.trades import TradeTracker
from flex.backtest_ab import ComparadorAB

logger = logging.getLogger(__name__)
TF_OPER = TIMEFRAMES[0]
COOLDOWN_MINUTOS = int(os.getenv("COOLDOWN_MINUTOS", "120"))


async def fetch_ticker_24h(session, symbol):
    contract_symbol = symbol.replace("USDT", "_USDT") if symbol.endswith("USDT") else symbol
    contract_url = f"{MEXC_CONTRACT}/ticker?symbol={contract_symbol}"
    contract_data = await fetch(session, contract_url)
    if isinstance(contract_data, dict) and isinstance(contract_data.get("data"), dict):
        data = contract_data["data"]
        bid = float(data.get("bid1", 0) or 0)
        ask = float(data.get("ask1", 0) or 0)
        return {
            "volume": float(data.get("amount24", 0) or 0),
            "high": float(data.get("high24Price", 0) or 0),
            "low": float(data.get("lower24Price", 0) or 0),
            "last": float(data.get("lastPrice", 0) or 0),
            "bid": bid,
            "ask": ask,
            "spread_pct": ((ask - bid) / bid * 100) if bid > 0 else 99,
        }

    spot_url = f"https://api.mexc.com/api/v3/ticker/24hr?symbol={symbol}"
    data = await fetch(session, spot_url)
    if isinstance(data, dict):
        return {
            "volume": float(data.get("quoteVolume", 0) or 0),
            "high": float(data.get("highPrice", 0) or 0),
            "low": float(data.get("lowPrice", 0) or 0),
            "last": float(data.get("lastPrice", 0) or 0),
            "bid": float(data.get("bidPrice", 0) or 0),
            "ask": float(data.get("askPrice", 0) or 0),
            "spread_pct": (
                (float(data.get("askPrice", 0) or 0) - float(data.get("bidPrice", 0) or 0))
                / float(data.get("bidPrice", 0) or 1) * 100
                if float(data.get("bidPrice", 0) or 0) > 0 else 99
            ),
        }
    return None


async def fetch_funding(session, symbol):
    contract_symbol = symbol.replace("USDT", "_USDT") if symbol.endswith("USDT") else symbol
    url = f"https://contract.mexc.com/api/v1/contract/funding_rate/{contract_symbol}"
    data = await fetch(session, url)
    if isinstance(data, dict) and data.get("data"):
        return float(data["data"].get("fundingRate", 0))
    return None


def _determine_direction(trend_data, flow_data, momentum_data, kalman_dir):
    tend = trend_data.get("DIRECAO", "lateral")
    if tend == "long":
        return "long"
    if tend == "short":
        return "short"
    delta = flow_data.get("DELTA", 0)
    if delta > 0.02:
        return "long"
    if delta < -0.02:
        return "short"
    rsi = momentum_data.get("RSI", 50)
    if rsi >= 50:
        return "long"
    if rsi < 50:
        return "short"
    return None


def _calc_atr_levels(atr, preco, direction, sl_atr_mult=None):
    stop_mult = sl_atr_mult if sl_atr_mult is not None else SL_ATR_MULT
    sl_dist = atr * stop_mult
    tp1 = atr * TP1_ATR_MULT
    tp2 = atr * TP2_ATR_MULT
    if direction == "long":
        sl = preco - sl_dist
        tp1_p = preco + tp1
        tp2_p = preco + tp2
    else:
        sl = preco + sl_dist
        tp1_p = preco - tp1
        tp2_p = preco - tp2
    return {
        "stop_loss": round(sl, 8),
        "tp1": round(tp1_p, 8),
        "tp2": round(tp2_p, 8),
        "stop_pct": round(sl_dist / preco * 100, 2) if preco > 0 else 0,
        "sl_atr_mult": stop_mult,
    }


async def processar_par(symbol, tf_data, ticker, funding, diag, follow_through_pct=0,
                         btc_direction="", eth_direction="", modo_defensivo=False):
    candles_op = tf_data.get(TF_OPER, [])
    candles_1h = tf_data.get(TIMEFRAMES[1], [])
    candles_4h = tf_data.get(TIMEFRAMES[2], [])
    if len(candles_op) < 50:
        return None

    # Blacklist: impedir trading de stablecoins
    if any(symbol.startswith(b) for b in BLACKLIST):
        return None

    # DEBUG: tracking de filtros
    passou_liquidez = False
    passou_volume = False
    passou_atr = False
    passou_rsi = False
    passou_adx = False
    passou_rvol = False
    passou_tendencia = False
    passou_fluxo = False
    passou_kalman = False
    passou_score = False
    passou_timing = False
    passou_spread = False
    passou_tp1 = False
    passou_mm200 = False
    passou_exaustao = False
    passou_multitf = False

    closes = [c[4] for c in candles_op]
    market = classify_market(candles_op)
    trend = analyze_trend(candles_op)
    smc = detect_smc(candles_op)
    flow = analyze_flow(candles_op)
    momentum = analyze_momentum(candles_op)
    kalman_dir = kalman_direction(closes)

    # V9.0: Detector de Setup Institucional
    setup = detect_setup(candles_op, trend, smc, flow, momentum)
    if not setup:
        diag.record_funil("recusada")
        diag.record_bloqueador("setup_nao_detectado")
        return None

    direction = _determine_direction(trend, flow, momentum, kalman_dir)
    if direction is None:
        diag.record_funil("recusada")
        return None

    # DEBUG: helper
    # Direção no 1H e 4H para multi-timeframe
    direction_1h = None
    direction_4h = None
    if len(candles_1h) >= 50:
        trend_1h = analyze_trend(candles_1h)
        flow_1h = analyze_flow(candles_1h)
        mom_1h = analyze_momentum(candles_1h)
        kd_1h = kalman_direction([c[4] for c in candles_1h])
        direction_1h = _determine_direction(trend_1h, flow_1h, mom_1h, kd_1h)

    if len(candles_4h) >= 50:
        trend_4h = analyze_trend(candles_4h)
        flow_4h = analyze_flow(candles_4h)
        mom_4h = analyze_momentum(candles_4h)
        kd_4h = kalman_direction([c[4] for c in candles_4h])
        direction_4h = _determine_direction(trend_4h, flow_4h, mom_4h, kd_4h)

    diag.record_funil("liquidez")

    # Indicadores
    volume_24h = ticker["volume"] if ticker else 0
    spread = ticker["spread_pct"] if ticker else 0
    rvol = flow.get("RVOL", 0)
    adx = momentum.get("ADX", 0)
    rsi = momentum.get("RSI", 50)

    if volume_24h is not None and volume_24h > 0:
        passou_liquidez = True
        passou_volume = True
        diag.record_funil("volume")
    else:
        passou_liquidez = False
        diag.record_sem_indicador("volume")
        diag.record_bloqueador("liquidez")

    if mom := momentum.get("ATR"):
        passou_atr = True
        diag.record_funil("atr")
    else:
        diag.record_sem_indicador("atr")
        diag.record_bloqueador("atr")

    if rsi > 0:
        passou_rsi = True
        diag.record_funil("rsi")
    else:
        diag.record_sem_indicador("rsi")
        diag.record_bloqueador("rsi")

    if adx > 0:
        passou_adx = True
        diag.record_funil("adx")
    else:
        diag.record_sem_indicador("adx")
        diag.record_bloqueador("adx")

    if rvol > 0:
        passou_rvol = True
        diag.record_funil("rvol")
    else:
        diag.record_sem_indicador("rvol")
        diag.record_bloqueador("rvol")

    tendencia_str = trend.get("TENDENCIA", "")
    passou_tendencia = True
    diag.record_funil("tendencia")

    aprovado, motivos, score_ajuste, velas = run_all(
        symbol, direction, trend, flow, momentum, smc, market,
        candles_op, kalman_dir, volume_24h, spread
    )

    if not aprovado:
        diag.record_funil("recusada")
        motivo_final = motivos[0] if motivos else "filtro_desconhecido"
        diag.record_bloqueador(motivo_final)
        logger.warning(f"SINAL BLOQUEADO: {symbol} | Motivo: {motivo_final}")
        return None

    passou_fluxo = True
    diag.record_funil("fluxo")
    passou_kalman = True
    diag.record_funil("kalman")

    timing_index = calcular_timing_index(trend, flow, momentum, smc, candles_op, direction)
    passou_timing = True
    exaustao_data = calcular_exaustao(trend, flow, momentum, candles_op, direction)
    passou_exaustao = True

    btc_eth_bonus = 0
    if direction == "long" and btc_direction == "long" and eth_direction == "long":
        btc_eth_bonus = 2
    elif direction == "short" and btc_direction == "short" and eth_direction == "short":
        btc_eth_bonus = 2

    regime_data = analyze_institutional_regime(
        symbol, direction, trend, flow, momentum, smc, market, kalman_dir,
        candles_op, direction_1h=direction_1h, direction_4h=direction_4h
    )
    regime_name = regime_data.get("regime", "TRANSICAO")

    score_data = calcular_score(
        trend, flow, momentum, smc, market, kalman_dir, direction,
        velas, follow_through_pct, volume_24h, spread,
        timing_index=timing_index, btc_eth_bonus=btc_eth_bonus,
        direction_1h=direction_1h, direction_4h=direction_4h,
        candles_op=candles_op, regime_name=regime_name
    )

    passou_score = score_data.get("aprovado", True)
    # Diagnóstico detalhado de reprovação no Score
    if not score_data.get("aprovado", True):
        # ... lógica de log ...
        motivos_list = score_data.get("motivos", [])
        score_details = score_data.get("componentes", {})
        logger.info(f"DEBUG SCORE REPROVADO: {symbol} | Total: {score_data.get('score_total', 0)} | Comp: {score_details} | Motivos: {motivos_list}")
        
        motivo = motivos_list[0] if motivos_list else "score_reprovado"
        diag.record_funil("recusada")
        diag.record_bloqueador(motivo if motivo in ("rsi_bloqueio", "fluxo_contra", "timing_bloqueio") else "score")
        diag.record_analise(symbol, direction.upper(), 0, False, motivo,
                            rsi, adx, rvol, volume_24h, tendencia=tendencia_str)
        return None

    diag.record_funil("score")

    atr = momentum.get("ATR", 0)
    preco = tf_data.get(TF_OPER, [[0,0,0,0,0,0]])[-1][4] # Pega preço atual do candle
    atr_pct = (atr / preco * 100) if (preco and preco > 0) else 0.0
    score_final = max(0, min(100, score_data["score_total"] + regime_data.get("score_delta", 0)))
    score_label = mapear_score_final(score_final)
    score_stage_entry = [symbol, direction.upper(), score_final, ""]

    # Exaustão: penalidade progressiva (nunca bloqueia — score final decide)
    score_com_exaustao = score_final + exaustao_data.get("penalidade", 0)

    pen = calcular_penalidades(score_com_exaustao, rsi, flow, direction, kalman_dir, trend)
    penalidade, motivos_pen = pen

    # Incluir penalidade do Kalman SIDE (aplicada no score, agora registrada aqui)
    kalman_penalty = score_data.get("kalman_penalty", 0)
    if kalman_penalty < 0:
        penalidade += abs(kalman_penalty)
        motivos_pen.append("kalman_side")

    # Limitar penalidade total a 8 pontos conforme pedido
    penalidade = min(penalidade, 8)
    score_com_penalidade = max(score_com_exaustao - penalidade, 0)

    if penalidade > 0:
        diag.score_penalizados.append((symbol, direction.upper(), penalidade, motivos_pen, score_com_exaustao, score_com_penalidade))

    # Determinar Score Mínimo Adaptativo baseado no Índice Institucional
    institutional_index = regime_data.get("institutional_index", 50)
    if institutional_index >= 75: min_score = 58
    elif institutional_index >= 60: min_score = 54
    elif institutional_index >= 45: min_score = 50
    else: min_score = 47

    if modo_defensivo:
        min_score += 10  # Aumenta exigência no Modo Defensivo
        logger.info(f"Modo Defensivo ativo para {symbol}: MinScore ajustado para {min_score}")

    if score_com_penalidade < min_score:
        if 55 <= score_com_penalidade < min_score:
            diag.presinais.append({"symbol": symbol, "score": score_com_penalidade, "faltando": "score_baixo"})
        diag.record_funil("recusada")
        diag.record_bloqueador("score_minimo_adaptativo")
        return None

    # Calcular convicção antes da classificação
    conviction_score = calcular_conviction_score(
        flow, momentum.get("ADX", 0), momentum.get("RVOL", 1.0),
        smc, momentum, kalman_dir
    )

    # Classificar
    categoria, motivo_recusa = classificar_por_requisitos(
        score_com_penalidade, adx, rvol, timing_index, flow, direction,
        kalman_dir, trend, velas, conviction_score, direction_1h=direction_1h,
        direction_4h=direction_4h, follow_through_pct=follow_through_pct
    )
    if categoria is None:
        diag.record_funil("recusada")
        diag.record_bloqueador("score")
        diag.record_analise(symbol, direction.upper(), score_com_penalidade, False,
                            motivo_recusa or "classificacao_reprovada", rsi, adx, rvol,
                            volume_24h, atr=atr_pct, tendencia=tendencia_str)
        return None

    emoji_map = {"OURO_SUPREMO": "💎", "OURO": "🥇", "PRATA": "🥈", "BRONZE": "🥉"}
    qual_map = {"OURO_SUPREMO": "SUPREMA", "OURO": "EXCELENTE", "PRATA": "MUITO BOA", "BRONZE": "BOA"}
    confianca = calcular_confianca(score_com_penalidade, categoria)
    confianca = adjust_confidence(confianca, regime_data.get("regime"), direction)
    if confianca < MIN_CONFIANCA:
        diag.record_funil("recusada")
        diag.record_bloqueador("confianca")
        diag.record_analise(symbol, direction.upper(), score_final, False,
                            f"confianca_baixa_{confianca}", rsi, adx, rvol, volume_24h,
                            atr=atr_pct, tendencia=tendencia_str)
        return None

    # Regra 3: Probabilidade não pode ser maior que a qualidade real dos filtros
    # Exemplo: Se RVOL ou Fluxo estão fracos, derrubamos a probabilidade
    confianca_ajustada = confianca
    if rvol < 0.8:
        confianca_ajustada = min(confianca_ajustada, 70)
    # Restaurar fluxo_forte para diagnóstico
    delta = flow.get("DELTA", 0)
    vol_cres = flow.get("VOLUME_CRESCENTE", False)
    rvol_v = flow.get("RVOL", 0)
    fluxo_forte = (
        (direction == "LONG" and delta > 0) or
        (direction == "SHORT" and delta < 0)
    ) and vol_cres and rvol_v > 1.2
    
    if not fluxo_forte:
        confianca_ajustada = min(confianca_ajustada, 80)
        
    classific = {
        "classificacao": categoria,
        "emoji": emoji_map.get(categoria, "📊"),
        "qualidade": qual_map.get(categoria, ""),
        "confianca": confianca_ajustada,
    }

    diag.dados_simulacao.append({
        "rvol": rvol, "adx": adx, "score": score_com_penalidade, "timing": timing_index,
        "direction": direction.upper(),
    })

    limite_atr = {
        "OURO_SUPREMO": ATR_MAX_OURO_SUPREMO,
        "OURO": ATR_MAX_OURO,
        "PRATA": ATR_MAX_PRATA,
        "BRONZE": ATR_MAX_BRONZE,
    }.get(categoria, ATR_MAX_BRONZE)
    if atr_pct * 100 > limite_atr:
        passou_atr = False
        motivo = f"atr_excedido_{atr_pct*100:.1f}%"
        score_stage_entry[3] = motivo
        diag.score_stage.append(tuple(score_stage_entry))
        diag.record_funil("recusada")
        diag.record_bloqueador("atr")
        diag.record_analise(symbol, direction.upper(), score_final, False,
                            f"atr_excedido_{atr_pct*100:.1f}%", rsi, adx, rvol, volume_24h,
                            atr=atr_pct, tendencia=tendencia_str)
        return None

    preco = flow.get("PRECO", 0)
    atr = momentum.get("ATR", 0)
    sl_atr_mult, atr_regime = dynamic_atr_stop_multiplier(atr_pct)
    levels = _calc_atr_levels(atr, preco, direction, sl_atr_mult) if atr > 0 and preco > 0 else {}

    # TP1 mínimo $1 + RR check
    gestao = calcular_gestao_operacao(
        score_com_penalidade, categoria, adx, rvol, timing_index,
        flow, direction, kalman_dir, levels.get("stop_pct", 0)
    )
    if gestao.get("perfil") == "RR_INSUFICIENTE":
        passou_tp1 = False
        score_stage_entry[3] = f"rr_insuficiente_{gestao.get('rr', 0):.1f}"
        diag.score_stage.append(tuple(score_stage_entry))
        diag.record_funil("recusada")
        diag.record_bloqueador("tp1_minimo")
        diag.record_analise(symbol, direction.upper(), score_final, False,
                            f"rr_insuficiente_{gestao.get('rr', 0):.1f}", rsi, adx, rvol, volume_24h,
                            atr=atr_pct, tendencia=tendencia_str)
        return None
    colateral = CAPITAL * gestao["risco_pct"] * gestao["mult_entrada"]
    posicao_total = colateral * gestao["alavancagem"]
    half_pos = posicao_total / 2
    tp1 = levels.get("tp1", 0)
    if direction == "long":
        tp1_gain_dol = half_pos * (tp1 - preco) / preco if preco > 0 and tp1 > 0 else 0
    else:
        tp1_gain_dol = half_pos * (preco - tp1) / preco if preco > 0 and tp1 > 0 else 0
    passou_tp1 = True
    if tp1_gain_dol < 0.08:
        passou_tp1 = False
        score_stage_entry[3] = f"tp1_${tp1_gain_dol:.2f}"
        diag.score_stage.append(tuple(score_stage_entry))
        diag.record_funil("recusada")
        diag.record_bloqueador("tp1_minimo")
        diag.record_analise(symbol, direction.upper(), score_final, False,
                            f"tp1_ganho_${tp1_gain_dol:.2f}", rsi, adx, rvol, volume_24h,
                            atr=atr_pct, tendencia=tendencia_str)
        return None

    diag.record_funil("aprovada")
    score_stage_entry[3] = "APROVADO"
    diag.score_stage.append(tuple(score_stage_entry))

    # Adicionar debug de score ao resultado
    result_data = {
        "symbol": symbol,
        "direction": direction.upper(),
        "setup": setup,
        "classificacao": classific["classificacao"],
        "prioridade": classify_priority(categoria, regime_data, flow, kalman_dir, direction, adx, rvol),
        "emoji": classific["emoji"],
        "score": score_com_penalidade,
        "confianca": confianca,
        "preco": preco,
        "rsi": rsi,
        "adx": adx,
        "rvol": rvol,
        "atr": atr,
        "atr_pct": atr_pct,
        "timing_index": timing_index,
        "exaustao": exaustao_data,
        "regime_data": regime_data,
        "atr_regime": atr_regime,
        "trend": trend.get("TENDENCIA", ""),
        "trend_alinhada": trend.get("EMA_ALINHADA", False),
        "kalman": kalman_dir,
        "flow_data": flow,
        "funding": funding,
        "timeframe": TF_OPER,
        "velas": velas,
        "debug": score_data.get("debug", {}),
        **levels,
    }
    
    return result_data


async def fetch_futures_symbols(session):
    url = "https://contract.mexc.com/api/v1/contract/detail"
    data = await fetch(session, url, timeout=15)
    if isinstance(data, dict) and data.get("success") and isinstance(data.get("data"), list):
        futuros = set()
        for c in data["data"]:
            base = c.get("baseCoin", "")
            quote = c.get("quoteCoin", "")
            if base and quote:
                    futuros.add(base + quote)
        return futuros
    return None


async def main_cycle(send_diag=True):
    diag = Diagnostics()
    trades = TradeTracker()
    diag.start()

    async with aiohttp.ClientSession() as session:
        try:
            logger.info("--- SINAIS TOP V2 — Iniciando ciclo (%d moedas) ---", MAX_CRYPTOS)
            t0 = asyncio.get_event_loop().time()
            market_data = await scan_market(session=session, top_n=MAX_CRYPTOS, timeframes=TIMEFRAMES)
            t1 = asyncio.get_event_loop().time()

            moedas_carregadas = len(market_data)
            diag.record_funil("exchange")
            diag.funil_exchange = moedas_carregadas
            candles_ok = sum(1 for v in market_data.values() if len(v.get(TIMEFRAMES[0], [])) >= 50)
            candles_inv = max(0, moedas_carregadas - candles_ok)

            futuros_validos = await fetch_futures_symbols(session)
            if futuros_validos is not None:
                antes = len(market_data)
                market_data = {s: v for s, v in market_data.items() if s in futuros_validos}
                logger.info("Filtro futuros: %d -> %d pares (removidos %d sem contrato futuro)",
                            antes, len(market_data), antes - len(market_data))
            else:
                logger.warning("Nao foi possivel obter lista de futuros — prosseguindo sem filtro")

            moedas_validas = len(market_data)
            erros_api = moedas_carregadas - moedas_validas
            diag.record_scanner_debug(moedas_carregadas, moedas_validas, candles_ok, candles_inv, erros_api, t1 - t0)

            logger.info("Buscando tickers 24h e funding...")
            symbols = list(market_data.keys())
            api_semaphore = asyncio.Semaphore(10)

            async def bounded_fetch_ticker(symbol):
                async with api_semaphore:
                    return await fetch_ticker_24h(session, symbol)

            async def bounded_fetch_funding(symbol):
                async with api_semaphore:
                    return await fetch_funding(session, symbol)

            ticker_tasks = [bounded_fetch_ticker(s) for s in symbols]
            funding_tasks = [bounded_fetch_funding(s) for s in symbols]
            tickers_list, fundings_list = await asyncio.gather(
                asyncio.gather(*ticker_tasks),
                asyncio.gather(*funding_tasks),
            )

            tickers = dict(zip(symbols, tickers_list))
            fundings = dict(zip(symbols, fundings_list))

            for sym, vol in tickers.items():
                if vol is None:
                    diag.record_sem_indicador("volume")
                if fundings.get(sym) is None:
                    diag.record_sem_indicador("funding")

            # Ajuste dinâmico do volume mínimo baseado na mediana do mercado
            volumes_24h = [t["volume"] for t in tickers.values() if t and t.get("volume", 0) > 0]
            if len(volumes_24h) >= 10:
                vols_sorted = sorted(volumes_24h)
                mediana = vols_sorted[len(vols_sorted) // 2]
                novo_min = max(
                    flex_config.VOLUME_MINIMO_ABSOLUTO,
                    min(flex_config.VOLUME_MAXIMO_ABSOLUTO,
                        round(mediana * flex_config.VOLUME_MULTIPLICADOR))
                )
                if novo_min != flex_config.MIN_VOLUME_24H:
                    logger.info("Volume mediano mercado: $%s -> MIN_VOLUME_24H ajustado: $%s (era $%s)",
                                f"{mediana:,.0f}", f"{novo_min:,.0f}", f"{flex_config.MIN_VOLUME_24H:,.0f}")
                    flex_config.MIN_VOLUME_24H = novo_min

            logger.info("Estimando Follow Through...")
            direcao_count = 0
            total = 0
            for symbol, tf_data in market_data.items():
                candles_op = tf_data.get(TF_OPER, [])
                if len(candles_op) < 50:
                    continue
                total += 1
                closes_v = [c[4] for c in candles_op]
                mkt = classify_market(candles_op)
                tr = analyze_trend(candles_op)
                fl = analyze_flow(candles_op)
                mm = analyze_momentum(candles_op)
                kd = kalman_direction(closes_v)
                dir_ = _determine_direction(tr, fl, mm, kd)
                if dir_ is not None:
                    trend_dir = tr.get("DIRECAO", "lateral")
                    flow_dir = "long" if fl.get("DELTA", 0) > 0 else "short"
                    kalman_ok = (kd == "UP" and dir_ == "long") or (kd == "DOWN" and dir_ == "short")
                    trend_ok = trend_dir == dir_
                    flow_ok = flow_dir == dir_
                    consec_ok = all(
                        (closes_v[-j] > closes_v[-j-1]) if dir_ == "long" else (closes_v[-j] < closes_v[-j-1])
                        for j in range(1, min(4, len(closes_v)))
                    )
                    score_alinhamento = sum([trend_ok, flow_ok, kalman_ok, consec_ok])
                    if score_alinhamento >= 3:
                        direcao_count += 0.5
                    if score_alinhamento >= 4:
                        direcao_count += 0.5

            follow_through_pct = (direcao_count / max(total, 1)) * 100
            logger.info("Follow Through estimado: %.1f%% (%d/%d)", follow_through_pct, direcao_count, total)

            # Baixo FT exige mais seletividade; nao relaxar liquidez em mercado sem continuacao.
            if follow_through_pct < 5:
                logger.info("Baixo FT (%.1f%%) -> MIN_VOLUME_24H mantido em $%s para preservar qualidade",
                            follow_through_pct, f"{flex_config.MIN_VOLUME_24H:,.0f}")

            btc_direction = ""
            eth_direction = ""
            btc_data = market_data.get("BTCUSDT", {}).get(TF_OPER, [])
            eth_data = market_data.get("ETHUSDT", {}).get(TF_OPER, [])
            if len(btc_data) >= 50:
                btc_flow = analyze_flow(btc_data)
                btc_emotions = analyze_momentum(btc_data)
                btc_kd = kalman_direction([c[4] for c in btc_data])
                btc_trend = analyze_trend(btc_data)
                btc_direction = _determine_direction(btc_trend, btc_flow, btc_emotions, btc_kd)
                diag.btc_trend = btc_trend.get("TENDENCIA", "?")
            if len(eth_data) >= 50:
                eth_flow = analyze_flow(eth_data)
                eth_emotions = analyze_momentum(eth_data)
                eth_kd = kalman_direction([c[4] for c in eth_data])
                eth_trend = analyze_trend(eth_data)
                eth_direction = _determine_direction(eth_trend, eth_flow, eth_emotions, eth_kd)
                diag.eth_trend = eth_trend.get("TENDENCIA", "?")

            cooldown_file = os.path.join(os.path.dirname(__file__), "..", "..", "state", "cooldown.json")
            cooldown_map = {}
            try:
                if os.path.exists(cooldown_file):
                    with open(cooldown_file) as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            cooldown_map = data
                        elif isinstance(data, list):
                            cooldown_map = {s: 0 for s in data}
            except Exception:
                pass

            agora = time.time()
            cooldown_syms = {
                s for s, ts in cooldown_map.items()
                if (agora - ts) < COOLDOWN_MINUTOS * 60
            }
            if cooldown_syms:
                logger.info("Símbolos em cooldown (%d min): %s", COOLDOWN_MINUTOS, cooldown_syms)

            _, consecutive_losses = trades.get_consecutive_stats()
            modo_defensivo = consecutive_losses >= 3
            if modo_defensivo:
                logger.warning("!!! MODO DEFENSIVO ATIVADO (Stops consecutivos: %d) !!!", consecutive_losses)

            # --- OTIMIZAÇÃO: Concorrência controlada no scan ---
            logger.info("Processando %d pares (concorrente)...", len(market_data))
            
            # Limitar concorrência para não estourar rate limit da MEXC
            semaphore = asyncio.Semaphore(10)
            
            async def bounded_process(symbol, tf_data):
                async with semaphore:
                    if symbol in cooldown_syms:
                        return None
                    return await processar_par(
                        symbol, tf_data, tickers.get(symbol), fundings.get(symbol), diag,
                        follow_through_pct, btc_direction, eth_direction, modo_defensivo
                    )
            
            tasks = [bounded_process(s, d) for s, d in market_data.items()]
            results = await asyncio.gather(*tasks)
            
            sinais = []
            for result in results:
                if not result:
                    continue
                # ... resto da lógica de sinal e cooldown

                if result.get("confianca", 0) < 60:
                    continue

                sinais.append(result)
                diag.record_sinal(
                    result["classificacao"], symbol, result["direction"],
                    result["score"], ""
                )
                flow_data = result.get("flow_data", {})
                delta = flow_data.get("DELTA", 0)
                vol_cres = flow_data.get("VOLUME_CRESCENTE", False)
                rvol_v = result.get("rvol", 0)
                fluxo_forte = (
                    (result["direction"] == "LONG" and delta > 0) or
                    (result["direction"] == "SHORT" and delta < 0)
                ) and vol_cres and rvol_v > 2.0
                diag.record_analise(
                    symbol, result["direction"], result["score"], True,
                    None, result["rsi"], result["adx"],
                    result["rvol"], tickers.get(symbol, {}).get("volume"),
                    atr=result.get("atr_pct", 0), velas=result.get("velas"),
                    fluxo_forte=fluxo_forte, kalman_dir=result.get("kalman"),
                    timing_index=result.get("timing_index"),
                    tendencia=result.get("trend", ""),
                )

                # Auditoria Matemática antes do envio
                is_valid, err = validar_sinal_matematico(
                    result["symbol"], result["direction"], result["preco"],
                    result.get("stop_loss", 0), result.get("tp1", 0), 
                    result.get("tp2", 0), 0, # TP3 as 0
                    0, result["funding"]
                )
                if not is_valid:
                    logger.warning("Sinal %s bloqueado por auditoria: %s", result["symbol"], err)
                    continue

                # Conviction Score
                result["conviction_score"] = calcular_conviction_score(
                    result["flow_data"], result["adx"], result["rvol"],
                    result.get("regime_data", {}), 
                    {"HA_BULL": True},
                    result["kalman"]
                )

                # Enviar sinal imediatamente
                asyncio.create_task(send_signal(
                    session=session,
                    symbol=result["symbol"],
                    direction=result["direction"],
                    preco=result["preco"],
                    score=result["score"],
                    classificacao=result["classificacao"],
                    confianca=result["confianca"],
                    rsi=result["rsi"],
                    adx=result["adx"],
                    rvol=result["rvol"],
                    trend_text=result["trend"],
                    flow_data=result["flow_data"],
                    kalman_dir=result["kalman"],
                    conviction_score=result["conviction_score"],
                    stop_loss=result.get("stop_loss", 0),
                    stop_pct=result.get("stop_pct", 0),
                    tp1=result.get("tp1", 0),
                    tp2=result.get("tp2", 0),
                    regime_data=result.get("regime_data"),
                    prioridade=result.get("prioridade"),
                    atr_regime=result.get("atr_regime"),
                    sl_atr_mult=result.get("sl_atr_mult"),
                    funding_rate=result["funding"],
                    timeframe=result["timeframe"],
                    velas_fortes=result["velas"],
                    timing_index=result.get("timing_index"),
                    atr_pct=result.get("atr_pct", 0),
                    setup=result.get("setup") # Passando info do Setup
                ))

                # Atualizar cooldown no ato
                cooldown_map[symbol] = agora
                try:
                    os.makedirs(os.path.dirname(cooldown_file), exist_ok=True)
                    with open(cooldown_file, "w") as f:
                        json.dump(cooldown_map, f)
                except Exception:
                    pass

                # Trade tracking também no ato
                if trades.open_trade and trades.open_trade["symbol"] != symbol:
                    old_ticker = tickers.get(trades.open_trade["symbol"], {})
                    current_price = old_ticker.get("last") if old_ticker else None
                    if current_price is None:
                        current_price = trades.open_trade.get("entry", 0)
                    trades.close(current_price)
                trades.open(
                    symbol=result["symbol"],
                    direction=result["direction"],
                    preco=result["preco"],
                    stop=result.get("stop_loss", 0),
                    tp1=result.get("tp1", 0),
                    classificacao=result["classificacao"],
                    score=result["score"],
                    ticker_last=tickers.get(result["symbol"], {}).get("last") if tickers.get(result["symbol"]) else None,
                )

            for f_val in fundings.values():
                diag.record_funding(f_val)

            # Relatório solicitado
            logger.info("=== RESULTADO DO CICLO ===")
            logger.info(f"Ativos analisados: {diag.total_analisadas}")
            logger.info(f"Chegaram ao Score: {diag.funil_score}")
            logger.info(f"Bronze: {diag.bronze} | Prata: {diag.prata} | Ouro: {diag.ouro}")
            logger.info(f"Reprovados: {diag.funil_recusadas}")
            
            logger.info("Distribuição dos motivos de reprovação:")
            for motivo, count in diag.motivos_recusa.most_common():
                logger.info(f"  {motivo}: {count}")
            logger.info("==========================")
            
            logger.info("  BLOCK: liq=%d rvol=%d adx=%d score=%d fluxo=%d kalman=%d atr=%d mm200=%d rsi=%d funding=%d (rvol_only=%d)",
                        diag.bloqueador_liquidez, diag.bloqueador_rvol, diag.bloqueador_adx,
                        diag.bloqueador_score, diag.bloqueador_fluxo, diag.bloqueador_kalman,
                        diag.bloqueador_atr, diag.bloqueador_mm200, diag.bloqueador_rsi,
                        diag.bloqueador_funding, diag.only_rvol_blocked)

            diag.trades = trades
            diag.finish()
            if send_diag:
                await send_diagnostic(session, diag)

                ab = ComparadorAB()
                ab.registrar(trades, diag)
                relatorio = ab.mensagem_relatorio()
                if relatorio:
                    url_ab = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                    try:
                        async with session.post(url_ab, json={"chat_id": TG_CHATID, "text": relatorio},
                                                timeout=aiohttp.ClientTimeout(total=10)) as r:
                            data = await r.json()
                            if data.get("ok"):
                                logger.info("Backtest A/B enviado")
                    except Exception as e:
                        logger.warning("Backtest A/B falhou: %s", e)
                ab.salvar_como_anterior()

            logger.info("--- CICLO COMPLETO ---")

        except Exception as e:
            logger.exception("Erro no ciclo: %s", e)
            raise
