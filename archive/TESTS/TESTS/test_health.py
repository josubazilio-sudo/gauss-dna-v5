import unittest
import sys
import time
import asyncio

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.health import HealthMonitor, HealthStatus


class TestHealthMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = HealthMonitor()

    def test_initial_state(self):
        self.assertIsNone(self.monitor.last_status)

    def test_initial_healthy(self):
        self.assertTrue(self.monitor.healthy)

    def test_check_returns_status(self):
        status = asyncio.run(self.monitor.check())
        self.assertIsInstance(status, HealthStatus)
        self.assertIsInstance(status.uptime_hours, float)
        self.assertIsInstance(status.errors, list)
        self.assertIsInstance(status.last_check, str)

    def test_check_without_ping_fn_succeeds(self):
        status = asyncio.run(self.monitor.check())
        self.assertTrue(status.healthy)

    def test_unhealthy_callback(self):
        results = []
        async def test_cb(status):
            results.append(status)
        self.monitor.on_unhealthy(test_cb)
        self.assertIn(test_cb, self.monitor._callbacks)

    def test_uptime_returns_float(self):
        before = self.monitor._start_time
        time.sleep(0.01)
        status = asyncio.run(self.monitor.check())
        self.assertIsInstance(status.uptime_hours, float)
        self.assertGreaterEqual(status.uptime_hours, 0.0)

    def test_db_check_handles_missing(self):
        mon = HealthMonitor(db_path="C:\\nonexistent\\path\\db.sqlite")
        status = asyncio.run(mon.check())
        self.assertIsInstance(status, HealthStatus)

    def test_start_stop(self):
        async def run():
            await self.monitor.start(interval=1)
        async def stop():
            await asyncio.sleep(0.1)
            await self.monitor.stop()

        async def test():
            task = asyncio.create_task(run())
            await asyncio.sleep(0.1)
            await stop()
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass
            self.assertFalse(self.monitor._running)

        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
