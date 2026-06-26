"""
Teste multi-timeframe: baixa 20+ pares em 15m, 1h, 4h e mostra resultados.
"""
import asyncio, sys
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
    "PESO_VOLATILIDADE": 5, "PESO_MULTI_TIMEFRAME": 10,
    "PESO_CONFIANCA": 10, "PESO_ATIVO": 5,
}

TIMEFRAMES = ["15m", "1h", "4h"]


def analisar_tf(candles, tf):
    market = classify_market(candles)
    trend = analyze_trend(candles)
    smc = detect_smc(candles)
    flow = analyze_flow(candles)
    momentum = analyze_momentum(candles)
    return {"MARKET": market, "TREND": trend, "SMC": smc, "FLOW": flow, "MOMENTUM": momentum}


def calc_mtf_bonus(analises):
    bonus = 0
    direcoes = []
    for tf, d in analises.items():
        direcoes.append(d["TREND"].get("DIRECAO", ""))
    nao_neutras = [d for d in direcoes if d != "lateral"]
    if len(nao_neutras) >= 2 and all(d == nao_neutras[0] for d in nao_neutras):
        bonus = 15
    elif len(nao_neutras) >= 1:
        bonus = 5
    return bonus


async def main():
    print("=== GAUSS DNA V5 — TEST MULTI-TIMEFRAME ===\n")
    data = await scan_market(top_n=50, timeframes=TIMEFRAMES)
    print(f"Scan: {len(data)} pares carregados (3 TFs cada)\n")

    resultados = []
    for symbol, tf_data in data.items():
        analises = {}
        ok = True
        for tf in TIMEFRAMES:
            candles = tf_data.get(tf, [])
            if len(candles) < 50:
                ok = False
                break
            analises[tf] = analisar_tf(candles, tf)

        if not ok:
            continue

        op = analises["15m"]
        conf = analises["1h"]

        mtf_bonus = calc_mtf_bonus(analises)

        v = empty_schema()
        v["SYMBOL"] = symbol
        v.update(op["MARKET"])
        v.update(op["TREND"])
        v.update(op["SMC"])
        v.update(op["FLOW"])
        v.update(op["MOMENTUM"])

        blockers = check_blockers(v, op["MARKET"], op["FLOW"], op["MOMENTUM"], op["TREND"])
        v.update(blockers)

        if blockers.get("PARAR_OPERACOES"):
            resultados.append((symbol, "BLOQ", 0, "parar", "", 0, 0, 0, "", 0, ""))
            continue

        passed, filter_result = check_filters(
            v, op["TREND"], op["FLOW"], op["MOMENTUM"], op["MARKET"], op["SMC"]
        )
        v.update(filter_result)

        score_data = calculate_score(
            ADAPTIVE_WEIGHTS, op["TREND"], op["FLOW"], op["SMC"],
            op["MOMENTUM"], op["MARKET"],
            mtf_bonus=mtf_bonus,
        )
        v.update(score_data)

        classification = classify_signal(score_data["SCORE_TOTAL"])
        v.update(classification)

        status = classification.get("CLASSIFICACAO_FINAL", "") or "RECUS"
        motivo = v.get("MOTIVO_RECUSA", "")
        score_t = score_data["SCORE_TOTAL"]
        tend = op["TREND"].get("TENDENCIA", "")
        direcao = op["TREND"].get("DIRECAO", "")
        rvol = op["FLOW"].get("RVOL", 0)
        rsi = op["MOMENTUM"].get("RSI", 0)
        adx = op["MOMENTUM"].get("ADX", 0)
        estado = op["MARKET"].get("ESTADO_MERCADO", "")

        resultados.append((symbol, status, score_t, motivo, direcao.upper(), rvol, rsi, adx, tend[:10], mtf_bonus, estado))

    # Print
    print(f"{'SYMBOL':<12} {'ST':<6} {'SCR':<4} {'RVOL':<5} {'RSI':<5} {'ADX':<5} {'DIR':<6} {'TEND':<12} {'MTF':<4} {'ESTADO':<16}")
    print("-" * 85)
    for r in sorted(resultados, key=lambda r: r[2], reverse=True):
        s, st, sc, obs, d, rv, rsi_val, adx_val, tend, mtf, estado = r
        print(f"{s:<12} {st:<6} {sc:<4} {rv:<5.1f} {rsi_val:<5.0f} {adx_val:<5.0f} {d:<6} {tend:<12} +{mtf:<2} {estado:<16}")

    aprov = [r for r in resultados if r[1] in ("OURO", "PRATA", "BRONZE")]
    rec = [r for r in resultados if r[1] == "RECUS"]
    blq = [r for r in resultados if r[1] == "BLOQ"]
    print(f"\nAprovados: {len(aprov)} | Recusados: {len(rec)} | Bloqueados: {len(blq)}")


if __name__ == "__main__":
    asyncio.run(main())
