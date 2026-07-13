import unittest
import sys

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.bootstrap import Startup, Shutdown


class TestStartup(unittest.TestCase):
    def setUp(self):
        self.startup = Startup()

    def test_create_creates_startup(self):
        self.assertIsNotNone(self.startup)
        self.assertIsNotNone(self.startup._settings)
        self.assertIsNotNone(self.startup._event_bus)

    def test_run_executes_without_error(self):
        try:
            self.startup.run()
        except Exception as e:
            self.fail(f"Startup.run() raised: {e}")

    def test_settings_has_constants(self):
        self.assertEqual(self.startup._settings.constants.PROJECT_NAME, "QuantOS")


class TestShutdown(unittest.TestCase):
    def setUp(self):
        self.shutdown = Shutdown()

    def test_create_creates_shutdown(self):
        self.assertIsNotNone(self.shutdown)

    def test_run_executes_without_error(self):
        try:
            self.shutdown.run()
        except Exception as e:
            self.fail(f"Shutdown.run() raised: {e}")

    def test_run_with_handlers(self):
        results = []
        self.shutdown.register(lambda: results.append(1))
        self.shutdown.register(lambda: results.append(2))
        self.shutdown.run()
        self.assertEqual(len(results), 2)

    def test_run_executes_in_reverse_order(self):
        results = []
        self.shutdown.register(lambda: results.append("first"))
        self.shutdown.register(lambda: results.append("second"))
        self.shutdown.run()
        self.assertEqual(results, ["second", "first"])

    def test_run_handles_handler_exception(self):
        def failing():
            raise RuntimeError("handler failed")
        def ok():
            pass
        self.shutdown.register(failing)
        self.shutdown.register(ok)
        try:
            self.shutdown.run()
        except Exception:
            self.fail("Shutdown should not propagate handler exceptions")


class TestStartupWithShutdown(unittest.TestCase):
    def test_full_flow(self):
        startup = Startup()
        shutdown = Shutdown()
        startup.run()
        shutdown.run()

    def test_shutdown_with_init_handlers(self):
        def h():
            pass
        shutdown = Shutdown(handlers=[h])
        self.assertEqual(len(shutdown._handlers), 1)


if __name__ == "__main__":
    unittest.main()
