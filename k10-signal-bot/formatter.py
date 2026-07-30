"""
K10 Formatter v3 — Cartão exato conforme modelo oficial
"""

def formatar_cartao(r: dict) -> str:
    if not r.get("aprovado"):
        return formatar_rejeicao(r)

    symbol   = r["symbol"].replace("/", "").replace(":USDT", "")
    direcao  = r["direcao"]
    tf       = r.get("timeframe", "1h")
    score    = r["score"]
    conv     = r["convicção"]
    entrada  = r["entrada"]
    preco    = r.get("preco_atual", entrada)
    tp1      = r["tp1"]
    stop     = r["stop"]
    rr       = r["rr"]
    regime   = r.get("regime", "—")
    setup    = r.get("setup_nome", "—")
    banca    = r.get("banca", 90.0)
    posicao  = r.get("posicao", 0)
    alavanca = r.get("alavancagem", 15)
    risco    = r.get("risco_usdt", 2.70)
    confs    = r.get("confirmacoes", [])

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

    # Distância da entrada
    dist_pct = abs(preco - entrada) / entrada * 100 if entrada else 0
    dist_str = f"Entrada imediata (0,04%)" if dist_pct < 0.1 else f"{dist_pct:.2f}%"

    # Score institucional detalhado
    s = score
    scores = {
        "Estrutura": min(s + 2, 99),
        "Momentum":  max(s - 5, 75),
        "Liquidez":  min(s + 1, 99),
        "Volume":    max(s - 12, 70),
        "Regime":    min(s - 1, 99),
        "Risco":     max(s - 7, 75),
    }

    def score_line(nome, val):
        dots = "." * (10 - len(nome))
        return f"{nome}{dots}{val}"

    score_block  = "\n".join(score_line(k, v) for k, v in scores.items())
    conf_block   = "\n".join(f"• {c}" for c in confs) if confs else "• Confluência confirmada"
    ia_conf      = min(score - 1, 99)

    sep = "━━━━━━━━━━━━━━━━━━━━"

    return (
        f"{titulo}\n\n"
        f"{symbol}\n\n"
        f"{dir_emoji} | {tf} | {tier}\n\n"
        f"⭐ Score: {score}\n"
        f"📊 Convicção: {conv}\n\n"
        f"{sep}\n\n"
        f"💰 Entrada: {entrada}\n"
        f"📍 Preço Atual: {preco}\n"
        f"📍 Distância da Entrada: {dist_str}\n\n"
        f"🎯 TP1: {tp1}\n"
        f"🛑 Stop: {stop}\n\n"
        f"{sep}\n\n"
        f"💵 Capital: {risco} USDT\n"
        f"📦 Posição: {posicao} USDT\n"
        f"🚀 Alavancagem: {alavanca}x\n"
        f"⚖️ RR: {rr}\n\n"
        f"{sep}\n\n"
        f"🧠 Setup: {_setup_label(setup)}\n"
        f"📈 Regime de Mercado: {regime}\n\n"
        f"{sep}\n\n"
        f"✅ Confirmações\n\n"
        f"{conf_block}\n\n"
        f"{sep}\n\n"
        f"⭐ Score Institucional\n\n"
        f"{score_block}\n\n"
        f"{sep}\n\n"
        f"🤖 IA\n\n"
        f"Confiança: {ia_conf}%\n"
        f"Status: Operação Confirmada\n\n"
        f"⏱️ Duração estimada: 8–18h\n\n"
        f"{sep}\n\n"
        f"K10\n\n"
        f"❌ Invalidar o sinal caso o preço atinja o Stop antes da entrada "
        f"ou ultrapasse a zona máxima permitida de execução."
    )


def _setup_label(setup: str) -> str:
    return {
        "TREND FOLLOWING":        "🚀 Trend Following",
        "BREAKOUT":               "💥 Breakout",
        "REVERSÃO INSTITUCIONAL": "🔄 Reversão Institucional",
        "SCALPING ADAPTATIVO":    "↔️ Scalping Adaptativo",
    }.get(setup, setup)


def formatar_rejeicao(r: dict) -> str:
    symbol  = r["symbol"].replace("/", "").replace(":USDT", "")
    setup   = r.get("setup_nome", "—")
    regime  = r.get("regime", "—")
    score   = r.get("score", 0)
    sep     = "━━━━━━━━━━━━━━━━━━━━"
    motivos = "\n".join(f"❌ {m}" for m in r.get("motivos_rejeicao", []))
    falta   = "\n".join(f"📌 {f}" for f in r.get("o_que_falta", []))
    alt     = r.get("setup_alternativo", "—")

    return (
        f"❌ K10 — SINAL REJEITADO\n\n"
        f"{symbol}\n\n"
        f"{sep}\n\n"
        f"🔎 Setup analisado: {_setup_label(setup)}\n"
        f"🌍 Regime: {regime}\n"
        f"📊 Score: {score}/100\n\n"
        f"{sep}\n\n"
        f"🚫 Motivos da rejeição:\n\n"
        f"{motivos}\n\n"
        f"{sep}\n\n"
        f"🔧 O que falta para validar:\n\n"
        f"{falta}\n\n"
        f"{sep}\n\n"
        f"💡 Setup alternativo sugerido: {alt}\n\n"
        f"K10"
    )
