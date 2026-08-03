"""
K10/K11 Formatter — Cartão limpo, só informações aprovadas
"""

def formatar_cartao(r: dict, bot_name: str = "K10") -> str:
    if not r.get("aprovado"):
        return None  # Não formatar rejeitados

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
    rsi     = r.get("rsi", 0)
    adx     = r.get("adx", 0)
    rvol    = r.get("rvol", 0)
    smc     = r.get("confirmacoes_smc", [])
    banca   = r.get("banca", 90)
    capital = r.get("capital", 0)
    posicao = r.get("posicao", 0)
    alav    = r.get("alavancagem", 8)
    duracao = {"30m":"4–8h","1h":"6–12h","4h":"24–48h","1d":"3–7d"}.get(tf,"6–12h")

    dir_emoji = "🟢 LONG" if direcao == "LONG" else "🔴 SHORT"

    tier_map = {
        "DIAMANTE": "💎 DIAMANTE",
        "PLATINA":  "🏅 PLATINA",
        "OURO":     "🥇 OURO",
        "PRATA":    "🥈 PRATA",
        "BRONZE":   "🥉 BRONZE",
    }
    tier_label = tier_map.get(tier, "🥉 BRONZE")

    conv_map = {
        "DIAMANTE": "ELITE 🔥",
        "PLATINA":  "MUITO ALTA 💎",
        "OURO":     "ALTA ✅",
        "PRATA":    "BOA ⚡",
        "BRONZE":   "MODERADA 🔶",
    }
    convicc = conv_map.get(tier, "MODERADA 🔶")

    setup_label = {
        "TREND_FOLLOWING": "Trend Following",
        "RANGE_TRADING":   "Range Trading",
        "BREAKOUT":        "Breakout",
        "MEAN_REVERSION":  "Mean Reversion",
    }.get(setup, setup)

    # Só confirmações SMC aprovadas
    smc_block = "\n".join(f"✅ {item}" for item in smc) if smc else "✅ Estrutura confirmada"

    sep = "━━━━━━━━━━━━━━"

    return (
        f"🏆 {bot_name}\n\n"
        f"{symbol}\n\n"
        f"{dir_emoji} | {tf} | {tier_label}\n\n"
        f"⭐ Score: {score}\n"
        f"🤖 Convicção: {convicc}\n\n"
        f"{sep}\n\n"
        f"💰 Entrada: {entrada}\n"
        f"🎯 TP1: {tp1}\n"
        f"🎯 TP2: {tp2}\n"
        f"🛑 Stop: {stop}\n"
        f"⚖️ RR: {rr}\n\n"
        f"{sep}\n\n"
        f"🌍 {regime} | 📊 {setup_label}\n"
        f"⏱️ {duracao}\n\n"
        f"{sep}\n\n"
        f"📊 RSI: {rsi:.0f} | ADX: {adx:.0f} | RVOL: {rvol:.2f}\n\n"
        f"{smc_block}\n\n"
        f"{sep}\n\n"
        f"💵 Capital: {capital} USDT | {alav}x\n"
        f"📦 Posição: {posicao} USDT\n\n"
        f"{sep}\n\n"
        f"❌ Invalidar se stop atingido\n"
        f"❌ Invalidar se preço >30% do TP1\n\n"
        f"{bot_name} | Adaptativo Institucional"
    )


def formatar_rejeicao(r: dict) -> str:
    return None  # Rejeitados não geram cartão
