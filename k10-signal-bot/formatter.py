"""
K10 Formatter v5 — Compacto, informações lado a lado
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
    confs    = r.get("confirmacoes", [])
    adx      = r.get("adx", 0)
    rsi      = r.get("rsi", 0)
    atr      = r.get("atr", 0)
    tend_4h  = r.get("tend_4h", "—")
    tend_1d  = r.get("tend_1d", "—")
    ema21    = r.get("ema21", preco)
    vwap_v   = r.get("vwap", preco)

    dir_emoji = "🟢 LONG" if direcao == "LONG" else "🔴 SHORT"

    if score >= 90:   tier, rank = "🥇 OURO",   "🥇 #1 DO CICLO"
    elif score >= 80: tier, rank = "🥈 PRATA",  "🥈 TOP DO CICLO"
    elif score >= 70: tier, rank = "🥉 BRONZE", "🥉 SINAL CONFIRMADO"
    else:             tier, rank = "🥉 BRONZE", "🥉 SINAL MONITORADO"

    tp1_pct  = abs(tp1  - entrada) / entrada * 100
    tp2_pct  = abs(tp2  - entrada) / entrada * 100
    stop_pct = abs(stop - entrada) / entrada * 100
    s1 = "+" if tp1 > entrada else "-"
    s2 = "+" if tp2 > entrada else "-"
    ss = "-" if stop < entrada else "+"

    win_rate  = round(40 + score * 0.45, 1)
    confianca = round(score * 0.8, 1)
    risco_sc  = max(5, 100 - score)
    timing    = min(round((adx / 50 * 50) + (50 - abs(rsi - 50))), 100)
    inst_sc   = round(score * 0.9)
    inst_qual = "A" if inst_sc >= 85 else "B" if inst_sc >= 70 else "C"
    atr_pct   = atr / preco * 100 if preco > 0 else 0
    atr_cons  = round(atr_pct / (atr_pct + stop_pct) * 100) if (atr_pct + stop_pct) > 0 else 0
    dist_ema  = round(abs(preco - ema21) / atr, 2) if atr > 0 else 0
    dist_vwap = round(abs(preco - vwap_v) / preco * 100, 2) if preco > 0 else 0
    pullback  = "SIM" if dist_ema < 1.5 else "NÃO"
    kalman    = "UP ↑" if direcao == "LONG" else "DOWN ↓"
    fluxo     = "🟢 Comprador Forte" if direcao == "LONG" else "🔴 Vendedor Forte"
    tend_label= {"ALTA":"Forte ↑","BAIXA":"Forte ↓","NEUTRA":"Lateral →"}.get(tend_4h, tend_4h)
    duracao   = {"30m":"4–8h","1h":"8–18h","4h":"24–48h","1d":"3–7d"}.get(tf,"8–18h")
    conf_line = " • ".join(confs[:5]) if confs else "Confluência confirmada"
    pontos    = "\n".join(f"✅ {c}" for c in confs)
    narrativa = ", ".join(confs[:3]) + f", Kalman {kalman}." if confs else f"Kalman {kalman}."

    filled = round(score / 10)
    barra  = "█" * filled + "░" * (10 - filled)

    sep = "━━━━━━━━━━━━━━━━━━━━"

    setup_label = {
        "TREND FOLLOWING":        "🚀 Trend Following",
        "BREAKOUT":               "💥 Breakout",
        "REVERSÃO INSTITUCIONAL": "🔄 Reversão SMC",
        "SCALPING ADAPTATIVO":    "↔️ Scalping",
    }.get(setup, setup)

    return (
        f"🔶 SINAL APROVADO\n\n"
        f"{symbol}\n\n"
        f"{dir_emoji} | {tf} | {tier} | ⭐ {score}\n"
        f"{rank}\n\n"
        f"{sep}\n\n"
        f"💰 Entrada: {entrada}\n"
        f"🎯 TP1: {tp1} ({s1}{tp1_pct:.2f}%) | TP2: {tp2} ({s2}{tp2_pct:.2f}%)\n"
        f"🛑 Stop: {stop} ({ss}{stop_pct:.2f}%)\n\n"
        f"{sep}\n\n"
        f"💵 Banca: {banca} USDT | 💰 Capital: {capital} USDT\n"
        f"📦 Posição: {posicao} USDT | 🚀 {alavanca}x | ⚖️ RR {rr}\n\n"
        f"{sep}\n\n"
        f"⭐ Score: {barra} {score}%\n"
        f"🎲 Win: {win_rate}% | 🧠 Conf: {confianca}% | ⚠️ Risco: {risco_sc}/100\n\n"
        f"{sep}\n\n"
        f"🎯 Timing: {timing}/100 | 📉 ATR: {atr_cons}% consumido\n"
        f"📏 EMA21: {dist_ema} ATR | VWAP: {dist_vwap}% | Pullback: {pullback}\n\n"
        f"{sep}\n\n"
        f"🏦 Institucional: {inst_sc}/100 | 🏅 {inst_qual} | {fluxo}\n"
        f"📈 Tendência: {tend_label} | H4: {tend_4h} | D1: {tend_1d}\n"
        f"💧 Liquidez: Alta | 📉 Kalman: {kalman}\n\n"
        f"{sep}\n\n"
        f"✅ {conf_line}\n\n"
        f"{sep}\n\n"
        f"⭐ Pontos Fortes\n\n"
        f"{pontos}\n\n"
        f"{sep}\n\n"
        f"📝 {narrativa}\n\n"
        f"{sep}\n\n"
        f"🧠 Setup: {setup_label} | 🌍 Regime: {regime}\n"
        f"⏱️ Duração: {duracao} | 📈 Gain: +{tp2_pct:.2f}% | 📉 Loss: -{stop_pct:.2f}%\n\n"
        f"{sep}\n\n"
        f"✅ APROVADO\n\n"
        f"{sep}\n\n"
        f"K10 v3.0 | Engine Institucional Adaptativo"
    )


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
        f"🔎 Setup: {setup} | 🌍 Regime: {regime}\n"
        f"⭐ Score: {barra} {score}%\n\n"
        f"{sep}\n\n"
        f"🚫 Motivos:\n\n{motivos}\n\n"
        f"{sep}\n\n"
        f"🔧 O que falta:\n\n{falta}\n\n"
        f"{sep}\n\n"
        f"❌ REJEITADO\n\n"
        f"{sep}\n\n"
        f"K10 v3.0 | Engine Institucional Adaptativo"
    )
