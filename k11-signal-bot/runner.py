"""
K11 Runner
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
        logger.error(f"Config ausente: CHAT_ID={CHAT_ID} BOT_TOKEN={'ok' if BOT_TOKEN else 'vazio'}")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={"chat_id": CHAT_ID, "text": texto[:4096]})
        logger.info(f"Telegram K11: {r.status_code}")
        if r.status_code != 200:
            logger.error(r.text)

async def main():
    logger.info(f"K11 iniciado | CHAT_ID={CHAT_ID} | TOKEN={'ok' if BOT_TOKEN else 'VAZIO'}")
    
    try:
        scanner = K10Scanner(max_workers=6)
        aprovados = scanner.scan(min_score=75, max_ativos=500)
        logger.info(f"K11 scan: {len(aprovados)} aprovados")
    except Exception as e:
        logger.error(f"Erro scan: {traceback.format_exc()}")
        await enviar(f"K11 ERRO scan: {e}")
        return

    if not aprovados:
        logger.info("K11: nenhum sinal aprovado")
        return

    for sinal in aprovados[:3]:
        try:
            cartao = formatar_cartao(sinal)
            cartao = cartao.replace("K10 | Adaptativo Institucional", "K11 | Adaptativo Institucional")
            await enviar(cartao)
            logger.info(f"K11 enviado: {sinal['symbol']} score={sinal['score']}")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Erro envio: {e}")

if __name__ == "__main__":
    asyncio.run(main())
