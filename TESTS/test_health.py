import unittest
import sys
import time

sys.path.insert(0, 'C:\\Users\\josue\\QuantOS')

from CORE.health import HealthMonitor, Heartbeat, StatusRegistry, Diagnostics
from CORE.health.health_monitor import HealthLevel
from CORE.events.event_bus import EventBus


class TestHealthMonitor(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.monitor = HealthMonitor(self.bus)

    def test_health_levels_exist(self):
        self.assertEqual(HealthLevel.HEALTHY.value, "healthy")
        self.assertEqual(HealthLevel.WARNING.value, "warning")
        self.assertEqual(HealthLevel.DEGRADED.value, "degraded")
        self.assertEqual(HealthLevel.CRITICAL.value, "critical")
        self.assertEqual(HealthLevel.OFFLINE.value, "offline")

    def test_update_status_changes_level(self):
        self.monitor.update_status("engine", HealthLevel.HEALTHY)
        self.assertEqual(self.monitor.get_status("engine"), HealthLevel.HEALTHY)

    def test_get_status_defaults_to_offline(self):
        self.assertEqual(self.monitor.get_status("unknown"), HealthLevel.OFFLINE)

    def test_all_healthy_returns_true_when_all_healthy(self):
        self.monitor.update_status("mod1", HealthLevel.HEALTHY)
        self.monitor.update_status("mod2", HealthLevel.HEALTHY)
        self.assertTrue(self.monitor.all_healthy())

    def test_all_healthy_returns_false_when_not_all_healthy(self):
        self.monitor.update_status("mod1", HealthLevel.HEALTHY)
        self.monitor.update_status("mod2", HealthLevel.WARNING)
        self.assertFalse(self.monitor.all_healthy())

    def test_update_publishes_event(self):
        received = []
        self.bus.subscribe("health.changed", lambda e: received.append(e))
        self.monitor.update_status("test", HealthLevel.HEALTHY)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["module"], "test")


class TestHeartbeat(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.monitor = HealthMonitor(self.bus)
        self.heartbeat = Heartbeat(self.monitor, self.bus)

    def test_register_adds_module(self):
        self.heartbeat.register("engine")
        result = self.heartbeat.check("engine", timeout=30)
        self.assertTrue(result)

    def test_check_returns_false_after_timeout(self):
        self.heartbeat.register("mod")
        result = self.heartbeat.check("mod", timeout=-1)
        self.assertFalse(result)

    def test_check_updates_monitor_on_timeout(self):
        self.heartbeat.register("mod")
        self.heartbeat.check("mod", timeout=-1)
        self.assertEqual(self.monitor.get_status("mod"), HealthLevel.WARNING)


class TestStatusRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = StatusRegistry()

    def test_register_adds_module(self):
        self.registry.register("engine", {"version": "1.0"})
        data = self.registry.get("engine")
        self.assertEqual(data["metadata"]["version"], "1.0")
        self.assertEqual(data["status"], "healthy")

    def test_update_changes_status(self):
        self.registry.register("engine", {})
        self.registry.update("engine", "warning")
        self.assertEqual(self.registry.get("engine")["status"], "warning")

    def test_get_returns_empty_for_unknown(self):
        self.assertEqual(self.registry.get("unknown"), {})

    def test_get_all_returns_all(self):
        self.registry.register("a", {})
        self.registry.register("b", {})
        all_data = self.registry.get_all()
        self.assertIn("a", all_data)
        self.assertIn("b", all_data)
        self.assertEqual(len(all_data), 2)


class TestDiagnostics(unittest.TestCase):
    def test_run_all_checks_modules(self):
        diag = Diagnostics(["os", "sys"])
        results = diag.run_all()
        self.assertIsInstance(results, list)
        for r in results:
            self.assertIn("module", r)
            self.assertIn("status", r)

    def test_check_known_module_returns_ok(self):
        diag = Diagnostics(["json"])
        results = diag.run_all()
        for r in results:
            if r["module"] == "json":
                self.assertEqual(r["status"], "ok")

    def test_check_unknown_module_returns_error(self):
        diag = Diagnostics(["_nonexistent_module_quantos_"])
        results = diag.run_all()
        for r in results:
            if r["module"] == "_nonexistent_module_quantos_":
                self.assertEqual(r["status"], "error")


if __name__ == "__main__":
    unittest.main()
