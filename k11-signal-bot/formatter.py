"""
K10/K11 Formatter — Cartão final
"""

def formatar_cartao(r: dict, bot_name: str = "K10") -> str:
    if not r.get("aprovado"):
        return None

    symbol  = r["symbol"].replace("/USDT:USDT","").replace("/USDT","")
    direcao = r["direcao"]
    tf      = r.get("timeframe","30m")
    score   = r["score"]
    tier    = r.get("tier","BRONZE")
    entrada = r["entrada"]
    tp1     = r["tp1"]
    stop    = r["stop"]
    rr      = round(abs(tp1 - entrada) / abs(stop - entrada), 2) if stop != entrada else 0
    regime  = r.get("regime","—")
    setup   = r.get("setup_nome","—")
    smc     = r.get("confirmacoes_smc", [])
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
    conv_map = {
        "DIAMANTE": "ELITE 🔥",
        "PLATINA":  "MUITO ALTA 💎",
        "OURO":     "ALTA ✅",
        "PRATA":    "BOA ⚡",
        "BRONZE":   "MODERADA 🔶",
    }
    setup_label = {
        "TREND_FOLLOWING": "Trend Following",
        "RANGE_TRADING":   "Range Trading",
        "BREAKOUT":        "Breakout",
        "MEAN_REVERSION":  "Mean Reversion",
    }.get(setup, setup)

    smc_block = "\n".join(f"✅ {item}" for item in smc) if smc else "✅ Estrutura confirmada"
    sep = "━━━━━━━━━━━━━━"

    return (
        f"🏆 {symbol}\n\n"
        f"{dir_emoji} | {tf} | {tier_map.get(tier,'🥉 BRONZE')}\n\n"
        f"⭐ Score: {score} | {conv_map.get(tier,'MODERADA 🔶')}\n\n"
        f"{sep}\n\n"
        f"💰 Entrada: {entrada}\n"
        f"🎯 TP1: {tp1}\n"
        f"🛑 Stop: {stop}\n"
        f"⚖️ RR: {rr}\n\n"
        f"💵 Banca: {capital} USDT | 🚀 {alav}x\n"
        f"⚠️ Risco: {r.get('risco_usdt', 2.70)} USDT (3%)\n"
        f"📦 Posição: {posicao} USDT\n\n"
        f"{sep}\n\n"
        f"🌍 {regime}\n"
        f"📊 {setup_label} | ⏱️ {duracao}\n\n"
        f"{smc_block}\n\n"
        f"{bot_name}"
    )


def formatar_rejeicao(r: dict) -> str:
    return None
