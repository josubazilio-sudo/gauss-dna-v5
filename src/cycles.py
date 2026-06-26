import asyncio
import logging

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

logger = logging.getLogger(__name__)


async def main_cycle():
    risk = RiskManager()
    diagnostics = Diagnostics()

    while True:
        try:
            logger.info("--- Iniciando ciclo de scan ---")

            market_data = await scan_market()

            for symbol, candles in market_data.items():
                market_state = classify_market(candles)
                if market_state == "lateral":
                    diagnostics.record(symbol, "bloqueado", "mercado_lateral")
                    continue

                trend = analyze_trend(candles)
                smc = detect_smc(candles)
                flow = analyze_flow(candles)
                momentum = analyze_momentum(candles)

                score = calculate_score(trend, flow, smc, momentum)
                classification = classify_signal(score)

                blockers = check_blockers(trend, flow, smc, momentum, flow)
                if blockers:
                    diagnostics.record(symbol, "bloqueado", blockers)
                    continue

                passed = check_filters(trend, flow, momentum)
                if not passed:
                    diagnostics.record(symbol, "recusado", "filtros")
                    continue

                if risk.can_enter(symbol):
                    risk.enter(symbol)
                    diagnostics.record(symbol, classification, score)

            await risk.refresh()
            diagnostics.report()

        except Exception as e:
            logger.exception("Erro no ciclo: %s", e)

        await asyncio.sleep(300)
