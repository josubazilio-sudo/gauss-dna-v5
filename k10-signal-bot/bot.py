"""
K10 Trading Signal Bot — Telegram
Arquitetura adaptativa com 4 setups, Market Regime, Entry Engine e Quality Gate
"""

import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
from k10_engine import K10Engine
from config import BOT_TOKEN, ALLOWED_CHAT_IDS
from formatter import formatar_cartao

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

engine = K10Engine()

# ── Autenticação ──────────────────────────────────────────────────────────────
def auth(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
            await update.message.reply_text("⛔ Acesso não autorizado.")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ── /start ────────────────────────────────────────────────────────────────────
@auth
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Analisar Ativo", callback_data="menu_analisar")],
        [InlineKeyboardButton("🔁 Scan Multi-Ativo", callback_data="menu_scan")],
        [InlineKeyboardButton("ℹ️ Sobre o K10", callback_data="menu_sobre")],
    ]
    await update.message.reply_text(
        "🤖 *K10 Signal Engine* — v1.0\n\n"
        "Sistema adaptativo com 4 setups institucionais.\n"
        "Use os botões abaixo ou os comandos:\n\n"
        "`/analisar BTCUSDT`\n"
        "`/scan` — varre múltiplos ativos\n"
        "`/regime ETHUSDT` — regime atual\n"
        "`/ajuda` — lista completa",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── /ajuda ────────────────────────────────────────────────────────────────────
@auth
async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📋 *Comandos disponíveis*\n\n"
        "`/analisar <SYMBOL>` — análise completa K10\n"
        "`/scan` — varre lista de ativos\n"
        "`/regime <SYMBOL>` — identifica regime\n"
        "`/setup <SYMBOL>` — setup recomendado\n"
        "`/ajuda` — esta mensagem"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ── /analisar ─────────────────────────────────────────────────────────────────
@auth
async def analisar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: `/analisar BTCUSDT`", parse_mode="Markdown")
        return

    symbol = context.args[0].upper()
    msg = await update.message.reply_text(f"⏳ Analisando *{symbol}*...", parse_mode="Markdown")

    result = engine.analisar(symbol)
    text = formatar_sinal(result)

    await msg.edit_text(text, parse_mode="Markdown")


# ── /scan ─────────────────────────────────────────────────────────────────────
@auth
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import WATCHLIST
    msg = await update.message.reply_text(
        f"🔍 Varrendo {len(WATCHLIST)} ativos...", parse_mode="Markdown"
    )

    aprovados = []
    for symbol in WATCHLIST:
        result = engine.analisar(symbol)
        if result.get("aprovado"):
            aprovados.append(result)

    if not aprovados:
        await msg.edit_text("🔎 Nenhum sinal aprovado no momento. Tente novamente em breve.")
        return

    resumo = f"✅ *{len(aprovados)} sinal(is) aprovado(s)*\n\n"
    for r in aprovados:
        resumo += (
            f"• *{r['symbol']}* | {r['setup_nome']} | "
            f"Score {r['score']}/100 | RR {r['rr']}\n"
        )
    resumo += "\nUse `/analisar SYMBOL` para ver detalhes."
    await msg.edit_text(resumo, parse_mode="Markdown")


# ── /regime ───────────────────────────────────────────────────────────────────
@auth
async def regime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: `/regime BTCUSDT`", parse_mode="Markdown")
        return

    symbol = context.args[0].upper()
    data = engine.obter_regime(symbol)

    emoji_map = {
        "Bull Trend": "🟢", "Bear Trend": "🔴",
        "Range": "🟡", "Alta Volatilidade": "🔶",
        "Baixa Volatilidade": "⬜", "Transição": "🔵"
    }
    emoji = emoji_map.get(data["regime"], "⚪")

    msg = (
        f"{emoji} *Regime — {symbol}*\n\n"
        f"Regime: `{data['regime']}`\n"
        f"ADX: `{data['adx']:.1f}`\n"
        f"ATR: `{data['atr']:.4f}`\n"
        f"Tendência 4H: `{data['tendencia_4h']}`\n"
        f"Tendência 1D: `{data['tendencia_1d']}`\n"
        f"Setup recomendado: `{data['setup_recomendado']}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ── /setup ────────────────────────────────────────────────────────────────────
@auth
async def setup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: `/setup BTCUSDT`", parse_mode="Markdown")
        return

    symbol = context.args[0].upper()
    data = engine.obter_regime(symbol)

    descricoes = {
        "SETUP 1 — CONTINUAÇÃO": "Tendência confirmada, pull ao EMA20/VWAP, BOS e volume.",
        "SETUP 2 — REVERSAL": "Mercado esticado, RSI extremo, divergência, candle de reversão.",
        "SETUP 3 — BREAKOUT": "Consolidação rompida, volume explosivo, ADX crescente.",
        "SETUP 4 — RANGE": "Lateral, ADX baixo, oscilando entre S/R.",
    }
    nome = data["setup_recomendado"]
    desc = descricoes.get(nome, "—")

    await update.message.reply_text(
        f"🧠 *Setup para {symbol}*\n\n"
        f"`{nome}`\n\n"
        f"_{desc}_",
        parse_mode="Markdown"
    )


# ── Callbacks de menu ─────────────────────────────────────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_analisar":
        await query.message.reply_text(
            "Digite: `/analisar BTCUSDT`", parse_mode="Markdown"
        )
    elif query.data == "menu_scan":
        context.args = []
        await scan(query, context)
    elif query.data == "menu_sobre":
        await query.message.reply_text(
            "🤖 *K10 Signal Engine*\n\n"
            "Sistema institucional adaptativo com:\n"
            "• 4 setups automáticos\n"
            "• Market Regime Detection\n"
            "• Entry Engine com 10+ filtros\n"
            "• Quality Gate com RR ≥ 2\n"
            "• Hierarquia multi-timeframe (30m→1D)",
            parse_mode="Markdown"
        )


# ── Formatação do sinal ───────────────────────────────────────────────────────
def formatar_sinal(r: dict) -> str:
    return formatar_cartao(r)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("analisar", analisar))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("regime", regime))
    app.add_handler(CommandHandler("setup", setup_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("✅ K10 Bot iniciado.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
