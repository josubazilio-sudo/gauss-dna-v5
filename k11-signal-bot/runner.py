"""
K11 Runner — Core Freeze V1 + Early Entry Shadow Mode
"""
import asyncio, logging, os, httpx, traceback
from scanner import K10Scanner
from formatter import formatar_cartao
from config import BOT_TOKEN, ALLOWED_CHAT_IDS

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
CHAT_ID = ALLOWED_CHAT_IDS[0] if ALLOWED_CHAT_IDS else None

async def enviar(texto: str):
    if not CHAT_ID or not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={"chat_id": CHAT_ID, "text": texto[:4096]})
        logger.info(f"TG: {r.status_code}")

async def main():
    logger.info("K11 iniciado")

    # ── Engine principal ──────────────────────────────────────────────────
    try:
        scanner = K10Scanner(max_workers=6)
        aprovados = scanner.scan(min_score=70, max_ativos=500)
        logger.info(f"K11 principal: {len(aprovados)} aprovados")
    except Exception:
        logger.error(traceback.format_exc())
        aprovados = []

    def prioridade(r):
        return r.get("score",0)*0.5 + min(r.get("rvol",0)*10,30)*0.3 + r.get("confluencia",0)*0.2

    aprovados.sort(key=prioridade, reverse=True)

    for sinal in aprovados[:3]:
        cartao = formatar_cartao(sinal, bot_name="K11")
        if cartao:
            await enviar(cartao)
            logger.info(f"K11: {sinal['symbol']} score={sinal['score']}")
            await asyncio.sleep(2)

    # ── Early Entry Shadow Mode ───────────────────────────────────────────
    try:
        from early_entry_engine import EarlyEntryEngine
        from watchlist import get_watchlist, WATCHLIST_FALLBACK
        from concurrent.futures import ThreadPoolExecutor, as_completed

        ee_engine = EarlyEntryEngine()
        wl = (get_watchlist(min_volume_usdt=100_000) or WATCHLIST_FALLBACK)[:200]

        ee_resultados = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(ee_engine.analisar, sym): sym for sym in wl}
            for f in as_completed(futures):
                r = f.result()
                if r and r.get("aprovado"):
                    ee_resultados.append(r)

        ee_resultados.sort(key=lambda x: x.get("score",0), reverse=True)
        logger.info(f"Early Entry shadow: {len(ee_resultados)} aprovados")

        # Reportar no Telegram como SHADOW (sem executar)
        if ee_resultados:
            top = ee_resultados[:3]
            linhas = [f"👁 SHADOW — Early Entry V1 ({len(ee_resultados)} sinais):\n"]
            for r in top:
                sym  = r["symbol"].replace("/USDT:USDT","")
                linhas.append(
                    f"🔍 {sym} {r['direcao']} | {r['timeframe']} | score={r['score']} rvol={r['rvol']:.2f}\n"
                    f"   Entrada={r['entrada']} TP1={r['tp1']} Stop={r['stop']}\n"
                    f"   Confs: {', '.join(r.get('confirmacoes_smc',[]))}"
                )
            await enviar("\n".join(linhas))

    except Exception as e:
        logger.warning(f"Early Entry shadow erro: {e}")

if __name__ == "__main__":
    asyncio.run(main())
