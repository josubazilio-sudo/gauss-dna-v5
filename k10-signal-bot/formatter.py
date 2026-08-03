"""
K10 Formatter V11 — Cartão otimizado RFC V11
"""

def formatar_cartao(r: dict) -> str:
    if not r.get("aprovado"):
        return formatar_rejeicao(r)

    symbol  = r["symbol"].replace("/", "").replace(":USDT", "")
    direcao = r["direcao"]
    tf      = r.get("timeframe", "30m")
    score   = r["score"]
    entrada = r["entrada"]
    preco   = r.get("preco_atual", entrada)
    tp1     = r["tp1"]
    tp2     = r.get("tp2", tp1)
    stop    = r["stop"]
    rr      = r["rr"]
    regime  = r.get("regime", "—")
    setup   = r.get("setup_nome", "—")
    rsi     = r.get("rsi", 0)
    adx     = r.get("adx", 0)
    rvol    = r.get("rvol", 0)
    cmo     = r.get("cmo", 0)
    vwap_v  = r.get("vwap", preco)
    ema10   = r.get("ema10", preco)
    ema21   = r.get("ema21", preco)
    ema50   = r.get("ema50", preco)
    atr     = r.get("atr", 0)
    convicc = r.get("conviccao", "—")
    tend_4h = r.get("tend_4h", "—")
    tend_1d = r.get("tend_1d", "—")
    exaustao = r.get("exaustao", "Nenhuma")
    smc_confs = r.get("confirmacoes_smc", [])
    v11_confs = r.get("confirmacoes_v11", [])

    dir_emoji = "🟢" if direcao == "LONG" else "🔴"

    tier_raw = r.get("tier", "BRONZE")
    tier_map = {
        "DIAMANTE": "💎 DIAMANTE",
        "OURO":     "🥇 OURO",
        "PRATA":    "🥈 PRATA",
        "BRONZE":   "🥉 BRONZE",
    }
    tier_label = tier_map.get(tier_raw, "🥉 BRONZE")

    dist_pct = abs(preco - entrada) / entrada * 100 if entrada else 0
    duracao  = {"30m":"4–8h","1h":"6–12h","4h":"24–48h","1d":"3–7d"}.get(tf, "6–12h")

    # Tendência label
    tend_label = {
        "ALTA":  "Alta Forte ↑",
        "BAIXA": "Baixa Forte ↓",
        "NEUTRA":"Lateral →"
    }.get(tend_4h, tend_4h)

    # Setup label
    setup_label = {
        "TREND FOLLOWING":        "Trend Following",
        "BREAKOUT":               "Breakout Institucional",
        "REVERSÃO INSTITUCIONAL": "Reversão SMC",
        "SCALPING ADAPTATIVO":    "Scalping",
    }.get(setup, setup)

    # Indicadores com status
    rsi_status  = "✅" if 32 <= rsi <= 68 else "⚠️"
    adx_status  = "✅" if adx >= 20 else "⚠️"
    rvol_status = "✅" if rvol >= 1.2 else "⚠️"
    macd_hist   = r.get("macd_hist", 0)
    macd_label  = "Cruzando ✅" if abs(macd_hist) < abs(macd_hist) * 1.5 + 0.0001 else ("Alta ✅" if macd_hist > 0 and direcao=="LONG" else "Baixa ✅" if macd_hist < 0 and direcao=="SHORT" else "⚠️")
    macd_status = "✅" if (macd_hist > 0 and direcao=="LONG") or (macd_hist < 0 and direcao=="SHORT") else "⚠️"
    vwap_status = "✅" if (preco > vwap_v and direcao=="LONG") or (preco < vwap_v and direcao=="SHORT") else "⚠️"
    vwap_pos    = "Acima" if preco > vwap_v else "Abaixo"
    atr_status  = "✅" if atr / preco * 100 < 3 else "⚠️"
    atr_label   = "Normal" if atr / preco * 100 < 2 else "Elevado"
    ema_alinha  = "✅" if (ema10>ema21>ema50 and direcao=="LONG") or (ema10<ema21<ema50 and direcao=="SHORT") else "⚠️"

    # SMC confirmações
    smc_items = ["Estrutura","BOS","CHoCH","Order Block","FVG","Liquidez","Reteste"]
    smc_block = "\n".join(
        f"{'✅' if item in smc_confs or item == 'Estrutura' else '—'} {item}"
        for item in smc_items
    )

    # Probabilidade / fase
    prob_label = "🟢 Início do movimento"
    if rsi > 60 and direcao == "LONG":   prob_label = "🟡 Meio do movimento"
    if rsi > 68 and direcao == "LONG":   prob_label = "🔴 Possível exaustão"
    if rsi < 40 and direcao == "SHORT":  prob_label = "🟡 Meio do movimento"
    if rsi < 32 and direcao == "SHORT":  prob_label = "🔴 Possível exaustão"

    confianca = round(score * 0.87, 1)

    sep = "━━━━━━━━━━━━━━"

    return (
        f"🏆 K10\n\n"
        f"{symbol}\n\n"
        f"{dir_emoji} {direcao} | {tf} | {tier_label}\n\n"
        f"⭐ Score: {score}\n"
        f"🤖 IA: {confianca}%\n\n"
        f"{sep}\n\n"
        f"💰 Entrada\n{entrada}\n\n"
        f"📍 Atual\n{preco}\n\n"
        f"📏 Distância\n{dist_pct:.2f}%\n\n"
        f"🎯 TP1\n{tp1}\n\n"
        f"🎯 TP2\n{tp2}\n\n"
        f"🛑 Stop\n{stop}\n\n"
        f"RR {rr}\n\n"
        f"{sep}\n\n"
        f"📈 Tendência\n{tend_label}\n\n"
        f"📊 Setup\n{setup_label}\n\n"
        f"{sep}\n\n"
        + smc_block + "\n\n"
        f"{sep}\n\n"
        f"Indicadores\n\n"
        f"RSI: {rsi:.0f} {rsi_status}\n"
        f"MACD: {'Cruzando ✅' if abs(macd_hist) < 0.001 else ('Alta ✅' if macd_hist > 0 and direcao=='LONG' else 'Baixa ✅' if macd_hist < 0 and direcao=='SHORT' else '⚠️')}\n"
        f"ADX: {adx:.0f} {adx_status}\n"
        f"RVOL: {rvol:.2f} {rvol_status}\n"
        f"VWAP: {vwap_pos} {vwap_status}\n"
        f"ATR: {atr_label} {atr_status}\n"
        f"EMA10>21>50 {ema_alinha}\n\n"
        f"{sep}\n\n"
        f"⚠️ Exaustão\n{exaustao}\n\n"
        f"{sep}\n\n"
        f"Probabilidade\n\n"
        f"{prob_label}\n\n"
        f"Confiança: {confianca}%\n"
        f"Tempo esperado: {duracao}\n\n"
        f"{sep}\n\n"
        f"INVALIDAR\n\n"
        f"❌ Stop antes da entrada\n"
        f"❌ Distância >0.35 ATR\n"
        f"❌ Perda da VWAP\n"
        f"❌ Volume diminuir\n"
        f"❌ Estrutura perder BOS/CHoCH\n"
        f"❌ RSI entrar em exaustão\n\n"
        f"{sep}\n\n"
        f"K10"
    )


def formatar_rejeicao(r: dict) -> str:
    symbol  = r["symbol"].replace("/", "").replace(":USDT", "")
    score   = r.get("score", 0)
    sep     = "━━━━━━━━━━━━━━"
    motivos = "\n".join(f"❌ {m}" for m in r.get("motivos_rejeicao", []))
    falta   = "\n".join(f"📌 {f}" for f in r.get("o_que_falta", []))

    return (
        f"🔴 REJEITADO\n\n"
        f"{symbol}\n\n"
        f"{sep}\n\n"
        f"Score: {score}\n\n"
        f"{sep}\n\n"
        f"Motivos:\n\n{motivos}\n\n"
        f"{sep}\n\n"
        f"O que falta:\n\n{falta}\n\n"
        f"{sep}\n\n"
        f"K10"
    )
