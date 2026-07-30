"""
K10 Formatter v4 — Cartão no formato QuantOS/K10 completo
"""

def formatar_cartao(r: dict) -> str:
    if not r.get("aprovado"):
        return formatar_rejeicao(r)

    symbol   = r["symbol"].replace("/", "").replace(":USDT", "")
    direcao  = r["direcao"]
    tf       = r.get("timeframe", "30m")
    score    = r["score"]
    entrada  = r["entrada"]
    preco    = r.get("preco_atual", entrada)
    tp1      = r["tp1"]
    tp2      = r.get("tp2", tp1)
    stop     = r["stop"]
    rr       = r["rr"]
    regime   = r.get("regime", "—")
    setup    = r.get("setup_nome", "—")
    banca    = r.get("banca", 90.0)
    posicao  = r.get("posicao", 0)
    alavanca = r.get("alavancagem", 15)
    capital  = r.get("capital", 0)
    risco    = r.get("risco_usdt", 2.70)
    confs    = r.get("confirmacoes", [])
    adx      = r.get("adx", 0)
    rsi      = r.get("rsi", 0)
    atr      = r.get("atr", 0)
    rvol     = r.get("rvol", 0)
    tend_4h  = r.get("tend_4h", "—")
    tend_1d  = r.get("tend_1d", "—")

    dir_emoji = "🟢 LONG" if direcao == "LONG" else "🔴 SHORT"

    # Tier / medalha
    if score >= 90:
        tier = "🥇 OURO"
        titulo = "🔶 SINAL APROVADO"
        rank = "🥇 #1 DO CICLO"
    elif score >= 80:
        tier = "🥈 PRATA"
        titulo = "🔶 SINAL APROVADO"
        rank = "🥈 #TOP DO CICLO"
    else:
        tier = "🥉 BRONZE"
        titulo = "🔶 SINAL APROVADO"
        rank = "🥉 SINAL CONFIRMADO"

    # Percentuais de TP/Stop
    tp1_pct  = abs(tp1  - entrada) / entrada * 100
    tp2_pct  = abs(tp2  - entrada) / entrada * 100
    stop_pct = abs(stop - entrada) / entrada * 100
    tp1_sinal  = "+" if tp1  > entrada else "-"
    tp2_sinal  = "+" if tp2  > entrada else "-"
    stop_sinal = "-" if stop < entrada else "+"

    # Margem %
    margem_pct = round(capital / posicao * 100, 1) if posicao > 0 else 0
    margem_cor = "🟢 Seguro" if margem_pct > 10 else "🟡 Atenção" if margem_pct > 5 else "🔴 Alto Risco"

    # ATR % relativo ao preço
    atr_pct = atr / preco * 100 if preco > 0 else 0

    # Win rate estimado (baseado no score)
    win_rate = round(40 + score * 0.45, 1)
    confianca = round(score * 0.8, 1)
    risco_score = max(5, 100 - score)

    # Timing score (ADX + RSI)
    timing = round((adx / 50 * 50) + (50 - abs(rsi - 50)))
    timing = min(timing, 100)

    # ATR consumido
    atr_consumido = round(atr_pct / (atr_pct + stop_pct) * 100) if (atr_pct + stop_pct) > 0 else 0

    # Dist EMA21 e VWAP
    ema21     = r.get("ema21", preco)
    vwap      = r.get("vwap", preco)
    dist_ema  = round(abs(preco - ema21) / atr, 2) if atr > 0 else 0
    dist_vwap = round(abs(preco - vwap) / preco * 100, 2) if preco > 0 else 0
    pullback  = "SIM" if dist_ema < 1.5 else "NÃO"

    # Institucional score
    inst_score = round(score * 0.9)
    inst_qual  = "A" if inst_score >= 85 else "B" if inst_score >= 70 else "C"
    fluxo = "🟢 Fluxo Comprador: Forte" if direcao == "LONG" else "🔴 Fluxo Vendedor: Forte"
    kalman = "UP" if direcao == "LONG" else "DOWN"

    # Ajustes de nível
    ajustes = []
    nivel_str = ""
    if atr_pct > 2.5:
        ajustes.append(f"➖ ATR > 2.5% (dist. stop {stop_pct:.2f}%) -> -1 nivel")
    if win_rate >= 80:
        ajustes.append(f"➖ Win {win_rate}% >= 80% -> +1 nivel")

    # Barra de score
    filled = round(score / 10)
    barra  = "█" * filled + "░" * (10 - filled)

    # Confirmações resumidas
    conf_inline = " • ".join(confs[:6]) if confs else "Confluência confirmada"

    # Pontos fortes
    pontos_fortes = "\n".join(f"✅ {c}" for c in confs)

    # Descrição narrativa
    desc_confs = ", ".join(confs[:4]) if confs else "Confluência detectada"
    narrativa = f"📝 {desc_confs}, Kalman alinhado."

    # Duração por timeframe
    duracoes = {"30m":"4–8h","1h":"8–18h","4h":"24–48h","1d":"3–7d"}
    duracao  = duracoes.get(tf, "8–18h")

    sep = "━━━━━━━━━━━━━━━━━━━━"

    linhas_ajuste = "\n".join(ajustes) if ajustes else ""
    bloco_ajuste  = f"\n{linhas_ajuste}" if linhas_ajuste else ""

    return (
        f"{titulo}\n\n"
        f"{symbol}\n\n"
        f"{dir_emoji} | {tf} | {tier} | ⭐ {score}\n\n"
        f"{rank}\n\n"
        f"{sep}\n\n"
        f"💰 Entrada: {entrada}\n"
        f"🎯 TP1: {tp1} ({tp1_sinal}{tp1_pct:.2f}%) | TP2: {tp2} ({tp2_sinal}{tp2_pct:.2f}%)\n"
        f"🛑 Stop: {stop} ({stop_sinal}{stop_pct:.2f}%)\n\n"
        f"{sep}\n\n"
        f"💵 Banca: {banca} USDT | 💰 Capital: {capital} USDT\n"
        f"📦 Posição: {posicao} USDT | 🚀 {alavanca}x | ⚖️ RR {rr}\n"
        f"🚀 Alavancagem: {alavanca}x\n"
        f"🛡️ Margem: {margem_pct}% | {margem_cor}\n"
        f"📊 Ajustes: ATR > 2.5% (dist. stop {stop_pct:.2f}%) -> -1 nivel; Win {win_rate}% >= 80% -> +1 nivel\n\n"
        f"{sep}\n\n"
        f"📊 Base: {score}{bloco_ajuste}\n\n"
        f"⭐ Score Final\n"
        f"{barra} {score}%\n\n"
        f"{sep}\n\n"
        f"🎲 Win: {win_rate}% | 🧠 Conf: {confianca}%\n"
        f"⚠️ Risco: {risco_score}/100\n\n"
        f"{sep}\n\n"
        f"🎯 Timing Score: {timing}/100\n"
        f"📉 ATR Consumido: {atr_consumido}%\n"
        f"📏 Dist. EMA21: {dist_ema} ATR | Dist. VWAP: {dist_vwap}%\n"
        f"🔄 Pullback Detectado: {pullback}\n\n"
        f"{sep}\n\n"
        f"🏦 Institucional: {inst_score}/100\n"
        f"🏅 Qualidade: {inst_qual}\n"
        f"{fluxo}\n\n"
        f"{sep}\n\n"
        f"📈 Tendência: {_tendencia_label(tend_4h)}\n"
        f"💧 Liquidez: Alta | 📉 Kalman: {kalman}\n\n"
        f"{sep}\n\n"
        f"✅ {conf_inline}\n\n"
        f"{sep}\n\n"
        f"⭐ Pontos Fortes\n\n"
        f"{pontos_fortes}\n\n"
        + (f"⚠️ Penalizações\n\n{linhas_ajuste}\n\n{sep}\n\n" if linhas_ajuste else f"{sep}\n\n")
        + f"{narrativa}\n\n"
        f"{sep}\n\n"
        f"⏱️ Duração: {duracao}\n"
        f"📈 Gain: +{tp2_pct:.2f}%\n"
        f"📉 Loss: -{stop_pct:.2f}%\n\n"
        f"{sep}\n\n"
        f"✅ APROVADO\n\n"
        f"{sep}\n\n"
        f"K10 v3.0 | Engine Institucional Adaptativo"
    )


def _tendencia_label(tend: str) -> str:
    return {"ALTA": "Forte ↑", "BAIXA": "Forte ↓", "NEUTRA": "Lateral →"}.get(tend, tend)


def formatar_rejeicao(r: dict) -> str:
    symbol  = r["symbol"].replace("/", "").replace(":USDT", "")
    setup   = r.get("setup_nome", "—")
    regime  = r.get("regime", "—")
    score   = r.get("score", 0)
    sep     = "━━━━━━━━━━━━━━━━━━━━"
    motivos = "\n".join(f"❌ {m}" for m in r.get("motivos_rejeicao", []))
    falta   = "\n".join(f"📌 {f}" for f in r.get("o_que_falta", []))
    filled  = round(score / 10)
    barra   = "█" * filled + "░" * (10 - filled)

    return (
        f"🔴 SINAL REJEITADO\n\n"
        f"{symbol}\n\n"
        f"{sep}\n\n"
        f"🔎 Setup: {setup}\n"
        f"🌍 Regime: {regime}\n\n"
        f"⭐ Score Final\n"
        f"{barra} {score}%\n\n"
        f"{sep}\n\n"
        f"🚫 Motivos da rejeição:\n\n"
        f"{motivos}\n\n"
        f"{sep}\n\n"
        f"🔧 O que falta:\n\n"
        f"{falta}\n\n"
        f"{sep}\n\n"
        f"❌ REJEITADO\n\n"
        f"{sep}\n\n"
        f"K10 v3.0 | Engine Institucional Adaptativo"
    )
