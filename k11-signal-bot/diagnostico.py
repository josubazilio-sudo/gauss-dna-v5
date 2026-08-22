import asyncio, httpx, os, sys, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, ".")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("ALLOWED_CHAT_IDS", "").split(",")[0].strip()

async def tg(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(url, json={"chat_id": CHAT_ID, "text": msg[:4000]})

async def main():
    try:
        from k10_engine import K10Engine
        from watchlist import get_watchlist, WATCHLIST_FALLBACK, WATCHLIST_PRIORITY
        from formatter import formatar_cartao

        engine = K10Engine()

        # Buscar watchlist completa
        wl_geral = get_watchlist(min_volume_usdt=50_000) or WATCHLIST_FALLBACK
        wl_sem_dup = [p for p in wl_geral if p not in WATCHLIST_PRIORITY]
        wl = WATCHLIST_PRIORITY + wl_sem_dup
        total_pares = len(wl)

        await tg(f"K11 DIAG iniciando... {total_pares} pares")

        # Escanear todos em paralelo
        resultados = []
        def analisar(sym):
            try:
                r = engine.analisar(sym)
                if r and "symbol" not in r: r["symbol"] = sym
                return r
            except Exception as e:
                return {"symbol":sym,"score":0,"aprovado":False,
                    "motivos_rejeicao":[str(e)[:50]],"timeframe":"?","direcao":"?","rvol":0}

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(analisar, sym): sym for sym in wl[:300]}
            for f in as_completed(futures):
                r = f.result()
                if r: resultados.append(r)

        resultados.sort(key=lambda x: x.get("score",0), reverse=True)
        aprovados = [r for r in resultados if r.get("aprovado")]

        linhas = [f"K11 DIAG — {len(aprovados)} aprovados de {len(resultados)} escaneados:\n"]
        for r in resultados[:12]:
            sym    = r.get("symbol","?").replace("/USDT:USDT","")
            ok     = "✅" if r.get("aprovado") else "❌"
            motivo = (r.get("motivos_rejeicao") or ["ok"])[0][:50]
            tf     = r.get("timeframe","?")
            rvol   = r.get("rvol",0)
            t_score= r.get("score_timing","")
            t_str  = f" T={t_score}" if t_score else ""
            linhas.append(f"{ok} {sym} s={r.get('score')} {tf} rv={rvol:.2f}{t_str}\n   {motivo}")

        await tg("\n".join(linhas))

        for s in aprovados[:3]:
            cartao = formatar_cartao(s, bot_name="K12")
            if cartao: await tg(cartao)

    except Exception:
        await tg("ERRO:\n" + traceback.format_exc()[-2000:])

asyncio.run(main())
