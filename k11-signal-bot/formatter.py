"""
K10/K11 Formatter — Cartão limpo: Entrada, TP1, Stop
"""
from config import TP1_FRACAO_VOLUME

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
    tp2     = r.get("tp2", tp1)
    be      = r.get("be", "")
    stop    = r["stop"]
    rr      = r.get("rr") if r.get("rr") else round(abs(tp1 - entrada) / abs(stop - entrada), 2) if stop != entrada else 0
    regime  = r.get("regime","—")
    setup   = r.get("setup_nome","—")
    smc     = r.get("confirmacoes_smc", [])
    capital = r.get("capital", 0)
    posicao = r.get("posicao", 0)
    alav    = r.get("alavancagem", 8)
    risco   = r.get("risco_usdt", 2.7)
    duracao = {"30m":"4–8h","1h":"6–12h","4h":"24–48h","1d":"3–7d"}.get(tf,"6–12h")
    prioridade = r.get("prioridade","")

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
        "VIRADA":          "Virada",
    }.get(setup, setup)

    smc_block = "\n".join(f"✅ {item}" for item in smc) if smc else ""
    sep = "━━━━━━━━━━━━━━"
    prioridade_line = f"{prioridade}\n\n" if prioridade else ""

    frac_tp1 = int(round(TP1_FRACAO_VOLUME * 100))
    return (
        f"🏆 {symbol}\n\n"
        f"{prioridade_line}"
        f"{dir_emoji} | {tf} | {tier_map.get(tier,'🥉 BRONZE')}\n\n"
        f"⭐ Score: {score} | {conv_map.get(tier,'MODERADA 🔶')}\n\n"
        f"EQ: {r.get('entry_quality',0)}/100 | EMA21:{r.get('eq_detalhes',{}).get('ema21',0):+d} OB:{r.get('eq_detalhes',{}).get('ob_fvg',0):+d} MACD:{r.get('eq_detalhes',{}).get('timing',0):+d} RSI:{r.get('eq_detalhes',{}).get('rsi',0):+d} BOS:{r.get('eq_detalhes',{}).get('bos',0):+d}\n"
        f"{sep}\n\n"
        f"💰 Entrada: {entrada}\n"
        f"🎯 TP1: {tp1} (parcial {frac_tp1}%)\n"
        f"🎯 TP2: {tp2}\n"
        f"⚡ BE em: {be}\n"
        f"🛑 Stop: {stop}\n"
        f"⚖️ RR: {rr}\n\n"
        f"💵 Banca: {capital} USDT | 🚀 {alav}x\n"
        f"⚠️ Risco: {risco} USDT (3%)\n"
        f"📦 Posição: {posicao} USDT\n\n"
        f"{sep}\n\n"
        f"🌍 {regime}\n"
        f"📊 {setup_label} | ⏱️ {duracao}\n\n"
        f"{smc_block + chr(10) + chr(10) if smc_block else ''}"
        f"{bot_name}"
    )

def formatar_rejeicao(r: dict) -> str:
    return None
