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

logger = logging.getLogger(__name__)


async def main_cycle():
    risk = RiskManager()
    diagnostics = Diagnostics()

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                logger.info("--- Iniciando ciclo de scan ---")
                cycle_signals = []

                market_data = await scan_market()

                for symbol, candles in market_data.items():
                    market_state = classify_market(candles)
                    if market_state == "lateral":
                        diagnostics.record(symbol, "bloqueado", "mercado_lateral")
                        continue

                    trend_dir, trend_mas = analyze_trend(candles)
                    smc = detect_smc(candles)
                    flow = analyze_flow(candles)
                    momentum = analyze_momentum(candles)

                    score = calculate_score((trend_dir, trend_mas), flow, smc, momentum)
                    classification = classify_signal(score)

                    blockers = check_blockers(trend_dir, flow, smc, momentum, flow)
                    if blockers:
                        diagnostics.record(symbol, "bloqueado", blockers)
                        continue

                    passed = check_filters((trend_dir, trend_mas), flow, momentum)
                    if not passed:
                        diagnostics.record(symbol, "recusado", "filtros")
                        continue

                    if not risk.can_enter(symbol):
                        diagnostics.record(symbol, "recusado", "limite_risco")
                        continue

                    risk.enter(symbol)
                    diagnostics.record(symbol, classification, score)
                    cycle_signals.append((symbol, trend_dir, trend_mas, smc, flow, momentum, classification, score))

                # Enviar sinais via Telegram
                for item in cycle_signals:
                    symbol, trend_dir, _, _, flow, momentum, classification, score = item
                    close = market_data[symbol][-1][4]
                    direction = "LONG" if flow["fluxo_direcao"] == "comprador" else "SHORT"

                    enviado = await send_signal(
                        session=session,
                        symbol=symbol,
                        direction=direction,
                        preco=close,
                        score=score,
                        classificacao=classification,
                        rsi=momentum["rsi"],
                        adx=momentum["adx"],
                        rvol=flow["rvol"],
                        tendencia=trend_dir,
                    )
                    if enviado:
                        logger.info("Sinal %s %s enviado ao Telegram", classification, symbol)

                # Enviar diagnóstico se não houve sinais
                if not cycle_signals:
                    resumo = diagnostics.summary()
                    if resumo:
                        await send_diagnostic(session, resumo)

                await risk.refresh()

            except Exception as e:
                logger.exception("Erro no ciclo: %s", e)

            await asyncio.sleep(300)
