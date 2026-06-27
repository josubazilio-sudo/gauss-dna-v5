import logging
import aiohttp
from datetime import datetime

from config import TG_TOKEN, TG_CHATID

logger = logging.getLogger(__name__)

def _fmt(v):
    return f"{v:.6f}" if v < 0.01 else f"{v:.4f}" if v < 1 else f"{v:.2f}"

def _escape(text):
    s = str(text).replace('\\', '\\\\')
    for ch in r"_*[]()~`>#+=|{}.!-":
        s = s.replace(ch, f"\\{ch}")
    return s

def _grade_emoji(classificacao):
    return {"OURO": "🥇", "PRATA": "🥈", "BRONZE": "🥉"}.get(classificacao, "📊")

async def send_signal(session, symbol, direction, preco, score, classificacao,
                      rsi, adx, rvol, tendencia, timeframe="1h", detalhes=None,
                      stop_loss=None, tp1=None, tp2=None, alavancagem=None,
                      stop_pct=None, tp1_pct=None, tp2_pct=None):
    if not TG_TOKEN or not TG_CHATID:
        logger.warning("TG_TOKEN ou TG_CHATID nao configurados")
        return False

    agora = datetime.now().strftime("%H:%M — %d/%m/%Y")
    direcao_emoji = "🟢" if direction == "LONG" else "🔴"
    grade_emoji = _grade_emoji(classificacao)

    linha_detalhes = ""
    if detalhes:
        for k, v in detalhes.items():
            linha_detalhes += f"📌 {_escape(k)}: `{_escape(str(v))}`\n"

    linha_tp_sl = ""
    if stop_loss:
        sl_label = f"{_escape(f'SL {stop_pct}%')}" if stop_pct else "SL"
        tp1_label = f"{_escape(f'TP1 {tp1_pct}%')}" if tp1_pct else "TP1"
        tp2_label = f"{_escape(f'TP2 {tp2_pct}%')}" if tp2_pct else "TP2"
        alav_label = f" \\| {alavancagem}x" if alavancagem else ""
        linha_tp_sl = (
            f"\n🛑 {sl_label}: `${_escape(str(stop_loss))}`\n"
            f"✅ {tp1_label}: `${_escape(str(tp1))}`\n"
            f"🏆 {tp2_label}: `${_escape(str(tp2))}`{alav_label}\n"
        )

    texto = (
        f"🚨 *GAUSS DNA V5 — {direction}*\n\n"
        f"{direcao_emoji} *{_escape(symbol)}* \\| 🕐 *{_escape(timeframe)}*\n"
        f"{grade_emoji} *{_escape(classificacao)}* \\| Score: *{_escape(str(score))}/100*\n\n"
        f"💰 Entrada: `${_fmt(preco)}`\n"
        f"📊 RSI: {_escape(f'{rsi:.0f}')} \\| ADX: {_escape(f'{adx:.0f}')}\n"
        f"📈 RVOL: `{_escape(f'{rvol:.2f}')}x`\n"
        f"📍 Tendência: {_escape(tendencia)}\n"
        f"{linha_tp_sl}"
        f"{linha_detalhes}\n"
        f"⏰ {_escape(agora)}"
    )

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        async with session.post(
            url,
            json={"chat_id": TG_CHATID, "text": texto, "parse_mode": "MarkdownV2"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            data = await r.json()
            if data.get("ok"):
                logger.info("✅ Sinal enviado: %s %s %s Score:%s", direction, symbol, classificacao, score)
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
