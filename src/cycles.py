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
from filters import check_filters, check_blockers
from risk import RiskManager
from diagnostics import Diagnostics
from notify import send_signal, send_diagnostic
from schema.variables import empty_schema
from adaptive import AdaptiveWeights
from config import MAX_CRYPTOS, TIMEFRAME_OPERACAO, TIMEFRAME_CONFIRMACAO, TIMEFRAME_MACRO

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
        diagnostics.record(symbol, "bloqueado", "parar_operacoes")
        v["IGNORAR"] = True
        v["MOTIVO"] = "parar_operacoes"
        v["EXECUTAR_ORDEM"] = False
        return v

    passed, filter_result = check_filters(
        v, op_data["TREND"], op_data["FLOW"], op_data["MOMENTUM"], op_data["MARKET"], op_data["SMC"]
    )
    v.update(filter_result)

    if not passed:
        diagnostics.record(symbol, "recusado", v.get("MOTIVO_RECUSA", "filtro"))
        v["IGNORAR"] = True
        v["MOTIVO"] = v.get("MOTIVO_RECUSA", "filtro")
        v["EXECUTAR_ORDEM"] = False
        return v

    # Score com bonus MTF
    score_data = calculate_score(
        adaptive.get_weights(symbol),
        op_data["TREND"], op_data["FLOW"], op_data["SMC"],
        op_data["MOMENTUM"], op_data["MARKET"],
        mtf_bonus=mtf_bonus,
    )
    v.update(score_data)

    # Classificacao
    confianca = adaptive.get_confianca(symbol, score_data["SCORE_TOTAL"])
    classification = classify_signal(score_data["SCORE_TOTAL"], confianca)
    v.update(classification)

    if not classification.get("CLASSIFICACAO_FINAL"):
        v["IGNORAR"] = True
        v["MOTIVO"] = f"score_{score_data['SCORE_TOTAL']}"
        v["EXECUTAR_ORDEM"] = False
        return v

    if not risk.can_enter(symbol):
        diagnostics.record(symbol, "recusado", "limite_risco")
        v["IGNORAR"] = True
        v["MOTIVO"] = "limite_risco"
        v["EXECUTAR_ORDEM"] = False
        return v

    # Decisao final
    direcao = op_data["TREND"].get("DIRECAO", "lateral")
    if direcao == "long":
        v["LONG_PERMITIDO"] = True
        v["LONG_CONFIRMADO"] = True
        v["LONG_SCORE"] = score_data["SCORE_TOTAL"]
        v["LONG_ENTRADA"] = op_data["FLOW"].get("VOLUME", 0)
    elif direcao == "short":
        v["SHORT_PERMITIDO"] = True
        v["SHORT_CONFIRMADO"] = True
        v["SHORT_SCORE"] = score_data["SCORE_TOTAL"]
        v["SHORT_ENTRADA"] = op_data["FLOW"].get("VOLUME", 0)

    v["OPERAR"] = True
    v["IGNORAR"] = False
    v["CONFIANCA"] = confianca
    v["CLASSIFICACAO_FINAL"] = classification.get("CLASSIFICACAO_FINAL", "")
    v["EXECUTAR_ORDEM"] = True
    v["MOTIVO_ENTRADA"] = classification.get("CLASSIFICACAO_FINAL", "")
    v["MOTIVO"] = v["MOTIVO_ENTRADA"]

    risk.enter(symbol)
    diagnostics.record(symbol, v["CLASSIFICACAO_FINAL"], score_data["SCORE_TOTAL"])
    return (symbol, direcao, v)


async def main_cycle():
    risk = RiskManager()
    diagnostics = Diagnostics()
    adaptive = AdaptiveWeights()

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                logger.info("--- GAUSS DNA V5 INFINITY — Iniciando ciclo ---")
                cycle_signals = []

                market_data = await scan_market(
                    session=session,
                    top_n=MAX_CRYPTOS,
                    timeframes=TIMEFRAMES,
                )

                tasks = [
                    processar_par(symbol, tf_data, risk, diagnostics, adaptive, session)
                    for symbol, tf_data in market_data.items()
                ]
                results = await asyncio.gather(*tasks)

                for r in results:
                    if r and len(r) == 3:
                        cycle_signals.append(r)

                # Enviar sinais via Telegram
                for symbol, direcao, v in cycle_signals:
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
                        detalhes={
                            "MTF": v.get("MTF_CONVERGENCIA", False),
                            "Mercado": v.get("ESTADO_MERCADO", ""),
                            "Score": f"{v.get('SCORE_TOTAL', 0)}/100",
                        },
                    )
                    if enviado:
                        logger.info("Sinal %s %s enviado", v.get("CLASSIFICACAO_FINAL"), symbol)

                if not cycle_signals:
                    resumo = diagnostics.summary()
                    if resumo:
                        await send_diagnostic(session, resumo)

                await risk.refresh()

            except Exception as e:
                logger.exception("Erro no ciclo: %s", e)

            await asyncio.sleep(300)
