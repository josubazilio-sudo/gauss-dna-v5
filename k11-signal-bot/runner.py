"""
K11 Runner — com Trade Tracker
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
        logger.info(f"K11 TG: {r.status_code}")

async def main():
    logger.info("K11 iniciado")
    try:
        from k10_engine import K10Engine
        from watchlist import get_watchlist, WATCHLIST_FALLBACK
        from trade_tracker import registrar, relatorio_telegram

        engine = K10Engine()
        # Pares prioritários primeiro, depois watchlist geral
        from watchlist import get_watchlist, WATCHLIST_FALLBACK, WATCHLIST_PRIORITY
        wl_geral = get_watchlist(min_volume_usdt=100_000) or WATCHLIST_FALLBACK
        # Remover duplicatas mantendo prioritários na frente
        wl_geral_sem_dup = [p for p in wl_geral if p not in WATCHLIST_PRIORITY]
        wl = WATCHLIST_PRIORITY + wl_geral_sem_dup[:490]
        aprovados = []

        def analisar(sym):
            try: return engine.analisar(sym)
            except: return None

        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(analisar, sym): sym for sym in wl}
            for f in as_completed(futures):
                r = f.result()
                if r and r.get("aprovado") and r.get("score", 0) >= 70:
                    aprovados.append(r)

        aprovados.sort(key=lambda x: x.get("score", 0), reverse=True)
        logger.info(f"K11: {len(aprovados)} aprovados")

    except Exception:
        logger.error(traceback.format_exc())
        return

    if not aprovados:
        logger.info("K11: nenhum sinal")
        return

    # Anti-repetição — não enviar mesmo símbolo+direção+TF nas últimas 2h
    import json, os, time as t
    cache_file = "/tmp/k11_sent.json"
    try:
        cache = json.load(open(cache_file)) if os.path.exists(cache_file) else {}
        # Limpar entradas antigas (>2h)
        now = t.time()
        cache = {k:v for k,v in cache.items() if now-v < 7200}
    except:
        cache = {}

    aprovados_novos = []
    for s in aprovados:
        chave = f"{s['symbol']}_{s['direcao']}_{s['timeframe']}"
        if chave not in cache:
            aprovados_novos.append(s)
        else:
            logger.info(f"K11: {s['symbol']} já enviado recentemente — ignorando")

    if not aprovados_novos:
        logger.info("K11: todos sinais já enviados recentemente")
        return

    for sinal in aprovados_novos[:3]:
        cartao = formatar_cartao(sinal, bot_name="K11")
        if cartao:
            await enviar(cartao)
            try:
                trade_id = registrar(sinal)
                logger.info(f"K11 #{trade_id}: {sinal['symbol']} {sinal['direcao']} score={sinal['score']}")
            except Exception as e:
                logger.warning(f"Tracker: {e}")
            # Salvar no cache anti-repetição
            chave = f"{sinal['symbol']}_{sinal['direcao']}_{sinal['timeframe']}"
            cache[chave] = t.time()
            await asyncio.sleep(2)

    try:
        with open(cache_file, "w") as f:
            json.dump(cache, f)
    except:
        pass

if __name__ == "__main__":
    asyncio.run(main())
