"""
K11 Runner — Core Freeze V1
Padrão operacional estável — alterações somente após 50+ trades
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
    logger.info("K11 Core Freeze V1 — iniciado")
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

    # Priorização Core Freeze V1: Score > RVOL > Estrutura > Timing
    def prioridade(r):
        score  = r.get("score", 0)
        rvol   = min(r.get("rvol", 0) * 10, 30)
        conf   = r.get("confluencia", 0)
        return score * 0.5 + rvol * 0.3 + conf * 0.2

    aprovados.sort(key=prioridade, reverse=True)

    # Enviar top 2-3 sinais de maior qualidade
    enviados = 0
    for sinal in aprovados[:3]:
        cartao = formatar_cartao(sinal, bot_name="K11")
        if cartao:
            await enviar(cartao)
            logger.info(f"K11: {sinal['symbol']} score={sinal['score']} rvol={sinal.get('rvol',0):.2f}")
            enviados += 1
            await asyncio.sleep(2)

    logger.info(f"K11: {enviados} sinais enviados neste ciclo")

if __name__ == "__main__":
    asyncio.run(main())
