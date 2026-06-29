import asyncio
import logging
import aiohttp

from modules.scanner import scan_market
from market import classify_market
from trend import analyze_trend
from smart_money import detect_smc
from flow import analyze_flow
from momentum import analyze_momentum
from score import calculate_score, classify_signal
from filters import check_filters, check_blockers, tendencia_adaptativa, confirmacao_disparo
from risk import RiskManager
from diagnostics import Diagnostics
from notify import send_signal, send_diagnostic
from schema.variables import empty_schema
from adaptive import AdaptiveWeights
from config import (
    MAX_CRYPTOS, TIMEFRAME_OPERACAO, TIMEFRAME_CONFIRMACAO, TIMEFRAME_MACRO,
    MAX_SINAIS_POR_CICLO,
    CONFIANCA_MIN_FORTE, CONFIANCA_MIN_MODERADO, CONFIANCA_MIN_FRACO,
)

logger = logging.getLogger(__name__)

# Timeframes para analise multi-timeframe
TIMEFRAMES = [TIMEFRAME_OPERACAO, TIMEFRAME_CONFIRMACAO, TIMEFRAME_MACRO]


def analisar_tf(candles, tf):
    """Analisa um par em um timeframe especifico."""
    market_state = classify_market(candles)
    trend_data = analyze_trend(candles)
    smc_data = detect_smc(candles)
    flow_data = analyze_flow(candles)
    momentum_data = analyze_momentum(candles)
    return {
        "MARKET": market_state,
        "TREND": trend_data,
        "SMC": smc_data,
        "FLOW": flow_data,
        "MOMENTUM": momentum_data,
    }


def calcular_mtf_bonus(analises):
    """
    Calcula bonus multi-timeframe baseado na convergencia entre TFs.
    Retorna (bonus, dados_mtf).
    """
    mtf_data = {}
    bonus = 0

    for tf, dados in analises.items():
        tend = dados["TREND"].get("TENDENCIA", "")
        direcao = dados["TREND"].get("DIRECAO", "")
        sc = 0
        if tend in ("alta", "alta_moderada"):
            sc = 1
        elif tend in ("baixa", "baixa_moderada"):
            sc = -1
        mtf_data[f"MTF_{tf}_TENDENCIA"] = tend
        mtf_data[f"MTF_{tf}_DIRECAO"] = direcao
        mtf_data[f"MTF_{tf}_SCORE"] = sc

    # Verificar convergencia
    direcoes = [d["TREND"].get("DIRECAO") for d in analises.values()]
    nao_neutras = [d for d in direcoes if d != "lateral"]
    if len(nao_neutras) >= 2:
        if all(d == nao_neutras[0] for d in nao_neutras):
            bonus = 15  # Convergencia forte
            mtf_data["MTF_CONVERGENCIA"] = True
        else:
            bonus = 5
            mtf_data["MTF_CONVERGENCIA"] = False
    else:
        mtf_data["MTF_CONVERGENCIA"] = False

    mtf_data["MTF_BONUS"] = bonus
    return bonus, mtf_data


async def processar_par(symbol, tf_data, risk, diagnostics, adaptive, session):
    """Processa um par com multi-timeframe e retorna o schema ou None."""
    # Analisar cada timeframe
    analises = {}
    for tf in TIMEFRAMES:
        candles = tf_data.get(tf, [])
        if len(candles) < 50:
            return None
        analises[tf] = analisar_tf(candles, tf)

    # Usar o timeframe de operacao (15m) para dados principais
    op_data = analises[TIMEFRAME_OPERACAO]
    conf_data = analises[TIMEFRAME_CONFIRMACAO]

    v = empty_schema()
    v["SYMBOL"] = symbol
    v["TIMEFRAME_OPERACAO"] = TIMEFRAME_OPERACAO
    v["TIMEFRAME_CONFIRMACAO"] = TIMEFRAME_CONFIRMACAO
    v["TIMEFRAME_MACRO"] = TIMEFRAME_MACRO

    # Preencher dados principais (timeframe de operacao)
    v.update(op_data["MARKET"])
    v.update(op_data["TREND"])
    v.update(op_data["SMC"])
    v.update(op_data["FLOW"])
    v.update(op_data["MOMENTUM"])

    # Multi-timeframe bonus
    mtf_bonus, mtf_data = calcular_mtf_bonus(analises)
    v.update(mtf_data)

    # Filtros e bloqueios
    blockers = check_blockers(v, op_data["MARKET"], op_data["FLOW"], op_data["MOMENTUM"], op_data["TREND"])
    v.update(blockers)

    if blockers.get("PARAR_OPERACOES"):
        diagnostics.record(symbol, "bloqueado", "circuit_breaker")
        v["IGNORAR"] = True
        v["MOTIVO"] = "circuit_breaker"
        v["EXECUTAR_ORDEM"] = False
        return v

    passed, filter_result = check_filters(
        v, op_data["TREND"], op_data["FLOW"], op_data["MOMENTUM"], op_data["MARKET"], op_data["SMC"]
    )
    v.update(filter_result)

    for f in v.get("FILTROS_REPROVADOS", []):
        diagnostics.record_filter_block(f)

    rsi_val = op_data["MOMENTUM"].get("RSI", 50)

    if not passed:
        diagnostics.record(symbol, "recusado", v.get("MOTIVO_RECUSA", "filtro"), score=0)
        diagnostics.add_candidate(symbol, "LAT", 0, rsi_val, v.get("MOTIVO_RECUSA", "filtro"))
        v["IGNORAR"] = True
        v["MOTIVO"] = v.get("MOTIVO_RECUSA", "filtro")
        v["EXECUTAR_ORDEM"] = False
        return v

    # Determinar direcao: tendencia > delta > RSI > EMA
    direcao = op_data["TREND"].get("DIRECAO", "lateral")
    if direcao not in ("long", "short"):
        delta = op_data["FLOW"].get("DELTA", 0)
        rsi = op_data["MOMENTUM"].get("RSI", 50)
        ema10 = op_data["TREND"].get("EMA_10", 0)
        ema50 = op_data["TREND"].get("EMA_50", 0)
        if delta > 0:
            direcao = "long"
        elif delta < 0:
            direcao = "short"
        elif rsi > 55:
            direcao = "long"
        elif rsi < 45:
            direcao = "short"
        elif ema10 and ema50 and ema10 > ema50:
            direcao = "long"
        elif ema10 and ema50 and ema10 < ema50:
            direcao = "short"
        else:
            v["IGNORAR"] = True
            v["MOTIVO"] = "sem_direcao"
            v["EXECUTAR_ORDEM"] = False
            return v

    preco = op_data["FLOW"].get("PRECO", 0)

    # V7.3 — Tendencia adaptativa (score-based, nao bloqueia)
    tend_pontos, tend_motivo, tend_bloq = tendencia_adaptativa(
        op_data["TREND"], op_data["FLOW"], op_data["MOMENTUM"], direcao, preco,
    )
    if tend_bloq:
        diagnostics.record(symbol, "recusado", f"tendencia_bloqueada_{tend_motivo}", score=0)
        diagnostics.add_candidate(symbol, direcao.upper(), 0, rsi_val, f"TENDENCIA_BLOQUEADA_{tend_motivo}")
        v["IGNORAR"] = True
        v["MOTIVO"] = f"TENDENCIA_BLOQUEADA_{tend_motivo}"
        v["EXECUTAR_ORDEM"] = False
        diagnostics.record_filter_block(f"TENDENCIA_BLOQ_{tend_motivo}")
        return v

    if tend_motivo == "tendencia_parcial":
        diagnostics.record_filter_block(f"TENDENCIA_PARCIAL_{tend_pontos}pts")

    # Score com direcao real, bonus MTF e bonus de tendencia
    score_data = calculate_score(
        adaptive.get_weights(symbol),
        op_data["TREND"], op_data["FLOW"], op_data["SMC"],
        op_data["MOMENTUM"], op_data["MARKET"],
        mtf_bonus=mtf_bonus + tend_pontos,
        preco=preco,
        direcao=direcao,
    )
    v.update(score_data)
    score_total = score_data.get("SCORE_TOTAL", 0)

    # Classificacao
    confianca = adaptive.get_confianca(symbol, score_total)
    classification = classify_signal(score_total, confianca)
    v.update(classification)

    if not classification.get("CLASSIFICACAO_FINAL"):
        diagnostics.record(symbol, "recusado", f"score_{score_total}", score=score_total)
        diagnostics.add_candidate(symbol, direcao.upper(), score_total, rsi_val, f"score_{score_total}")
        v["IGNORAR"] = True
        v["MOTIVO"] = f"score_{score_total}"
        v["EXECUTAR_ORDEM"] = False
        return v

    # Confianca dinamica conforme forca do mercado
    estado = op_data["MARKET"].get("ESTADO_MERCADO", "")
    if estado in ("tendencia_forte",):
        conf_min = CONFIANCA_MIN_FORTE
    elif estado in ("tendencia_moderada", "micro_tendencia"):
        conf_min = CONFIANCA_MIN_MODERADO
    else:
        conf_min = CONFIANCA_MIN_FRACO

    if confianca < conf_min:
        diagnostics.record(symbol, "recusado", f"confianca_{confianca}", score=score_total)
        diagnostics.add_candidate(symbol, direcao.upper(), score_total, rsi_val, f"confianca_{confianca}")
        v["IGNORAR"] = True
        v["MOTIVO"] = f"confianca_{confianca}"
        v["EXECUTAR_ORDEM"] = False
        return v

    # V7.3 Regra 6 — Confirmacao antes do disparo (ate 2 falhas permitidas)
    confirmado, motivo_confirm, detalhes = confirmacao_disparo(
        op_data["TREND"], op_data["FLOW"], op_data["MOMENTUM"],
        op_data["SMC"], direcao, preco,
    )
    if not confirmado:
        v["IGNORAR"] = True
        v["MOTIVO"] = motivo_confirm
        v["EXECUTAR_ORDEM"] = False
        diagnostics.record_filter_block(f"CONFIRMACAO_{motivo_confirm}")
        return v

    for d in detalhes:
        if "sem_" in d:
            diagnostics.record_filter_block(f"CONFIRMACAO_FALTA_{d}")

    ema200 = op_data["TREND"].get("EMA_200", 0)
    if preco and ema200:
        if direcao == "long" and preco < ema200:
            v["IGNORAR"] = True
            v["MOTIVO"] = "preco_abaixo_mm200"
            v["EXECUTAR_ORDEM"] = False
            return v
        if direcao == "short" and preco > ema200:
            v["IGNORAR"] = True
            v["MOTIVO"] = "preco_acima_mm200"
            v["EXECUTAR_ORDEM"] = False
            return v

    v["LONG_PERMITIDO"] = direcao == "long"
    v["LONG_CONFIRMADO"] = direcao == "long"
    v["LONG_SCORE"] = score_data["SCORE_TOTAL"]
    v["LONG_ENTRADA"] = op_data["FLOW"].get("PRECO", op_data["FLOW"].get("VOLUME", 0)) if direcao == "long" else 0
    v["SHORT_PERMITIDO"] = direcao == "short"
    v["SHORT_CONFIRMADO"] = direcao == "short"
    v["SHORT_SCORE"] = score_data["SCORE_TOTAL"]
    v["SHORT_ENTRADA"] = op_data["FLOW"].get("PRECO", op_data["FLOW"].get("VOLUME", 0)) if direcao == "short" else 0

    v["OPERAR"] = True
    v["IGNORAR"] = False
    v["CONFIANCA"] = confianca
    v["CLASSIFICACAO_FINAL"] = classification.get("CLASSIFICACAO_FINAL", "")
    v["EXECUTAR_ORDEM"] = True
    v["MOTIVO_ENTRADA"] = classification.get("CLASSIFICACAO_FINAL", "")
    v["MOTIVO"] = v["MOTIVO_ENTRADA"]

    # Calcular TP/SL baseado em ATR
    atr = op_data["MOMENTUM"].get("ATR", 0)
    preco = op_data["FLOW"].get("PRECO", 0)
    if atr > 0 and preco > 0:
        levels = risk.calc_atr_levels(atr, preco, direcao)
        v.update(levels)
    else:
        v.update({
            "stop_loss": 0, "tp1": 0, "tp2": 0,
            "stop_pct": 0, "tp1_pct": 0, "tp2_pct": 0,
            "tp1_quote_size": 0.5,
        })

    # Risco: sinal sempre enviado, mas entrada real limitada
    pode_entrar = risk.can_enter(symbol)
    if pode_entrar:
        risk.enter(symbol)
        v["MOTIVO"] = f"{v['CLASSIFICACAO_FINAL']}_ENTRADA"
    else:
        v["MOTIVO"] = f"{v['CLASSIFICACAO_FINAL']}_LIMITE_RISCO"
        v["EXECUTAR_ORDEM"] = False

    diagnostics.record(symbol, v["CLASSIFICACAO_FINAL"], score_data["SCORE_TOTAL"])
    diagnostics.add_candidate(
        symbol, direcao.upper(), score_total,
        op_data["MOMENTUM"].get("RSI", 50),
        v.get("MOTIVO", "")
    )
    return (symbol, direcao, v)


async def main_cycle():
    risk = RiskManager()
    diagnostics = Diagnostics()
    adaptive = AdaptiveWeights()

    async with aiohttp.ClientSession() as session:
        try:
            diagnostics.cycle_count = 1
            logger.info("--- GAUSS DNA V5 — Ciclo %d ---", diagnostics.cycle_count)

            market_data = await scan_market(
                session=session,
                top_n=MAX_CRYPTOS,
                timeframes=TIMEFRAMES,
            )

            diagnostics.total_analises = 0
            tasks = [
                processar_par(symbol, tf_data, risk, diagnostics, adaptive, session)
                for symbol, tf_data in market_data.items()
            ]
            results = await asyncio.gather(*tasks)

            cycle_signals = []
            for r in results:
                if r is None:
                    continue
                diagnostics.total_analises += 1
                if len(r) == 3:
                    cycle_signals.append(r)

            # Enviar sinais via Telegram (formato DNA FLEX)
            sinais_enviados = 0
            for symbol, direcao, v in cycle_signals:
                if sinais_enviados >= MAX_SINAIS_POR_CICLO:
                    diagnostics.sinais_pulados = len(cycle_signals) - sinais_enviados
                    logger.info("Limite de %d sinais por ciclo (%d pulados)", MAX_SINAIS_POR_CICLO, diagnostics.sinais_pulados)
                    break
                close = v.get("LONG_ENTRADA") or v.get("SHORT_ENTRADA") or 0
                enviado = await send_signal(
                    session=session,
                    symbol=symbol,
                    direction=direcao.upper(),
                    preco=close,
                    score=v.get("SCORE_TOTAL", 0),
                    classificacao=v.get("CLASSIFICACAO_FINAL", ""),
                    rsi=v.get("RSI", 50),
                    adx=v.get("ADX", 0),
                    rvol=v.get("RVOL", 1.0),
                    tendencia=v.get("TENDENCIA", ""),
                    v=v,
                    timeframe=TIMEFRAME_OPERACAO,
                )
                if enviado:
                    sinais_enviados += 1
                    logger.info("Sinal %s %s enviado (%d/%d)", v.get("CLASSIFICACAO_FINAL"), symbol, sinais_enviados, MAX_SINAIS_POR_CICLO)
                await asyncio.sleep(0.5)

            # Sempre enviar resumo com recomendacao
            await asyncio.sleep(2)
            resumo = diagnostics.summary()
            if resumo:
                await send_diagnostic(session, resumo)

            await risk.refresh()

        except Exception as e:
            logger.exception("Erro no ciclo: %s", e)
            raise

        logger.info("--- CICLO COMPLETO ---")
