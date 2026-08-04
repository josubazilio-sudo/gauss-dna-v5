"""
REVERSE Runner — Inverte os sinais do K10
LONG vira SHORT, SHORT vira LONG
Teste: se o K10 está sempre errado, o REVERSE ganha
"""
import asyncio, logging, os, httpx, traceback
from scanner import K10Scanner
from formatter import formatar_cartao
from config import BOT_TOKEN, ALLOWED_CHAT_IDS

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
CHAT_ID = ALLOWED_CHAT_IDS[0] if ALLOWED_CHAT_IDS else None

def inverter_sinal(sinal: dict) -> dict:
    """Inverte completamente a direção do sinal."""
    s = sinal.copy()

    # Inverter direção
    s["direcao"] = "SHORT" if sinal["direcao"] == "LONG" else "LONG"

    # Trocar TP e Stop
    entrada = sinal["entrada"]
    stop_orig = sinal["stop"]
    tp1_orig  = sinal["tp1"]

    # Novo stop = onde era o TP1, novo TP = onde era o stop
    dist_stop = abs(entrada - stop_orig)
    dist_tp   = abs(entrada - tp1_orig)

    if s["direcao"] == "SHORT":
        s["stop"] = round(entrada + dist_stop, 6)
        s["tp1"]  = round(entrada - dist_tp, 6)
        s["tp2"]  = s["tp1"]
        s["regime"] = sinal.get("regime","").replace("Alta","Baixa").replace("LONG","SHORT").replace("↑","↓").replace("↗","↘")
    else:
        s["stop"] = round(entrada - dist_stop, 6)
        s["tp1"]  = round(entrada + dist_tp, 6)
        s["tp2"]  = s["tp1"]
        s["regime"] = sinal.get("regime","").replace("Baixa","Alta").replace("SHORT","LONG").replace("↓","↑").replace("↘","↗")

    # TP nunca negativo
    if s["tp1"] <= 0: s["tp1"] = round(entrada * 0.92, 6)

    return s

async def enviar(texto: str):
    if not CHAT_ID or not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={"chat_id": CHAT_ID, "text": texto[:4096]})
        logger.info(f"REVERSE TG: {r.status_code}")

async def main():
    logger.info("REVERSE iniciado")
    try:
        scanner = K10Scanner(max_workers=6)
        # REVERSE: apenas H4 e Diário — movimentos maiores, menos ruído
        from watchlist import get_watchlist, WATCHLIST_FALLBACK
        from k10_engine import K10Engine
        from concurrent.futures import ThreadPoolExecutor, as_completed

        engine = K10Engine()
        wl = (get_watchlist(min_volume_usdt=500_000) or WATCHLIST_FALLBACK)[:300]
        aprovados = []

        def analisar_htf(sym):
            resultados = []
            for tf in ["4h", "1d"]:
                try:
                    r = engine._analisar_tf(sym, tf)
                    resultados.append(r)
                except:
                    pass
            if not resultados: return None
            return max(resultados, key=lambda x: x.get("score", 0))

        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(analisar_htf, sym): sym for sym in wl}
            for f in as_completed(futures):
                r = f.result()
                if r and r.get("aprovado") and r.get("score", 0) >= 65:
                    aprovados.append(r)

        aprovados.sort(key=lambda x: x.get("score", 0), reverse=True)
        logger.info(f"REVERSE: {len(aprovados)} sinais do K10")
    except Exception:
        logger.error(traceback.format_exc())
        return

    if not aprovados:
        logger.info("REVERSE: nenhum sinal neste ciclo")
        return

    aprovados.sort(key=lambda x: x.get("score",0), reverse=True)

    for sinal in aprovados[:3]:
        invertido = inverter_sinal(sinal)
        cartao = formatar_cartao(invertido, bot_name="REVERSE")
        if cartao:
            await enviar(cartao)
            logger.info(f"REVERSE: {sinal['symbol']} {sinal['direcao']}→{invertido['direcao']} score={sinal['score']}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
