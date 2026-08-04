import asyncio, httpx, os, sys, traceback
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
        from watchlist import get_watchlist, WATCHLIST_FALLBACK

        engine = K10Engine()
        wl = get_watchlist(min_volume_usdt=100_000) or WATCHLIST_FALLBACK

        resultados = []
        for sym in wl[:15]:
            try:
                # Testar cada TF diretamente para pegar erro real
                melhor = None
                erro_tf = ""
                for tf, ctx in [("30m","1h"),("1h","4h")]:
                    try:
                        r = engine._analisar_tf(sym, tf, tf_contexto=ctx)
                        if melhor is None or r.get("score",0) > melhor.get("score",0):
                            melhor = r
                    except Exception as e:
                        erro_tf = f"{tf}: {str(e)[:50]}"

                if melhor:
                    if "symbol" not in melhor:
                        melhor["symbol"] = sym
                    resultados.append(melhor)
                else:
                    resultados.append({"symbol":sym,"score":0,"aprovado":False,
                        "motivos_rejeicao":[erro_tf or "Todos TFs falharam"],
                        "timeframe":"?","direcao":"?","rvol":0})
            except Exception as e:
                resultados.append({"symbol":sym,"score":0,"aprovado":False,
                    "motivos_rejeicao":[f"{type(e).__name__}: {str(e)[:60]}"],
                    "timeframe":"?","direcao":"?","rvol":0})

        resultados.sort(key=lambda x: x.get("score",0), reverse=True)
        aprovados = [r for r in resultados if r.get("aprovado")]

        linhas = [f"K11 DIAG — {len(aprovados)} aprovados:\n"]
        for r in resultados[:12]:
            sym    = r.get("symbol","?").replace("/USDT:USDT","")
            ok     = "✅" if r.get("aprovado") else "❌"
            motivo = (r.get("motivos_rejeicao") or ["ok"])[0][:60]
            tf     = r.get("timeframe","?")
            rvol   = r.get("rvol",0)
            t_score= r.get("score_timing","")
            t_str  = f" T={t_score}" if t_score else ""
            linhas.append(f"{ok} {sym} s={r.get('score')} {tf} rv={rvol:.2f}{t_str}\n   {motivo}")

        await tg("\n".join(linhas))

        if aprovados:
            from formatter import formatar_cartao
            cartao = formatar_cartao(aprovados[0], bot_name="K11")
            if cartao: await tg(cartao)

    except Exception:
        await tg("ERRO:\n" + traceback.format_exc()[-2000:])

asyncio.run(main())
