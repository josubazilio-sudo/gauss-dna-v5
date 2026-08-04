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

        # Verificar se passou mais de 30 minutos sem sinal
        cache_file = "/tmp/k11_sent.json"
        diag_file  = "/tmp/k11_last_diag.json"
        try:
            now = t.time()
            # Último sinal enviado
            cache = json.load(open(cache_file)) if os.path.exists(cache_file) else {}
            ultimo_sinal = max(cache.values()) if cache else 0
            # Último diagnóstico enviado
            diag_cache = json.load(open(diag_file)) if os.path.exists(diag_file) else {"ts": 0}
            ultimo_diag = diag_cache.get("ts", 0)

            sem_sinal_ha = (now - ultimo_sinal) / 60  # minutos
            sem_diag_ha  = (now - ultimo_diag) / 60

            # Enviar diagnóstico se: +30min sem sinal E +30min sem diagnóstico
            if sem_sinal_ha >= 30 and sem_diag_ha >= 30:
                # Pegar top 5 mais próximos de aprovação
                from k10_engine import K10Engine
                from watchlist import get_watchlist, WATCHLIST_FALLBACK, WATCHLIST_PRIORITY
                engine2 = K10Engine()
                wl2 = (WATCHLIST_PRIORITY + (get_watchlist(min_volume_usdt=100_000) or WATCHLIST_FALLBACK))[:50]

                todos = []
                def analisar2(sym):
                    try: return engine2.analisar(sym)
                    except: return None

                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=6) as ex2:
                    futures2 = {ex2.submit(analisar2, s): s for s in wl2}
                    for f2 in as_completed(futures2):
                        r2 = f2.result()
                        if r2 and r2.get("score",0) > 0:
                            todos.append(r2)

                todos.sort(key=lambda x: x.get("score",0), reverse=True)
                top5 = todos[:5]

                # Montar diagnóstico explicativo
                from datetime import datetime, timezone
                hora = datetime.now(timezone.utc).strftime("%H:%M UTC")
                linhas = [
                    f"📊 K11 — SEM SINAL há {sem_sinal_ha:.0f} minutos",
                    f"🕐 {hora} | Mercado em análise",
                    "━━━━━━━━━━━━━━",
                    "🔍 TOP ATIVOS MAIS PRÓXIMOS:",
                    ""
                ]
                for r2 in top5:
                    sym    = r2.get("symbol","").replace("/USDT:USDT","")
                    score  = r2.get("score", 0)
                    motivo = (r2.get("motivos_rejeicao") or ["ok"])[0][:40]
                    rvol   = r2.get("rvol", 0)
                    tf     = r2.get("timeframe","?")
                    falta  = "✅ Quase lá!" if score >= 65 else "⏳ Aguardando"
                    linhas.append(f"{falta} {sym} | s={score} | {tf} | RVOL {rvol:.2f}")
                    linhas.append(f"   → {motivo}")

                linhas += [
                    "",
                    "━━━━━━━━━━━━━━",
                    "💡 O mercado está:",
                ]
                # Diagnóstico geral
                scores = [r2.get("score",0) for r2 in todos]
                rvols  = [r2.get("rvol",0) for r2 in todos if r2.get("rvol",0) > 0]
                med_score = sum(scores)/len(scores) if scores else 0
                med_rvol  = sum(rvols)/len(rvols) if rvols else 0

                if med_rvol < 0.7:
                    linhas.append("📉 Volume baixo — institucional ausente")
                if med_score < 50:
                    linhas.append("😴 Sem momentum — aguardar movimento")
                motivos_freq = {}
                for r2 in todos:
                    for m in (r2.get("motivos_rejeicao") or []):
                        chave = m[:30]
                        motivos_freq[chave] = motivos_freq.get(chave, 0) + 1
                top_motivo = max(motivos_freq, key=motivos_freq.get) if motivos_freq else ""
                if top_motivo:
                    linhas.append(f"🚫 Principal bloqueio: {top_motivo}")

                linhas.append("━━━━━━━━━━━━━━")
                linhas.append("K11 continua monitorando...")

                await enviar("\n".join(linhas))

                # Salvar timestamp do diagnóstico
                with open(diag_file, "w") as f:
                    json.dump({"ts": now}, f)
        except Exception as e:
            logger.warning(f"Diag automático: {e}")

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
