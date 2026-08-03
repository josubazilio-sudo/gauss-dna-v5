"""
K11 Runner — Core Freeze V1
"""
import asyncio, logging, os, httpx, traceback
from scanner import K10Scanner
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
        logger.info(f"Telegram K11: {r.status_code}")

async def main():
    logger.info("K11 iniciado")
    try:
        scanner = K10Scanner(max_workers=6)
        aprovados = scanner.scan(min_score=70, max_ativos=500)
        logger.info(f"K11: {len(aprovados)} aprovados")
    except Exception:
        logger.error(traceback.format_exc())
        return

    if not aprovados:
        logger.info("K11: nenhum sinal neste ciclo")
        return

    def prioridade(r):
        return r.get("score",0)*0.5 + min(r.get("rvol",0)*10,30)*0.3 + r.get("confluencia",0)*0.2

    aprovados.sort(key=prioridade, reverse=True)

    for sinal in aprovados[:3]:
        cartao = formatar_cartao(sinal, bot_name="K11")
        if cartao:
            await enviar(cartao)
            logger.info(f"K11: {sinal['symbol']} score={sinal['score']}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
