"""
K10 Formatter — Modo Adaptativo Institucional V1.0
"""

def formatar_cartao(r: dict) -> str:
    if not r.get("aprovado"):
        return formatar_rejeicao(r)

    symbol  = r["symbol"].replace("/USDT:USDT","").replace("/USDT","")
    direcao = r["direcao"]
    tf      = r.get("timeframe","30m")
    score   = r["score"]
    tier    = r.get("tier","BRONZE")
    entrada = r["entrada"]
    tp1     = r["tp1"]
    tp2     = r["tp2"]
    stop    = r["stop"]
    rr      = r["rr"]
    regime  = r.get("regime","—")
    setup   = r.get("setup_nome","—")
    rsi     = r.get("rsi",0)
    adx     = r.get("adx",0)
    rvol    = r.get("rvol",0)
    vwap_v  = r.get("vwap",entrada)
    macd_h  = r.get("macd_hist",0)
    smc     = r.get("confirmacoes_smc",[])
    dist    = r.get("dist_entrada","—")
    convicc = r.get("conviccao","—")

    dir_emoji = "🟢" if direcao=="LONG" else "🔴"

    tier_map = {
        "DIAMANTE": "💎 DIAMANTE",
        "PLATINA":  "🏅 PLATINA",
        "OURO":     "🥇 OURO",
        "PRATA":    "🥈 PRATA",
        "BRONZE":   "🥉 BRONZE",
        "ABAIXO":   "⚪ BRONZE",
    }
    tier_label = tier_map.get(tier,"🥉 BRONZE")

    setup_label = {
        "TREND_FOLLOWING": "Trend Following",
        "RANGE_TRADING":   "Range Trading",
        "BREAKOUT":        "Breakout",
        "MEAN_REVERSION":  "Mean Reversion",
    }.get(setup, setup)

    dist_emoji = {"EXCELENTE":"🟢","BOA":"🟡","ACEITÁVEL":"🟠","RUIM":"🔴"}.get(dist,"⚪")

    rsi_ok   = "✅" if 30 <= rsi <= 70 else "⚠️"
    adx_ok   = "✅" if adx >= 20 else "⚠️"
    rvol_ok  = "✅" if rvol >= 1.0 else "⚠️"
    # MACD: em Range/Lateral, perto de zero é normal — só alerta se muito contra
    if "Range" in setup or "Reversion" in setup:
        macd_ok = "✅" if abs(macd_h) < abs(macd_h)*2 + 0.0001 else "⚠️"
        macd_ok = "✅"  # em range, MACD neutro é esperado
    else:
        macd_ok = "✅" if (macd_h>0 and direcao=="LONG") or (macd_h<0 and direcao=="SHORT") else "⚠️"
    vwap_pos = "Acima ✅" if (entrada>vwap_v and direcao=="LONG") or (entrada<vwap_v and direcao=="SHORT") else "Abaixo ⚠️"

    smc_items = ["BOS","CHoCH","Order Block","FVG","Liquidity Sweep","Reteste EMA21","Breaker Block"]
    smc_block = "\n".join(f"{'✅' if item in smc else '—'} {item}" for item in smc_items)

    duracao = {"30m":"4–8h","1h":"6–12h","4h":"24–48h","1d":"3–7d"}.get(tf,"6–12h")
    sep = "━━━━━━━━━━━━━━"

    return (
        f"🏆 K10\n\n"
        f"{symbol}\n\n"
        f"{dir_emoji} {direcao} | {tf} | {tier_label}\n\n"
        f"⭐ Score: {score}\n"
        f"🤖 Convicção: {convicc}\n\n"
        f"{sep}\n\n"
        f"💰 Entrada: {entrada}\n"
        f"🎯 TP1: {tp1}\n"
        f"🎯 TP2: {tp2}\n"
        f"🛑 Stop: {stop}\n"
        f"⚖️ RR: {rr}\n\n"
        f"{sep}\n\n"
        f"📍 Distância: {dist_emoji} {dist}\n"
        f"🌍 Regime: {regime}\n"
        f"📊 Setup: {setup_label}\n"
        f"⏱️ Duração: {duracao}\n\n"
        f"{sep}\n\n"
        f"{smc_label}\n\n"
        f"{smc_block}\n\n"
        f"{sep}\n\n"
        f"Indicadores\n\n"
        f"RSI: {rsi:.0f} {rsi_ok}\n"
        f"ADX: {adx:.0f} {adx_ok}\n"
        f"RVOL: {rvol:.2f} {rvol_ok}\n"
        f"MACD: {macd_status}\n"
        f"VWAP: {vwap_pos}\n\n"
        f"{sep}\n\n"
        f"INVALIDAR\n\n"
        f"❌ Stop atingido antes da entrada\n"
        f"❌ Preço percorreu >30% até TP1\n"
        f"❌ Volume desaparece\n"
        f"❌ Estrutura SMC invalidada\n\n"
        f"{sep}\n\n"
        f"K10 | Adaptativo Institucional"
    )


def formatar_rejeicao(r: dict) -> str:
    symbol  = r["symbol"].replace("/USDT:USDT","").replace("/USDT","")
    score   = r.get("score",0)
    regime  = r.get("regime","—")
    motivos = "\n".join(f"❌ {m}" for m in r.get("motivos_rejeicao",[]))
    sep     = "━━━━━━━━━━━━━━"
    return (
        f"🔴 REJEITADO\n\n"
        f"{symbol}\n\n"
        f"{sep}\n\n"
        f"Score: {score} | Regime: {regime}\n\n"
        f"{sep}\n\n"
        f"{motivos}\n\n"
        f"{sep}\n\n"
        f"K10 | Adaptativo Institucional"
    )
