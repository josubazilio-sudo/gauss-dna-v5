import unittest
import sys

sys.path.insert(0, 'C:\\Users\\josue\\QuantOS')

from CORE.errors import (
    QuantOSError, ConfigurationError, EngineError, ScannerError,
    ValidationError, BaselineError, InterfaceError,
    validate_error_code, validate_module_name, validate_context,
    Recovery, setup_global_handlers,
)
from CORE.events.event_bus import EventBus


class TestQuantOSError(unittest.TestCase):
    def test_without_code(self):
        err = QuantOSError("something broke")
        self.assertIsNone(err.code)
        self.assertEqual(str(err), "something broke")

    def test_with_code(self):
        err = QuantOSError("config missing", code="CFG001")
        self.assertEqual(err.code, "CFG001")
        self.assertEqual(str(err), "[CFG001] config missing")

    def test_is_exception(self):
        self.assertTrue(issubclass(QuantOSError, Exception))


class TestExceptionSubclasses(unittest.TestCase):
    def test_configuration_error(self):
        err = ConfigurationError("bad config")
        self.assertIsInstance(err, QuantOSError)
        self.assertEqual(str(err), "bad config")

    def test_engine_error(self):
        err = EngineError("engine failed")
        self.assertIsInstance(err, QuantOSError)

    def test_scanner_error(self):
        err = ScannerError("scan failed")
        self.assertIsInstance(err, EngineError)

    def test_validation_error(self):
        err = ValidationError("invalid")
        self.assertIsInstance(err, QuantOSError)

    def test_baseline_error(self):
        err = BaselineError("baseline missing")
        self.assertIsInstance(err, QuantOSError)

    def test_interface_error(self):
        err = InterfaceError("contract broken")
        self.assertIsInstance(err, QuantOSError)


class TestValidators(unittest.TestCase):
    def test_validate_error_code_valid(self):
        self.assertTrue(validate_error_code("CFG001"))
        self.assertTrue(validate_error_code("ENG999"))
        self.assertTrue(validate_error_code("VAL123"))

    def test_validate_error_code_invalid(self):
        self.assertFalse(validate_error_code(""))
        self.assertFalse(validate_error_code("CFG"))
        self.assertFalse(validate_error_code("CFG12"))
        self.assertFalse(validate_error_code("cfg001"))
        self.assertFalse(validate_error_code(123))

    def test_validate_module_name_valid(self):
        self.assertTrue(validate_module_name("engine"))
        self.assertTrue(validate_module_name("CORE.config"))

    def test_validate_module_name_invalid(self):
        self.assertFalse(validate_module_name(""))
        self.assertFalse(validate_module_name("   "))
        self.assertFalse(validate_module_name(123))
        self.assertFalse(validate_module_name(None))

    def test_validate_context_valid(self):
        self.assertTrue(validate_context({"key": "value"}))
        self.assertTrue(validate_context({}))

    def test_validate_context_invalid(self):
        self.assertFalse(validate_context("string"))
        self.assertFalse(validate_context(None))
        self.assertFalse(validate_context(42))
        self.assertFalse(validate_context([]))


class TestRecovery(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.recovery = Recovery(self.bus)

    def test_attempt_restore_publishes_event(self):
        events = []
        self.bus.subscribe("recovery.attempted", lambda e: events.append(e))
        result = self.recovery.attempt_restore("test_mod", ValueError("fail"))
        self.assertTrue(result)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].data["module"], "test_mod")

    def test_rollback_publishes_event(self):
        events = []
        self.bus.subscribe("recovery.rollback", lambda e: events.append(e))
        self.recovery.rollback("test_mod")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].data["module"], "test_mod")


class TestGlobalHandlers(unittest.TestCase):
    def test_setup_global_handlers_sets_excepthook(self):
        import sys
        old_hook = sys.excepthook
        try:
            setup_global_handlers()
            self.assertIsNotNone(sys.excepthook)
        finally:
            sys.excepthook = old_hook


if __name__ == "__main__":
    unittest.main()
