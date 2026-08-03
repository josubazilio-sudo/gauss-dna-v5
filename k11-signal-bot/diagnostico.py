import asyncio, httpx, os, sys, traceback
sys.path.insert(0, ".")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("ALLOWED_CHAT_IDS", "").split(",")[0].strip()

async def tg(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={"chat_id": CHAT_ID, "text": msg[:4000]})
        print(f"TG: {r.status_code}")

async def main():
    try:
        from k10_engine import K10Engine
        from watchlist import get_watchlist, WATCHLIST_FALLBACK
        from formatter import formatar_cartao

        engine = K10Engine()
        wl = get_watchlist(min_volume_usdt=100_000) or WATCHLIST_FALLBACK

        resultados = []
        for sym in wl[:15]:
            try:
                r = engine.analisar(sym)
                resultados.append(r)
            except Exception as e:
                resultados.append({"symbol":sym,"score":0,"aprovado":False,
                    "motivos_rejeicao":[str(e)[:50]],"timeframe":"?","direcao":"?"})

        resultados.sort(key=lambda x: x.get("score",0), reverse=True)
        aprovados = [r for r in resultados if r.get("aprovado")]

        linhas = [f"K11 DIAG — {len(aprovados)} aprovados de {len(resultados)}:\n"]
        for r in resultados[:8]:
            sym    = r["symbol"].replace("/USDT:USDT","")
            ok     = "OK" if r.get("aprovado") else "X"
            motivo = (r.get("motivos_rejeicao") or ["ok"])[0][:40]
            linhas.append(f"{ok} {sym} s={r.get('score')} rr={r.get('rr',0)} -> {motivo}")

        await tg("\n".join(linhas))

        if aprovados:
            cartao = formatar_cartao(aprovados[0], bot_name="K11")
            if cartao:
                await tg(cartao)

    except Exception:
        await tg("K11 ERRO:\n" + traceback.format_exc()[-2000:])

asyncio.run(main())
