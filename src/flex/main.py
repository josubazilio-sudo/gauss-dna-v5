"""SINAIS TOP — Entry Point (scanner contínuo + diagnóstico 30min)"""

import asyncio
import logging
import sys
import os
import time

_SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _SRC_PATH in sys.path:
    sys.path.remove(_SRC_PATH)
sys.path.insert(0, _SRC_PATH)

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip("'\"")
            if _k and not os.environ.get(_k):
                os.environ[_k] = _v

from flex.cycle import main_cycle

INTERVALO_SCAN = int(os.getenv("FLEX_INTERVALO_SCAN", "10"))
INTERVALO_DIAG_MIN = int(os.getenv("FLEX_INTERVALO_DIAG", "30"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)


async def loop_infinito():
    logger.info("SINAIS TOP — Scanner contínuo (scan a cada %ds, diagnóstico a cada %d min)",
                INTERVALO_SCAN, INTERVALO_DIAG_MIN)
    ciclo = 0
    ultimo_diag = time.monotonic() - INTERVALO_DIAG_MIN * 60  # primeiro ciclo envia diagnóstico
    while True:
        ciclo += 1
        agora = time.monotonic()
        enviar_diag = (agora - ultimo_diag) >= INTERVALO_DIAG_MIN * 60
        logger.info("=== CICLO %d (diagnóstico: %s) ===", ciclo, "SIM" if enviar_diag else "não")
        try:
            await main_cycle(send_diag=enviar_diag)
            if enviar_diag:
                ultimo_diag = time.monotonic()
        except Exception as e:
            logger.exception("Erro no ciclo %d: %s", ciclo, e)
        await asyncio.sleep(INTERVALO_SCAN)


if __name__ == "__main__":
    asyncio.run(loop_infinito())
