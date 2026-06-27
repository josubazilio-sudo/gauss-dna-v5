import asyncio
import logging
import os
import sys

from cycles import main_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
    force=True,
)

if __name__ == "__main__":
    asyncio.run(main_cycle())
