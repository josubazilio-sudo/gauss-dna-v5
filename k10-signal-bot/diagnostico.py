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
        engine = K10Engine()
        wl = get_watchlist(min_volume_usdt=100_000) or WATCHLIST_FALLBACK

        resultados = []
        for sym in wl[:15]:
            try:
                r = engine.analisar(sym)
                resultados.append(r)
            except Exception as e:
                resultados.append({"symbol":sym,"score":0,"aprovado":False,
                    "motivos_rejeicao":[str(e)],"timeframe":"?"})

        resultados.sort(key=lambda x: x.get("score",0), reverse=True)

        linhas = ["K10 DIAG — top 10 scores:\n"]
        for r in resultados[:10]:
            sym    = r["symbol"].replace("/USDT:USDT","")
            ok     = "✅" if r.get("aprovado") else "❌"
            motivo = (r.get("motivos_rejeicao") or ["?"])[0][:50]
            confs  = r.get("confirmacoes_smc",[])
            linhas.append(
                f"{ok} {sym} score={r.get('score')} tf={r.get('timeframe','?')} dir={r.get('direcao','?')}\n"
                f"   {motivo}\n"
                f"   confs: {confs}"
            )

        aprovados = [r for r in resultados if r.get("aprovado")]
        linhas.append(f"\n{len(aprovados)} aprovados de {len(resultados)} analisados")
        await tg("\n".join(linhas))

    except Exception:
        await tg("ERRO:\n" + traceback.format_exc()[-2000:])

asyncio.run(main())
