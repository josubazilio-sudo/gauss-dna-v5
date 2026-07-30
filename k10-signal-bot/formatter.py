"""
K10 Formatter v2 — Cartão institucional enxuto
"""
from datetime import datetime


def formatar_cartao(r: dict) -> str:
    if not r.get("aprovado"):
        return formatar_rejeicao(r)

    symbol   = r["symbol"].replace("/", "")
    direcao  = r["direcao"]
    tf       = r.get("timeframe", "30m")
    score    = r["score"]
    conv     = r["convicção"]
    entrada  = r["entrada"]
    tp1      = r["tp1"]
    stop     = r["stop"]
    rr       = r["rr"]
    regime   = r.get("regime", "—")
    setup    = r.get("setup_nome", "—")
    tend_4h  = r.get("tend_4h", "—")
    tend_1d  = r.get("tend_1d", "—")
    adx      = r.get("adx", 0)
    rsi      = r.get("rsi", 0)
    rvol     = r.get("rvol", 0)
    banca    = r.get("banca", 90.0)
    posicao  = r.get("posicao", 0)
    alavanca = r.get("alavancagem", 10)
    risco    = r.get("risco_usdt", 2.70)

    dir_emoji = "🟢 LONG" if direcao == "LONG" else "🔴 SHORT"

    if score >= 90:
        tier   = "💎 ELITE"
        titulo = "🏆 K10 - MELHOR OPORTUNIDADE DO CICLO"
    elif score >= 80:
        tier   = "⭐ PREMIUM"
        titulo = "✅ K10 - SINAL APROVADO"
    else:
        tier   = "✔️ PADRÃO"
        titulo = "📊 K10 - SINAL CONFIRMADO"

    sep = "━━━━━━━━━━━━━━━━━━━━"

    return (
        f"{titulo}\n\n"
        f"{symbol}\n\n"
        f"{dir_emoji} | {tf} | {tier}\n\n"
        f"⭐ Score: {score} | {conv}\n\n"
        f"{sep}\n\n"
        f"💰 Entrada: {entrada}\n"
        f"🎯 TP1:    {tp1}  (1:1)\n"
        f"🎯 TP2:    {r.get('tp2', '—')}  (1:2)\n"
        f"🎯 TP3:    {r.get('tp3', '—')}  (1:3)\n"
        f"🛑 Stop:   {stop}\n"
        f"⚖️ RR: {rr}\n\n"
        f"{sep}\n\n"
        f"💼 Banca: {banca} USDT\n"
        f"📦 Posição: {posicao} USDT\n"
        f"🚀 Alavancagem: {alavanca}x\n"
        f"⚠️ Risco: {risco} USDT (3%)\n\n"
        f"{sep}\n\n"
        f"📈 Regime: {regime}\n"
        f"🧠 Setup: {setup}\n"
        f"📊 H4: {tend_4h} | D1: {tend_1d}\n\n"
        f"ADX: {adx:.1f} | RSI: {rsi:.1f} | RVOL: {rvol:.2f}\n\n"
        f"{sep}\n\n"
        f"✅ {' • '.join(r.get('confirmacoes', []))}\n\n"
        f"{sep}\n\n"
        f"K10\n\n"
        f"❌ Invalidar se o preço atingir o Stop antes da entrada."
    )


def formatar_rejeicao(r: dict) -> str:
    symbol  = r["symbol"].replace("/", "")
    setup   = r.get("setup_nome", "—")
    regime  = r.get("regime", "—")
    score   = r.get("score", 0)
    sep     = "━━━━━━━━━━━━━━━━━━━━"
    motivos = "\n".join(f"❌ {m}" for m in r.get("motivos_rejeicao", []))
    falta   = "\n".join(f"📌 {f}" for f in r.get("o_que_falta", []))

    return (
        f"❌ K10 — SINAL REJEITADO\n\n"
        f"{symbol}\n\n"
        f"{sep}\n\n"
        f"🔎 Setup: {setup}\n"
        f"🌍 Regime: {regime}\n"
        f"📊 Score: {score}/100\n\n"
        f"{sep}\n\n"
        f"🚫 Motivos:\n\n{motivos}\n\n"
        f"{sep}\n\n"
        f"🔧 O que falta:\n\n{falta}\n\n"
        f"K10"
    )
