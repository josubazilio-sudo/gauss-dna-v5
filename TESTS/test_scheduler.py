import unittest
import sys

sys.path.insert(0, 'C:\\Users\\josue\\QuantOS')

from CORE.scheduler import Scheduler, Job, JobRegistry, JobExecutor


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.scheduler = Scheduler()

    def test_register_job(self):
        def my_job():
            pass
        self.scheduler.register_job("test_job", 60, my_job)
        report = self.scheduler.get_report()
        self.assertIn("test_job", report)

    def test_run_all_executes_jobs(self):
        results = []
        def track():
            results.append("ran")
        self.scheduler.register_job("tracker", 1, track)
        self.scheduler.run_all()
        self.assertEqual(len(results), 1)

    def test_register_multiple_jobs(self):
        self.scheduler.register_job("a", 10, lambda: None)
        self.scheduler.register_job("b", 20, lambda: None)
        report = self.scheduler.get_report()
        self.assertIn("a", report)
        self.assertIn("b", report)

    def test_start_stop_loop(self):
        self.scheduler.start_loop(interval_seconds=1)
        self.assertTrue(self.scheduler._running)
        self.scheduler.stop_loop()
        self.assertFalse(self.scheduler._running)


class TestJobExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = JobExecutor()

    def test_execute_job(self):
        results = []
        job = Job("test_job", 10, lambda: results.append("done"))
        self.executor.execute(job)
        self.assertEqual(len(results), 1)

    def test_execute_job_handles_exception(self):
        def failing():
            raise ValueError("fail")
        job = Job("failing", 10, failing)
        try:
            self.executor.execute(job)
        except Exception:
            self.fail("execute() should not propagate exceptions")

    def test_is_due_returns_true_when_not_run(self):
        job = Job("new", 1, lambda: None)
        self.assertTrue(self.executor.is_due(job))

    def test_is_due_returns_false_when_recently_run(self):
        job = Job("recent", 3600, lambda: None)
        self.executor.execute(job)
        self.assertFalse(self.executor.is_due(job))

    def test_last_run_returns_never(self):
        self.assertEqual(self.executor.last_run("unknown"), "never")

    def test_last_run_returns_string_after_execution(self):
        job = Job("lrun", 3600, lambda: None)
        self.executor.execute(job)
        result = self.executor.last_run("lrun")
        self.assertNotEqual(result, "never")
        self.assertIsInstance(result, str)


class TestJobRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = JobRegistry()

    def test_add_and_get(self):
        self.registry.add("job1", 60, lambda: None)
        job = self.registry.get("job1")
        self.assertIsNotNone(job)
        self.assertEqual(job.name, "job1")
        self.assertEqual(job.interval, 60)

    def test_list_all(self):
        self.registry.add("a", 10, lambda: None)
        self.registry.add("b", 20, lambda: None)
        jobs = self.registry.list_all()
        self.assertEqual(len(jobs), 2)

    def test_add_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self.registry.add("", 10, lambda: None)

    def test_remove(self):
        self.registry.add("r", 10, lambda: None)
        self.registry.remove("r")
        self.assertIsNone(self.registry.get("r"))

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.registry.get("unknown"))


if __name__ == "__main__":
    unittest.main()
