"""
REVERSE Runner — K10 normal em H4 e Diário
Sinal sem inversão — para comparar com K11
"""
import asyncio, logging, os, httpx, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        logger.info(f"REVERSE TG: {r.status_code}")

async def main():
    logger.info("REVERSE H4/D1 iniciado")
    try:
        from k10_engine import K10Engine
        from watchlist import get_watchlist, WATCHLIST_FALLBACK

        engine = K10Engine()
        wl = (get_watchlist(min_volume_usdt=500_000) or WATCHLIST_FALLBACK)[:300]
        aprovados = []

        def analisar(sym):
            melhores = []
            for tf in ["4h", "1d"]:
                try:
                    r = engine._analisar_tf(sym, tf)
                    melhores.append(r)
                except:
                    pass
            if not melhores: return None
            return max(melhores, key=lambda x: x.get("score", 0))

        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(analisar, sym): sym for sym in wl}
            for f in as_completed(futures):
                r = f.result()
                if r and r.get("aprovado") and r.get("score", 0) >= 65:
                    aprovados.append(r)

        aprovados.sort(key=lambda x: x.get("score", 0), reverse=True)
        logger.info(f"REVERSE: {len(aprovados)} aprovados H4/D1")

    except Exception:
        logger.error(traceback.format_exc())
        return

    if not aprovados:
        logger.info("REVERSE: nenhum sinal")
        return

    for sinal in aprovados[:3]:
        cartao = formatar_cartao(sinal, bot_name="REVERSE")
        if cartao:
            await enviar(cartao)
            logger.info(f"REVERSE: {sinal['symbol']} {sinal['direcao']} {sinal['timeframe']} score={sinal['score']}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
