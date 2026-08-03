import asyncio, logging, os, httpx, traceback, sys
sys.path.insert(0, ".")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("ALLOWED_CHAT_IDS", "").split(",")[0].strip()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def tg(msg):
    logger.info(f"Enviando: {msg[:80]}")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={"chat_id": CHAT_ID, "text": msg[:4096]})
        logger.info(f"TG status: {r.status_code} {r.text[:100]}")

async def main():
    logger.info(f"BOT_TOKEN={BOT_TOKEN[:10]}... CHAT_ID={CHAT_ID}")
    await tg(f"K11 DEBUG\nBOT ok: {bool(BOT_TOKEN)}\nCHAT: {CHAT_ID}")

    try:
        from scanner import K10Scanner
        scanner = K10Scanner(max_workers=4)
        await tg("K11: scanner criado, iniciando scan...")
        
        aprovados = scanner.scan(min_score=75, max_ativos=50)
        await tg(f"K11: {len(aprovados)} aprovados de 50 analisados")
        
        if aprovados:
            from formatter import formatar_cartao
            cartao = formatar_cartao(aprovados[0])
            cartao = cartao.replace("K10 | Adaptativo Institucional", "K11 | Adaptativo Institucional")
            await tg(cartao)
        else:
            # Mostrar top 3 scores mesmo sem aprovar
            from watchlist import get_watchlist, WATCHLIST_FALLBACK
            from k10_engine import K10Engine
            engine = K10Engine()
            wl = (get_watchlist() or WATCHLIST_FALLBACK)[:10]
            resultados = []
            for sym in wl:
                try:
                    r = engine.analisar(sym)
                    resultados.append(r)
                except: pass
            resultados.sort(key=lambda x: x.get("score",0), reverse=True)
            linhas = ["K11 top scores:\n"]
            for r in resultados[:5]:
                sym = r["symbol"].replace("/USDT:USDT","")
                motivo = (r.get("motivos_rejeicao") or ["?"])[0][:50]
                linhas.append(f"score={r.get('score')} {sym} tf={r.get('timeframe')}\n-> {motivo}")
            await tg("\n".join(linhas))
    except Exception:
        await tg(f"K11 ERRO:\n{traceback.format_exc()[-2000:]}")

asyncio.run(main())
