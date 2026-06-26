"""
Teste rápido: baixa 20+ pares da MEXC e mostra resultados completos.
Não envia Telegram.
"""
import asyncio, json, sys
sys.path.insert(0, "src")

from modules.scanner import scan_market
from market import classify_market
from trend import analyze_trend
from smart_money import detect_smc
from flow import analyze_flow
from momentum import analyze_momentum
from score import calculate_score, classify_signal
from filters import check_filters, check_blockers
from schema.variables import empty_schema

ADAPTIVE_WEIGHTS = {
    "PESO_TENDENCIA": 20, "PESO_FLUXO": 20, "PESO_VOLUME": 10,
    "PESO_LIQUIDEZ": 15, "PESO_ESTRUTURA": 20, "PESO_MOMENTUM": 10,
    "PESO_VOLATILIDADE": 5, "PESO_MULTI_TIMEFRAME": 5,
    "PESO_CONFIANCA": 10, "PESO_ATIVO": 5,
}

async def main():
    print("=== GAUSS DNA V5 — TEST CYCLE ===\n")
    data = await scan_market(top_n=30, timeframe="1h")
    print(f"Scan: {len(data)} pares carregados\n")

    resultados = []
    for symbol, candles in data.items():
        v = empty_schema()
        v["SYMBOL"] = symbol

        market_state = classify_market(candles)
        trend_data = analyze_trend(candles)
        smc_data = detect_smc(candles)
        flow_data = analyze_flow(candles)
        momentum_data = analyze_momentum(candles)

        v.update(market_state)
        v.update(trend_data)
        v.update(smc_data)
        v.update(flow_data)
        v.update(momentum_data)

        blockers = check_blockers(v, market_state, flow_data, momentum_data, trend_data)
        v.update(blockers)

        if blockers.get("PARAR_OPERACOES"):
            resultados.append((symbol, "BLOQ", 0, "parar", "", 0, 0, 0, ""))
            continue

        passed, filter_result = check_filters(
            v, trend_data, flow_data, momentum_data, market_state, smc_data
        )
        v.update(filter_result)

        score_data = calculate_score(
            ADAPTIVE_WEIGHTS, trend_data, flow_data, smc_data, momentum_data, market_state
        )
        v.update(score_data)

        classification = classify_signal(score_data["SCORE_TOTAL"])
        v.update(classification)

        status = classification.get("CLASSIFICACAO_FINAL", "") or "RECUS"
        motivo = v.get("MOTIVO_RECUSA", "")
        score_t = score_data["SCORE_TOTAL"]
        tend = trend_data.get("TENDENCIA", "")
        direcao = trend_data.get("DIRECAO", "")
        rvol = flow_data.get("RVOL", 0)
        rsi = momentum_data.get("RSI", 0)
        adx = momentum_data.get("ADX", 0)

        resultados.append((symbol, status, score_t, motivo, direcao.upper(), rvol, rsi, adx, tend))

    # Print header
    print(f"{'SYMBOL':<12} {'STATUS':<6} {'SCR':<4} {'RVOL':<6} {'RSI':<5} {'ADX':<5} {'DIR':<7} {'TENDENCIA':<18} {'OBS'}")
    print("-" * 80)
    for s, st, sc, obs, direcao, rvol, rsi, adx, tend in sorted(resultados, key=lambda r: r[2], reverse=True):
        print(f"{s:<12} {st:<6} {sc:<4} {rvol:<6.1f} {rsi:<5.0f} {adx:<5.0f} {direcao:<7} {tend:<18} {obs}")

    # Stats
    aprovados = [r for r in resultados if r[1] in ("OURO", "PRATA", "BRONZE")]
    recusados = [r for r in resultados if r[1] == "RECUS"]
    print(f"\nAprovados: {len(aprovados)} | Recusados: {len(recusados)} | Bloqueados: {len([r for r in resultados if r[1]=='BLOQ'])}")


if __name__ == "__main__":
    asyncio.run(main())
