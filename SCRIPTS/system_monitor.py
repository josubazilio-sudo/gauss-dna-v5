import psutil
import logging
import time

log = logging.getLogger("SystemMonitor")

def log_resources():
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=1)
    
    log.info(f"MONITOR: RAM={mem.percent}% ({mem.available // 1024 // 1024}MB free) | CPU={cpu}%")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", filename="SYSTEM_STATS.log")
    while True:
        log_resources()
        time.sleep(600) # 10 min
