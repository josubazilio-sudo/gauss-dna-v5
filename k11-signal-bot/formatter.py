"""
K10/K12 Formatter — Cartão limpo: Entrada, TP1, Stop
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
    risco_pct = r.get("risco_pct_aplicado", 3.0)
    duracao = {"5m":"20–40min","15m":"1–2h","30m":"4–8h","1h":"6–12h","4h":"24–48h","1d":"3–7d"}.get(tf,"6–12h")
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

    # RFC reequilibrio 22/08 — classificação de qualidade nova (APEX/PRO/
    # SETUP), coexiste com o tier OURO/PRATA acima. Só aparece quando o
    # engine calculou (sempre calcula agora, mas fica defensivo p/ dicts
    # antigos/sintéticos sem esse campo).
    tier_q = r.get("tier_qualidade")
    tier_q_emoji = {"APEX": "🔥 APEX", "PRO": "🟢 PRO", "SETUP": "🟡 SETUP"}.get(tier_q)
    tier_q_line = f"{tier_q_emoji} | Quality Final: {r.get('quality_final')}/100\n\n" if tier_q_emoji else ""

    soft_avisos = r.get("motivos_soft") or []
    soft_block = (
        "⚠️ Avisos (penalizaram, não bloquearam):\n"
        + "\n".join(f"⚠️ {m}" for m in soft_avisos) + "\n\n"
    ) if soft_avisos else ""

    frac_tp1 = int(round(TP1_FRACAO_VOLUME * 100))
    return (
        f"🏆 {symbol}\n\n"
        f"{prioridade_line}"
        f"{dir_emoji} | {tf} | {tier_map.get(tier,'🥉 BRONZE')}\n\n"
        f"⭐ Score: {score} | {conv_map.get(tier,'MODERADA 🔶')}\n\n"
        f"{tier_q_line}"
        f"EQ: {r.get('entry_quality',0)}/100 | EMA21:{r.get('eq_detalhes',{}).get('ema21',0):+d} OB:{r.get('eq_detalhes',{}).get('ob_fvg',0):+d} MACD:{r.get('eq_detalhes',{}).get('timing',0):+d} RSI:{r.get('eq_detalhes',{}).get('rsi',0):+d} BOS:{r.get('eq_detalhes',{}).get('bos',0):+d}\n"
        f"{sep}\n\n"
        f"💰 Entrada: {entrada}\n"
        f"🎯 TP1: {tp1} (parcial {frac_tp1}%)\n"
        f"🎯 TP2: {tp2}\n"
        f"⚡ BE em: {be}\n"
        f"🛑 Stop: {stop}\n"
        f"⚖️ RR: {rr}\n\n"
        f"💵 Banca: {capital} USDT | 🚀 {alav}x\n"
        f"⚠️ Risco: {risco} USDT ({risco_pct:g}%)\n"
        f"📦 Posição: {posicao} USDT\n\n"
        f"{sep}\n\n"
        f"🌍 {regime}\n"
        f"📊 {setup_label} | ⏱️ {duracao}\n\n"
        f"{smc_block + chr(10) + chr(10) if smc_block else ''}"
        f"{soft_block}"
        f"{bot_name}"
    )

def formatar_rejeicao(r: dict) -> str:
    return None


def formatar_cartao_operavel(r: dict, avaliacao: dict) -> str:
    """RFC modo-operavel 29/08 — formato de card do modulo final de
    liberacao. So chamado quando avaliacao['operar'] e True (o caso
    NAO OPERAR nao gera card de producao, so log — a RFC pede mostrar
    'somente os 3 principais motivos', o que fica no log, nao no
    Telegram, para nao gerar ruido de mensagens de sinais que nao saem)."""
    symbol  = r["symbol"].replace("/USDT:USDT", "").replace("/USDT", "")
    direcao = r["direcao"]
    tf      = r.get("timeframe", "30m")
    dir_emoji = "🟢 LONG" if direcao == "LONG" else "🔴 SHORT"

    classe = avaliacao["classificacao"]
    classe_emoji = {"PREMIUM": "🔥 PREMIUM", "BOM": "🟢 BOM", "ACEITAVEL": "🟡 ACEITÁVEL"}.get(classe, classe)

    est = avaliacao["estrutura"]
    ctx = avaliacao["contexto"]
    ok = lambda b: "✅" if b else "⚠️"

    sep = "━━━━━━━━━━━━━━━━━━━━"
    return (
        f"🏆 {symbol}\n\n"
        f"🔥 K12 OPERÁVEL\n\n"
        f"{dir_emoji} | {tf}\n"
        f"⭐ {classe_emoji}\n\n"
        f"Score: {r.get('score')}\n"
        f"EQ: {r.get('entry_quality')}\n"
        f"RVOL: {r.get('rvol', 0):.2f}\n"
        f"RR: {r.get('rr', 0):.2f}\n\n"
        f"{sep}\n\n"
        f"🧠 ESTRUTURA\n"
        f"BOS/CHoCH: {ok(est['bos_choch'])}\n"
        f"Liquidez: {ok(est['liquidez'])}\n"
        f"Pullback/reteste: {ok(est['pullback'])}\n"
        f"Zona institucional: {ok(est['zona_institucional'])}\n\n"
        f"📊 CONTEXTO\n"
        f"H1/H4: {ok(ctx['htf_alinhado'])}\n"
        f"EMA: {ok(ctx['ema_ok'])}\n"
        f"MACD: {ok(ctx['macd_ok'])}\n"
        f"Volume: {ok(ctx['volume_ok'])}\n\n"
        f"{sep}\n\n"
        f"💰 Entrada: {r.get('entrada')}\n"
        f"🎯 TP1: {r.get('tp1')}\n"
        f"🎯 TP2: {r.get('tp2')}\n"
        f"⚡ BE: {r.get('be')}\n"
        f"🛑 Stop: {r.get('stop')}\n\n"
        f"⚖️ RR: {r.get('rr', 0):.2f}\n\n"
        f"💵 Banca: {r.get('capital')} USDT\n"
        f"⚠️ Risco: {avaliacao['risco_usdt_final']} USDT ({avaliacao['risco_pct_final']:.2f}%)\n"
        f"📦 Posição: {avaliacao['posicao_final']} USDT\n\n"
        f"{sep}\n\n"
        f"🟢 DECISÃO: OPERAR\n\n"
        f"K12"
    )
