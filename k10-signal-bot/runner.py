"""
K10 Runner — GitHub Actions, a cada 15min
"""
import asyncio, logging, os, httpx
from scanner import K10Scanner
from formatter import formatar_cartao
from config import BOT_TOKEN, ALLOWED_CHAT_IDS

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
CHAT_ID = ALLOWED_CHAT_IDS[0] if ALLOWED_CHAT_IDS else None

async def enviar(texto: str):
    if not CHAT_ID or not BOT_TOKEN:
        logger.error("BOT_TOKEN ou CHAT_ID ausentes")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={"chat_id": CHAT_ID, "text": texto[:4096]})
        logger.info(f"Telegram: {r.status_code}")
        if r.status_code != 200:
            logger.error(r.text)

async def main():
    logger.info("K10 Runner iniciado")
    scanner = K10Scanner(max_workers=6)
    aprovados = scanner.scan(min_score=75, max_ativos=500)

    if not aprovados:
        logger.info("Nenhum sinal aprovado neste ciclo")
        return

    # Envia top 3 sinais aprovados
    for sinal in aprovados[:3]:
        cartao = formatar_cartao(sinal)
        await enviar(cartao)
        logger.info(f"Enviado: {sinal['symbol']} score={sinal['score']}")
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
