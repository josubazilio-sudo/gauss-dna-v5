"""
K10 Runner — Executado pelo GitHub Actions a cada 15min
Roda o scan completo e envia os melhores sinais no Telegram
"""

import asyncio
import logging
import os
import httpx
from scanner import K10Scanner
from formatter import formatar_cartao
from config import BOT_TOKEN, ALLOWED_CHAT_IDS

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

CHAT_ID = ALLOWED_CHAT_IDS[0] if ALLOWED_CHAT_IDS else None

async def enviar_mensagem(texto: str):
    if not CHAT_ID or not BOT_TOKEN:
        logger.error("BOT_TOKEN ou CHAT_ID não configurados")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload)
        if r.status_code != 200:
            logger.error(f"Telegram erro: {r.text}")

async def main():
    logger.info("🚀 K10 Runner iniciado")
    scanner = K10Scanner(max_workers=6)

    # Scan completo
    aprovados = scanner.scan(min_score=70, max_ativos=300)

    if not aprovados:
        logger.info("Nenhum sinal aprovado — sem envio")
        return

    # Envia o melhor sinal como cartão completo
    melhor = aprovados[0]
    cartao = formatar_cartao(melhor)
    await enviar_mensagem(cartao)
    logger.info(f"✅ Cartão enviado: {melhor['symbol']} score={melhor['score']}")

    # Se tiver mais sinais, envia resumo
    if len(aprovados) > 1:
        scanner2 = K10Scanner.__new__(K10Scanner)
        resumo = scanner.formatar_resumo(aprovados[1:], "multi-tf")
        await enviar_mensagem(resumo)

if __name__ == "__main__":
    asyncio.run(main())
