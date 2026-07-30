"""
K10 Trading Signal Bot — Telegram
Futuros USDT | 300-500 ativos | Multi-timeframe 30m/1h/4h/1D
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from k10_engine import K10Engine
from scanner import K10Scanner
from formatter import formatar_cartao
from config import BOT_TOKEN, ALLOWED_CHAT_IDS

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

engine  = K10Engine()
scanner = K10Scanner(max_workers=8)


# ── Auth ──────────────────────────────────────────────────────────────────────
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
    kb = [
        [InlineKeyboardButton("📊 Analisar Ativo",   callback_data="menu_analisar")],
        [InlineKeyboardButton("🔍 Scan 300-500 Ativos", callback_data="menu_scan")],
        [InlineKeyboardButton("⏱ Scan por Timeframe", callback_data="menu_tf")],
        [InlineKeyboardButton("🌍 Regime do Mercado", callback_data="menu_regime")],
        [InlineKeyboardButton("ℹ️ Sobre o K10",       callback_data="menu_sobre")],
    ]
    await update.message.reply_text(
        "🤖 *K10 Signal Engine v3.0*\n\n"
        "Futuros USDT | 300–500 ativos\n"
        "Timeframes: 30m | 1h | 4h | 1D\n\n"
        "Comandos:\n"
        "`/analisar BTCUSDT` — análise completa\n"
        "`/scan` — varre todos os futuros\n"
        "`/scan30m` `/scan1h` `/scan4h` — por TF\n"
        "`/regime BTCUSDT` — regime atual\n"
        "`/ajuda` — todos os comandos",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# ── /ajuda ────────────────────────────────────────────────────────────────────
@auth
async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Comandos K10*\n\n"
        "`/analisar SYMBOL` — análise completa\n"
        "`/scan` — scan 300-500 futuros USDT\n"
        "`/scan30m` — sinais do 30 minutos\n"
        "`/scan1h` — sinais do 1 hora\n"
        "`/scan4h` — sinais do 4 horas\n"
        "`/regime SYMBOL` — regime de mercado\n"
        "`/top` — top 5 melhores sinais agora\n"
        "`/ajuda` — esta mensagem",
        parse_mode="Markdown"
    )


# ── /analisar ─────────────────────────────────────────────────────────────────
@auth
async def analisar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: `/analisar BTCUSDT`", parse_mode="Markdown")
        return
    symbol = context.args[0].upper()
    if "/" not in symbol:
        symbol = symbol.replace("USDT","") + "/USDT"

    msg = await update.message.reply_text(f"⏳ Analisando *{symbol}*...", parse_mode="Markdown")
    result = engine.analisar(symbol)
    await msg.edit_text(formatar_cartao(result), parse_mode="Markdown")


# ── /scan ─────────────────────────────────────────────────────────────────────
@auth
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        "🔍 Iniciando scan de futuros USDT...\n"
        "Isso pode levar 2-5 minutos para 300+ ativos.",
        parse_mode="Markdown"
    )

    def progress(n, total):
        import asyncio
        asyncio.create_task(
            msg.edit_text(f"⏳ Analisando... {n}/{total} ativos", parse_mode="Markdown")
        )

    aprovados = scanner.scan(min_score=70)
    resumo    = scanner.formatar_resumo(aprovados)
    await msg.edit_text(resumo, parse_mode="Markdown")


# ── /scan por timeframe ───────────────────────────────────────────────────────
async def _scan_tf(update: Update, tf: str):
    msg = await update.message.reply_text(
        f"🔍 Scan *{tf}* em andamento...", parse_mode="Markdown"
    )
    # O engine usa 30m como operacional; filtrar pelo TF no resultado
    aprovados = scanner.scan(min_score=70)
    resumo    = scanner.formatar_resumo(aprovados, timeframe=tf)
    await msg.edit_text(resumo, parse_mode="Markdown")

@auth
async def scan30m(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _scan_tf(update, "30m")

@auth
async def scan1h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _scan_tf(update, "1h")

@auth
async def scan4h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _scan_tf(update, "4h")


# ── /top ──────────────────────────────────────────────────────────────────────
@auth
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🏆 Buscando top 5 oportunidades...", parse_mode="Markdown")
    aprovados = scanner.scan(min_score=80)[:5]
    if not aprovados:
        await msg.edit_text("Nenhum sinal com score ≥ 80 no momento.")
        return
    resumo = scanner.formatar_resumo(aprovados, timeframe="top5")
    await msg.edit_text(resumo, parse_mode="Markdown")


# ── /regime ───────────────────────────────────────────────────────────────────
@auth
async def regime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: `/regime BTCUSDT`", parse_mode="Markdown")
        return
    symbol = context.args[0].upper()
    if "/" not in symbol:
        symbol = symbol.replace("USDT","") + "/USDT"
    data = engine.obter_regime(symbol)
    emoji = {"Bull Trend":"🟢","Bear Trend":"🔴","Range":"🟡",
             "Compressão":"🔵","Transição":"🟠"}.get(data["regime"],"⚪")
    await update.message.reply_text(
        f"{emoji} *Regime — {symbol.replace('/USDT','')}*\n\n"
        f"Regime: `{data['regime']}`\n"
        f"ADX: `{data['adx']:.1f}`\n"
        f"ATR: `{data['atr']:.4f}`\n"
        f"H4: `{data['tendencia_4h']}` | D1: `{data['tendencia_1d']}`\n"
        f"Setup recomendado: `{data['setup_recomendado']}`",
        parse_mode="Markdown"
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "menu_analisar":
        await q.message.reply_text("Digite: `/analisar BTCUSDT`", parse_mode="Markdown")
    elif q.data == "menu_scan":
        await q.message.reply_text("Use o comando `/scan` para varrer todos os futuros.", parse_mode="Markdown")
    elif q.data == "menu_tf":
        kb = [
            [InlineKeyboardButton("30 minutos", callback_data="tf_30m")],
            [InlineKeyboardButton("1 hora",     callback_data="tf_1h")],
            [InlineKeyboardButton("4 horas",    callback_data="tf_4h")],
        ]
        await q.message.reply_text("Escolha o timeframe:", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data == "tf_30m":
        await q.message.reply_text("Use `/scan30m`", parse_mode="Markdown")
    elif q.data == "tf_1h":
        await q.message.reply_text("Use `/scan1h`", parse_mode="Markdown")
    elif q.data == "tf_4h":
        await q.message.reply_text("Use `/scan4h`", parse_mode="Markdown")
    elif q.data == "menu_regime":
        await q.message.reply_text("Digite: `/regime BTCUSDT`", parse_mode="Markdown")
    elif q.data == "menu_sobre":
        await q.message.reply_text(
            "🤖 *K10 Signal Engine v3.0*\n\n"
            "• 4 Setups institucionais com hierarquia\n"
            "• 300–500 futuros USDT analisados\n"
            "• Multi-timeframe: 30m | 1h | 4h | 1D\n"
            "• SMC: Sweep, CHoCH, BOS, OB, FVG\n"
            "• Score mínimo: 70 | RR mínimo: 1:2\n"
            "• Gestão dinâmica de banca $90",
            parse_mode="Markdown"
        )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("ajuda",    ajuda))
    app.add_handler(CommandHandler("analisar", analisar))
    app.add_handler(CommandHandler("scan",     scan))
    app.add_handler(CommandHandler("scan30m",  scan30m))
    app.add_handler(CommandHandler("scan1h",   scan1h))
    app.add_handler(CommandHandler("scan4h",   scan4h))
    app.add_handler(CommandHandler("top",      top))
    app.add_handler(CommandHandler("regime",   regime))
    app.add_handler(CallbackQueryHandler(callback_handler))
    logger.info("✅ K10 Bot v3.0 iniciado")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
