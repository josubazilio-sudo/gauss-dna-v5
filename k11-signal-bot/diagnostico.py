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
                    "motivos_rejeicao":[str(e)[:60]],"timeframe":"?","direcao":"?",
                    "rvol":0,"adx":0,"nivel_decisao":0,"log_reversao":""})

        resultados.sort(key=lambda x: x.get("score",0), reverse=True)
        aprovados = [r for r in resultados if r.get("aprovado")]

        linhas = [f"K11 DIAG V4.3.2 — {len(aprovados)} aprovados de {len(resultados)}:\n"]

        for r in resultados[:10]:
            sym    = r["symbol"].replace("/USDT:USDT","")
            ok     = "✅" if r.get("aprovado") else "❌"
            motivo = (r.get("motivos_rejeicao") or ["ok"])[0][:45]
            nivel  = r.get("nivel_decisao", 0)
            log    = r.get("log_reversao","")
            rvol   = r.get("rvol", 0)

            linha = f"{ok} {sym} s={r.get('score')} rr={r.get('rr',0):.1f} rvol={rvol:.2f}"
            if nivel > 0:
                linha += f" [N{nivel}]"
            linha += f"\n   {motivo}"

            if log:
                try:
                    parts = {}
                    for p in log.replace("__LOG_REVERSAO__ ","").split():
                        if "=" in p:
                            k,v = p.split("=",1)
                            parts[k] = v
                    linha += (
                        f"\n   BOS/CHoCH: {'SIM' if parts.get('bos','False')=='True' else 'NÃO'}"
                        f"\n   H1 contra: {'SIM' if parts.get('h1_contra','False')=='True' else 'NÃO'}"
                        f"\n   RVOL crítico: {'SIM' if float(parts.get('rvol',1)) < 1.2 else 'NÃO'}"
                        f"\n   ADX H4: {parts.get('adx4h','?')}"
                        f"\n   Nível aplicado: {parts.get('nivel','?')}"
                    )
                except: pass

            linhas.append(linha)

        await tg("\n".join(linhas))

        if aprovados:
            from formatter import formatar_cartao
            cartao = formatar_cartao(aprovados[0], bot_name="K11")
            if cartao: await tg(cartao)

    except Exception:
        await tg("K11 ERRO:\n" + traceback.format_exc()[-2000:])

asyncio.run(main())
