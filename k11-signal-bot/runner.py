"""
K11 Runner — SMC Engine
"""
import asyncio, logging, os, httpx, traceback, json, time as t
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
        logger.info(f"TG: {r.status_code}")

async def main():
    logger.info("K11 SMC iniciado")
    try:
        from k10_engine import K10Engine
        from watchlist import get_watchlist, WATCHLIST_FALLBACK, WATCHLIST_PRIORITY
        from trade_tracker import registrar

        engine = K10Engine()
        wl_geral = get_watchlist(min_volume_usdt=100_000) or WATCHLIST_FALLBACK
        wl_sem_dup = [p for p in wl_geral if p not in WATCHLIST_PRIORITY]
        wl = WATCHLIST_PRIORITY + wl_sem_dup[:490]

        aprovados = []
        def analisar(sym):
            try: return engine.analisar(sym)
            except: return None

        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(analisar, sym): sym for sym in wl}
            for f in as_completed(futures):
                r = f.result()
                if r and r.get("aprovado") and r.get("score",0) >= 70:
                    aprovados.append(r)

        aprovados.sort(key=lambda x: x.get("score",0), reverse=True)
        logger.info(f"K11: {len(aprovados)} aprovados")

    except Exception:
        logger.error(traceback.format_exc())
        return

    if not aprovados:
        logger.info("K11: nenhum sinal")
        return

    # Anti-repetição 2h
    cache_file = "/tmp/k11_sent.json"
    try:
        cache = json.load(open(cache_file)) if os.path.exists(cache_file) else {}
        now = t.time()
        cache = {k:v for k,v in cache.items() if now-v < 7200}
    except:
        cache = {}

    enviados = 0
    for sinal in aprovados[:3]:
        chave = f"{sinal['symbol']}_{sinal['direcao']}_{sinal['timeframe']}"
        if chave in cache:
            continue

        cartao = formatar_cartao(sinal, bot_name="K11")
        if cartao:
            await enviar(cartao)
            cache[chave] = t.time()
            try:
                trade_id = registrar(sinal)
                logger.info(f"K11 #{trade_id}: {sinal['symbol']} {sinal['direcao']} score={sinal['score']}")
            except Exception as e:
                logger.warning(f"Tracker: {e}")
            enviados += 1
            await asyncio.sleep(2)

    try:
        with open(cache_file, "w") as f:
            json.dump(cache, f)
    except:
        pass

    logger.info(f"K11: {enviados} sinais enviados")

if __name__ == "__main__":
    asyncio.run(main())
