import unittest
import sys

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.task import TaskRegistry, TaskQueue, TaskValidator, TaskManager, TaskDefinition


class TestTaskRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = TaskRegistry()

    def test_register_and_get(self):
        self.registry.register("task1", "First Task", "analysis")
        task = self.registry.get("task1")
        self.assertIsNotNone(task)
        self.assertEqual(task.name, "First Task")
        self.assertEqual(task.category, "analysis")
        self.assertEqual(task.status, "pending")

    def test_update_status(self):
        self.registry.register("t1", "Test", "cat")
        self.registry.update_status("t1", "running")
        self.assertEqual(self.registry.get("t1").status, "running")

    def test_update_status_unknown_does_not_error(self):
        try:
            self.registry.update_status("unknown", "failed")
        except Exception:
            self.fail("update_status on unknown task raised")

    def test_list_all(self):
        self.registry.register("a", "A", "cat")
        self.registry.register("b", "B", "cat")
        tasks = self.registry.list_all()
        self.assertIn("a", tasks)
        self.assertIn("b", tasks)
        self.assertEqual(len(tasks), 2)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.registry.get("unknown"))


class TestTaskQueue(unittest.TestCase):
    def setUp(self):
        self.queue = TaskQueue()

    def test_enqueue_and_dequeue(self):
        self.queue.enqueue("task1")
        self.queue.enqueue("task2")
        self.assertEqual(self.queue.dequeue(), "task1")
        self.assertEqual(self.queue.dequeue(), "task2")

    def test_dequeue_empty_returns_none(self):
        self.assertIsNone(self.queue.dequeue())

    def test_size(self):
        self.assertEqual(self.queue.size(), 0)
        self.queue.enqueue("a")
        self.assertEqual(self.queue.size(), 1)

    def test_clear(self):
        self.queue.enqueue("a")
        self.queue.enqueue("b")
        self.queue.clear()
        self.assertEqual(self.queue.size(), 0)


class TestTaskValidator(unittest.TestCase):
    def setUp(self):
        self.validator = TaskValidator()

    def test_validate_valid_payload(self):
        errors = self.validator.validate({"action": "run"})
        self.assertEqual(errors, [])

    def test_validate_missing_field(self):
        errors = self.validator.validate({})
        self.assertTrue(any("action" in e for e in errors))

    def test_validate_non_dict(self):
        errors = self.validator.validate("not a dict")
        self.assertTrue(any("dict" in e for e in errors))


class TestTaskManager(unittest.TestCase):
    def setUp(self):
        self.manager = TaskManager()

    def test_submit_task(self):
        self.manager.submit("t1", "Test Task", "general", {"action": "run"})
        task = self.manager._registry.get("t1")
        self.assertIsNotNone(task)
        self.assertEqual(task.payload, {"action": "run"})

    def test_submit_rejects_invalid_payload(self):
        self.manager.submit("t2", "Bad", "general", {})
        self.assertIsNone(self.manager._registry.get("t2"))

    def test_process_next_processes_task(self):
        self.manager.submit("t3", "Process Me", "general", {"action": "run"})
        self.manager.process_next()
        task = self.manager._registry.get("t3")
        self.assertEqual(task.status, "completed")

    def test_process_next_with_empty_queue(self):
        try:
            self.manager.process_next()
        except Exception:
            self.fail("process_next on empty queue raised")

    def test_get_report_returns_string(self):
        report = self.manager.get_report()
        self.assertIn("Task Report", report)


class TestTaskDefinition(unittest.TestCase):
    def test_default_status_is_pending(self):
        td = TaskDefinition("id", "name", "cat")
        self.assertEqual(td.status, "pending")

    def test_repr(self):
        td = TaskDefinition("id1", "Test", "cat")
        self.assertIn("id1", repr(td))


if __name__ == "__main__":
    unittest.main()
