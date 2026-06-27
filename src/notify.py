import logging
import aiohttp
from datetime import datetime

from config import TG_TOKEN, TG_CHATID, CAPITAL, ALAVANCAGEM_MIN, ALAVANCAGEM_MAX

logger = logging.getLogger(__name__)

def _fmt(v):
    if v is None: return "0"
    return f"{v:.6f}" if abs(v) < 0.01 else f"{v:.4f}" if abs(v) < 1 else f"{v:.2f}"

def _html(text):
    s = str(text)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _grade_emoji(c):
    return {"OURO": "🥇", "PRATA": "🥈", "BRONZE": "🥉"}.get(c, "📊")

def _score_desc(score):
    if score >= 90: return "MÁXIMO"
    if score >= 75: return "FORTE"
    if score >= 60: return "MODERADO"
    return "FRACO"

def _fluxo_desc(v):
    delta = v.get("DELTA")
    fluxo = v.get("FLUXO_TIPO", "")
    if delta is not None and delta > 0:
        return "🟢 Forte" if fluxo == "comprador" else "🟢 Moderado"
    if delta is not None and delta < 0:
        return "🔴 Fraco" if fluxo == "vendedor" else "🔴 Moderado"
    return "⚪ Neutro"

def _kalman_dir(v):
    k = v.get("KALMAN_DIRECAO", v.get("TENDENCIA", ""))
    if "alta" in str(k).lower(): return "↑"
    if "baixa" in str(k).lower(): return "↓"
    return "→"

def _funding_str(v):
    f = v.get("FUNDING_RATE")
    if f is not None:
        return f"{float(f)*100:.4f}%"
    return "—"

def _calc_gestao(v, preco):
    capital = CAPITAL
    score = v.get("SCORE_TOTAL", 0)
    if score >= 90:
        lote = "OURO"
        risco_pct = 0.03
        alav = 20
    elif score >= 75:
        lote = "PRATA"
        risco_pct = 0.02
        alav = 10
    else:
        lote = "BRONZE"
        risco_pct = 0.01
        alav = 5
    alav = max(ALAVANCAGEM_MIN, min(alav, ALAVANCAGEM_MAX))
    risco_dol = capital * risco_pct
    pos = (risco_dol / 0.01) if preco > 0 else 0
    margem = pos * preco / alav if alav > 0 else 0
    return lote, risco_dol, pos, alav, margem

async def send_signal(session, symbol, direction, preco, score, classificacao,
                      rsi, adx, rvol, tendencia, v, timeframe="1h"):
    if not TG_TOKEN or not TG_CHATID:
        logger.warning("TG_TOKEN ou TG_CHATID nao configurados")
        return False

    agora = datetime.now().strftime("%H:%M — %d/%m/%Y")
    dir_emoji = "🟢" if direction == "LONG" else "🔴"
    grade_emoji = _grade_emoji(classificacao)
    score_desc = _score_desc(score)
    fluxo = _fluxo_desc(v)
    kalman = _kalman_dir(v)

    sl = v.get("stop_loss")
    tp1 = v.get("tp1")
    sl_pct = v.get("stop_pct")

    lote, risco_dol, pos, alav, margem = _calc_gestao(v, preco)
    tp1_ganho = risco_dol * 1.0 if risco_dol > 0 else 0

    lines = [
        f"🚨 ⚡ DNA FLEX — {direction}",
        "",
        f"{dir_emoji} {_html(symbol)} | 🕐 {_html(timeframe)}",
        "",
        f"🏆 GRADE: {grade_emoji} | 🥉 {_html(classificacao)}",
        f"🏛 Score Inst: {score}/100 — {_html(score_desc)}",
        f"🎯 Confianca: {_html(str(v.get('CONFIANCA', 0)))}%",
        "",
        f"💰 Entrada: ${_fmt(preco)}",
        f"🛑 Stop ({_fmt(sl_pct)} ATR): ${_fmt(sl)} - R={_fmt(sl_pct)}%",
        f"🎯 TP1 (1.0R): ${_fmt(tp1)} -> fechar 50% - stop -> BE ${_fmt(preco)}",
        f"🏁 Restante (50%): trailing stop (50% do ganho desde o TP1, piso BE)",
        "",
        f"📊 RSI: {rsi:.0f}",
        f"📈 RVOL: {rvol:.2f}x {'STRONG' if rvol >= 1.5 else 'NORMAL' if rvol >= 1.0 else 'FRACO'}",
        f"📉 ADX: {adx:.0f}",
        f"📦 Fluxo: {_html(fluxo)} | Kalman: {_html(kalman)}",
        f"📍 Tendencia: {_html(tendencia.upper())}",
        "",
        f"📐 Gestao (lote fixo {_html(lote)})",
        f"Risco: ${_fmt(risco_dol)} | Pos: ${_fmt(pos)} | {alav}x (${_fmt(margem)} margem)",
        f"💸 TP1 +{_fmt(tp1_ganho)} garantido | restante 50% em trailing (min. BE)",
        f"💹 Funding: {_html(_funding_str(v))}",
        f"⏰ {_html(agora)}",
    ]
    texto = "\n".join(lines)

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        async with session.post(
            url,
            json={"chat_id": TG_CHATID, "text": texto},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            data = await r.json()
            if data.get("ok"):
                logger.info("Sinal enviado: %s %s %s Score:%s", direction, symbol, classificacao, score)
                return True
            else:
                logger.warning("Telegram erro: %s", data.get("description"))
                return False
    except Exception as e:
        logger.error("Falha ao enviar Telegram: %s", e)
        return False

async def send_diagnostic(session, texto):
    if not TG_TOKEN or not TG_CHATID:
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        async with session.post(
            url,
            json={"chat_id": TG_CHATID, "text": texto},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            data = await r.json()
            if not data.get("ok"):
                logger.warning("Diagnostico Telegram: %s", data.get("description"))
    except Exception as e:
        logger.warning("Diagnostico Telegram falhou: %s", e)
