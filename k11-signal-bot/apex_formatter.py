"""
K11 APEX — Formatador do card especial (SHADOW MODE).
Mensagem completamente distinta do cartão normal (secao 18 da RFC) —
nunca deve ser confundida com um sinal comum.
"""
from config import TP1_FRACAO_VOLUME


def formatar_apex_cartao(sinal: dict, apex_info: dict) -> str:
    symbol  = sinal["symbol"].replace("/USDT:USDT", "").replace("/USDT", "")
    direcao = sinal["direcao"]
    tf      = sinal.get("timeframe", "30m")
    tipo    = apex_info.get("apex_tipo", "—")
    score   = apex_info.get("apex_score", 0)
    chk     = apex_info.get("checklist", {})

    entrada = sinal["entrada"]
    tp1     = sinal["tp1"]
    tp2     = sinal.get("tp2", tp1)
    be      = sinal.get("be", "")
    stop    = sinal["stop"]
    rr      = sinal.get("rr", 0)

    dir_emoji  = "🟢 LONG" if direcao == "LONG" else "🔴 SHORT"
    tipo_label = "TENDÊNCIA" if tipo == "TREND" else "REVERSÃO" if tipo == "REVERSAL" else tipo

    sep = "━━━━━━━━━━━━━━"
    frac_tp1 = int(round(TP1_FRACAO_VOLUME * 100))

    return (
        f"🔥 K11 APEX\n\n"
        f"🏆 SETUP PREMIUM — {symbol}\n"
        f"🧭 APEX {tipo_label}\n\n"
        f"{dir_emoji} | {tf}\n"
        f"⭐ APEX: {score}/100\n\n"
        f"{sep}\n"
        f"🧠 ESTRUTURA\n"
        f"BOS/CHoCH: {chk.get('Estrutura','—')}\n"
        f"Liquidez / zona institucional: {chk.get('Liquidez','—')}\n\n"
        f"📊 CONFIRMAÇÃO\n"
        f"H1/H4 alinhado: {chk.get('HTF (H1/H4)','—')}\n"
        f"EMAs: {chk.get('Tendência/EMA','—')}\n"
        f"MACD: {chk.get('Momentum (MACD)','—')}\n\n"
        f"🔥 FLUXO\n"
        f"RVOL: {chk.get('RVOL','—')}\n\n"
        f"🎯 TIMING\n"
        f"Entry Quality: {chk.get('Timing (EQ)','—')}\n"
        f"{sep}\n\n"
        f"💰 Entrada: {entrada}\n"
        f"🎯 TP1: {tp1} (parcial {frac_tp1}%)\n"
        f"🎯 TP2: {tp2}\n"
        f"⚡ BE em: {be}\n"
        f"🛑 Stop: {stop}\n\n"
        f"⚖️ RR: {rr}\n\n"
        f"{sep}\n\n"
        f"🔥 APEX — AGUARDAR EXECUÇÃO\n"
        f"(shadow mode — em validação; progresso no resumo diário 23:30 BRT)"
    )
