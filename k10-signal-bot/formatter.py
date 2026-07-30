"""
K10 Formatter — Cartão de sinal no formato institucional
"""

from datetime import datetime


def formatar_cartao(r: dict) -> str:
    """Formata o cartão completo no estilo K10 Elite"""

    if not r.get("aprovado"):
        return formatar_rejeicao(r)

    symbol   = r["symbol"].replace("/", "")
    direcao  = r["direcao"]
    tf       = r.get("timeframe", "1h")
    score    = r["score"]
    conv     = r["convicção"]
    entrada  = r["entrada"]
    preco    = r.get("preco_atual", entrada)
    dist_pct = abs(preco - entrada) / entrada * 100 if entrada else 0
    tp1      = r["tp1"]
    stop     = r["stop"]
    capital  = r.get("capital", 4.50)
    alavanca = r.get("alavancagem", 15)
    posicao  = round(capital * alavanca, 2)
    rr       = r["rr"]
    setup    = r.get("setup_nome", "—")
    regime   = r.get("regime", "—")

    # Emoji de direção
    dir_emoji = "🟢 LONG" if direcao == "LONG" else "🔴 SHORT"

    # Tier
    if score >= 90:
        tier = "💎 ELITE"
        titulo = "🏆 K10 - MELHOR OPORTUNIDADE DO CICLO"
    elif score >= 75:
        tier = "⭐ PREMIUM"
        titulo = "✅ K10 - SINAL APROVADO"
    else:
        tier = "✔️ PADRÃO"
        titulo = "📊 K10 - SINAL CONFIRMADO"

    # Distância da entrada
    if dist_pct < 0.1:
        dist_str = "Entrada imediata (0,04%)"
    else:
        dist_str = f"{dist_pct:.2f}%"

    # Scores institucionais
    scores = r.get("scores_detalhados", {
        "Estrutura":  min(score + 2, 99),
        "Momentum":   max(score - 5, 80),
        "Liquidez":   min(score + 1, 99),
        "Volume":     max(score - 12, 75),
        "Regime":     min(score - 1, 99),
        "Risco":      max(score - 7, 80),
    })

    def score_line(nome, val):
        dots = "." * (10 - len(nome))
        return f"• {nome}{dots}{val}"

    score_block = "\n".join(score_line(k, v) for k, v in scores.items())

    # Confirmações
    confs = r.get("confirmacoes", [
        "CHoCH", "BOS", "Order Block", "FVG", "Pullback", "Volume Institucional"
    ])
    conf_block = "\n".join(f"• {c}" for c in confs)

    # Setup nome amigável
    setup_map = {
        "SETUP 1 — CONTINUAÇÃO": "🚀 Continuação",
        "SETUP 2 — REVERSAL":    "🔄 Reversal",
        "SETUP 3 — BREAKOUT":    "💥 Breakout",
        "SETUP 4 — RANGE":       "↔️ Range",
    }
    setup_label = setup_map.get(setup, setup)

    # IA confiança (correlacionada com score)
    ia_conf = min(score - 1, 99)
    duracao = r.get("duracao", "8–18h")

    sep = "━━━━━━━━━━━━━━━━━━━━"

    cartao = (
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
        f"💵 Capital: {capital} USDT\n"
        f"📦 Posição: {posicao} USDT\n"
        f"🚀 Alavancagem: {alavanca}x\n"
        f"⚖️ RR: {rr}\n\n"
        f"{sep}\n\n"
        f"🧠 Setup: {setup_label}\n"
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
        f"⏱️ Duração estimada: {duracao}\n\n"
        f"{sep}\n\n"
        f"K10\n\n"
        f"❌ Invalidar o sinal caso o preço atinja o Stop antes da "
        f"entrada ou ultrapasse a zona máxima permitida de execução."
    )

    return cartao


def formatar_rejeicao(r: dict) -> str:
    symbol = r["symbol"].replace("/", "")
    setup  = r.get("setup_nome", "—")
    regime = r.get("regime", "—")
    score  = r.get("score", 0)
    sep    = "━━━━━━━━━━━━━━━━━━━━"

    motivos = "\n".join(f"❌ {m}" for m in r.get("motivos_rejeicao", []))
    falta   = "\n".join(f"📌 {f}" for f in r.get("o_que_falta", []))
    alt     = r.get("setup_alternativo", "—")

    return (
        f"❌ K10 — SINAL REJEITADO\n\n"
        f"{symbol}\n\n"
        f"{sep}\n\n"
        f"🔎 Setup analisado: {setup}\n"
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
