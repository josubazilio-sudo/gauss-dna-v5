import asyncio, logging, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            os.environ.setdefault(k, v)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
    stream=sys.stdout,
    force=True,
)

from flex.cycle import main_cycle
asyncio.run(main_cycle(send_diag=True))
