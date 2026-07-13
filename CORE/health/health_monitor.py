import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Callable

log = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    healthy: bool = True
    exchange_ok: bool = False
    exchange_latency_ms: float = 0.0
    database_ok: bool = False
    database_size_mb: float = 0.0
    cpu_pct: float = 0.0
    memory_pct: float = 0.0
    uptime_hours: float = 0.0
    last_check: str = ""
    errors: List[str] = field(default_factory=list)


class HealthMonitor:
    def __init__(self, ping_fn=None, db_path: Optional[str] = None):
        self.ping_fn = ping_fn
        self.db_path = db_path
        self._callbacks: List[Callable] = []
        self._start_time = time.time()
        self._running = False
        self._last_status: Optional[HealthStatus] = None

    def on_unhealthy(self, callback):
        self._callbacks.append(callback)

    async def check(self) -> HealthStatus:
        status = HealthStatus(
            last_check=datetime.now(timezone.utc).isoformat(),
            uptime_hours=round((time.time() - self._start_time) / 3600, 2),
        )
        errors = []

        if self.ping_fn:
            try:
                t0 = time.monotonic()
                ok = await self.ping_fn()
                status.exchange_latency_ms = round((time.monotonic() - t0) * 1000, 1)
                status.exchange_ok = ok
                if not ok:
                    errors.append("Exchange API did not respond")
            except Exception as e:
                status.exchange_ok = False
                errors.append(f"Exchange API error: {e}")

        if self.db_path:
            try:
                if os.path.exists(self.db_path):
                    size = os.path.getsize(self.db_path)
                    status.database_ok = size > 0
                    status.database_size_mb = round(size / (1024 * 1024), 1)
                else:
                    status.database_ok = False
                    errors.append("Database not found")
            except Exception as e:
                status.database_ok = False
                errors.append(f"Database error: {e}")

        try:
            import psutil
            status.cpu_pct = psutil.cpu_percent(interval=0.5)
            status.memory_pct = psutil.virtual_memory().percent
            if status.cpu_pct > 90:
                errors.append(f"CPU at {status.cpu_pct}%")
            if status.memory_pct > 90:
                errors.append(f"RAM at {status.memory_pct}%")
        except ImportError:
            pass
        except Exception as e:
            log.warning("System check error: %s", e)

        status.errors = errors
        status.healthy = (
            (not self.ping_fn or status.exchange_ok) and
            (not self.db_path or status.database_ok) and
            len(errors) == 0
        )
        self._last_status = status
        return status

    async def start(self, interval: int = 60):
        self._running = True
        log.info("HealthMonitor started (interval=%ds)", interval)
        while self._running:
            try:
                status = await self.check()
                if not status.healthy:
                    log.warning("HEALTH CHECK FAILED: %s", "; ".join(status.errors))
                    for cb in self._callbacks:
                        try:
                            await cb(status)
                        except Exception as e:
                            log.error("Health callback error: %s", e)
                else:
                    log.debug("Health OK (lat=%.1fms cpu=%.0f%% mem=%.0f%%)",
                              status.exchange_latency_ms, status.cpu_pct, status.memory_pct)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Health monitor error: %s", e)
                await asyncio.sleep(interval)

    async def stop(self):
        self._running = False

    @property
    def last_status(self) -> Optional[HealthStatus]:
        return self._last_status

    @property
    def healthy(self) -> bool:
        return self._last_status is None or self._last_status.healthy
