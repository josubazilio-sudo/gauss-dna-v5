import unittest
import sys

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.state import StateStore, StateMachine, StateValidator, StateManager


class TestStateStore(unittest.TestCase):
    def setUp(self):
        self.store = StateStore()

    def test_set_and_get(self):
        self.store.set("key1", "value1")
        self.assertEqual(self.store.get("key1"), "value1")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("missing"))

    def test_delete_removes_key(self):
        self.store.set("k", "v")
        self.store.delete("k")
        self.assertIsNone(self.store.get("k"))

    def test_delete_unknown_does_not_error(self):
        try:
            self.store.delete("unknown")
        except Exception:
            self.fail("delete on unknown key raised")

    def test_get_all_returns_copy(self):
        self.store.set("a", 1)
        self.store.set("b", 2)
        all_data = self.store.get_all()
        self.assertEqual(len(all_data), 2)
        self.assertEqual(all_data["a"], 1)

    def test_clear_empties(self):
        self.store.set("x", 1)
        self.store.clear()
        self.assertEqual(len(self.store.get_all()), 0)


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.validator = StateValidator()
        self.machine = StateMachine(self.validator)

    def test_initial_state_is_init(self):
        self.assertEqual(self.machine.current(), "init")

    def test_valid_transition(self):
        result = self.machine.transition("booting")
        self.assertTrue(result)
        self.assertEqual(self.machine.current(), "booting")

    def test_invalid_transition_returns_false(self):
        result = self.machine.transition("stopped")
        self.assertFalse(result)
        self.assertEqual(self.machine.current(), "init")

    def test_full_flow(self):
        self.assertTrue(self.machine.transition("booting"))
        self.assertTrue(self.machine.transition("running"))
        self.assertTrue(self.machine.transition("paused"))
        self.assertTrue(self.machine.transition("running"))
        self.assertTrue(self.machine.transition("stopped"))
        self.assertTrue(self.machine.transition("init"))

    def test_can_transition_returns_bool(self):
        self.assertTrue(self.machine.can_transition("booting"))
        self.assertFalse(self.machine.can_transition("stopped"))

    def test_reset(self):
        self.machine.transition("booting")
        self.machine.reset()
        self.assertEqual(self.machine.current(), "init")


class TestStateValidator(unittest.TestCase):
    def setUp(self):
        self.validator = StateValidator()

    def test_can_transition_valid(self):
        self.assertTrue(self.validator.can_transition("init", "booting"))
        self.assertTrue(self.validator.can_transition("booting", "running"))
        self.assertTrue(self.validator.can_transition("running", "paused"))
        self.assertTrue(self.validator.can_transition("paused", "running"))
        self.assertTrue(self.validator.can_transition("running", "stopped"))

    def test_can_transition_invalid(self):
        self.assertFalse(self.validator.can_transition("init", "stopped"))
        self.assertFalse(self.validator.can_transition("stopped", "running"))
        self.assertFalse(self.validator.can_transition("paused", "init"))

    def test_add_transition_extends_allowed(self):
        v = StateValidator()
        self.assertFalse(v.can_transition("init", "stopped"))
        v.add_transition("init", "stopped")
        self.assertTrue(v.can_transition("init", "stopped"))
        StateValidator.VALID_TRANSITIONS["init"].remove("stopped")

    def test_unknown_current_state(self):
        self.assertFalse(self.validator.can_transition("unknown", "init"))


class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.manager = StateManager()

    def test_set_and_get(self):
        self.manager.set("mode", "live")
        self.assertEqual(self.manager.get("mode"), "live")

    def test_delete(self):
        self.manager.set("mode", "live")
        self.manager.delete("mode")
        self.assertIsNone(self.manager.get("mode"))

    def test_transition_valid(self):
        self.assertTrue(self.manager.transition("booting"))
        self.assertEqual(self.manager.current_state(), "booting")

    def test_transition_invalid(self):
        self.assertFalse(self.manager.transition("stopped"))
        self.assertEqual(self.manager.current_state(), "init")

    def test_get_report(self):
        self.manager.set("a", 1)
        report = self.manager.get_report()
        self.assertIn("State Report", report)


if __name__ == "__main__":
    unittest.main()
