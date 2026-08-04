import asyncio, httpx, os, sys, traceback
sys.path.insert(0, ".")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("ALLOWED_CHAT_IDS", "").split(",")[0].strip()

async def tg(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={"chat_id": CHAT_ID, "text": msg[:4000]})

async def main():
    try:
        from k10_engine import K10Engine
        from watchlist import get_watchlist, WATCHLIST_FALLBACK
        from formatter import formatar_cartao

        engine = K10Engine()
        wl = get_watchlist(min_volume_usdt=100_000) or WATCHLIST_FALLBACK

        # Analisar top 15
        resultados = []
        for sym in wl[:15]:
            try:
                # Testar cada TF separadamente para ver qual bloqueia
                melhor = {"score": 0}
                for tf, ctx in [("30m","1h"), ("1h","4h"), ("4h","1d")]:
                    try:
                        r = engine._analisar_tf(sym, tf, tf_contexto=ctx)
                        if r.get("score",0) > melhor.get("score",0):
                            melhor = r
                    except:
                        pass
                resultados.append(melhor)
            except Exception as e:
                resultados.append({"symbol":sym,"score":0,"aprovado":False,
                    "motivos_rejeicao":[str(e)[:50]],"timeframe":"?","direcao":"?","rvol":0})

        resultados.sort(key=lambda x: x.get("score",0), reverse=True)
        aprovados = [r for r in resultados if r.get("aprovado")]

        linhas = [f"K11 DIAG — {len(aprovados)} aprovados de {len(resultados)}:\n"]
        for r in resultados[:12]:
            sym    = r["symbol"].replace("/USDT:USDT","")
            ok     = "✅" if r.get("aprovado") else "❌"
            motivo = (r.get("motivos_rejeicao") or ["ok"])[0][:50]
            tf     = r.get("timeframe","?")
            linhas.append(f"{ok} {sym} s={r.get('score')} tf={tf} rvol={r.get('rvol',0):.2f}\n   {motivo}")

        await tg("\n".join(linhas))

        for s in aprovados[:2]:
            cartao = formatar_cartao(s, bot_name="K11")
            if cartao: await tg(cartao)

    except Exception:
        await tg("ERRO:\n" + traceback.format_exc()[-2000:])

asyncio.run(main())
