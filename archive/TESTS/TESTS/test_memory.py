"""
Testes do sistema de memória permanente (FASE 02).
"""

import unittest
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from CORE.memory.file_store import FileStore
from CORE.memory.lesson_registry import Lesson, LessonRegistry
from CORE.memory.improvement_log import ImprovementEntry, ImprovementLog
from CORE.memory.parameter_history import ParameterRecord, ParameterHistory
from CORE.memory.backtest_records import BacktestRecord, BacktestRecords
from CORE.memory.change_log import ChangeEntry, ChangeLog
from CORE.memory.memory_query import MemoryQuery
from CORE.memory.memory_engine import MemoryEngine


class TestLesson(unittest.TestCase):
    def test_create_lesson(self):
        lesson = Lesson.create("titulo", "descricao", category="trading", severity="critical")
        self.assertTrue(len(lesson.lesson_id) > 0)
        self.assertEqual(lesson.title, "titulo")
        self.assertEqual(lesson.description, "descricao")
        self.assertEqual(lesson.category, "trading")
        self.assertEqual(lesson.severity, "critical")
        self.assertEqual(lesson.source, "manual")
        self.assertIn("T", lesson.created_at)

    def test_lesson_to_dict(self):
        lesson = Lesson.create("test", "desc")
        d = lesson.to_dict()
        self.assertEqual(d["title"], "test")
        self.assertEqual(d["description"], "desc")

    def test_lesson_defaults(self):
        lesson = Lesson.create("titulo", "desc")
        self.assertEqual(lesson.category, "general")
        self.assertEqual(lesson.severity, "info")
        self.assertEqual(lesson.source, "manual")


class TestLessonRegistry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = FileStore(Path(self._tmp))
        self._registry = LessonRegistry(self._store)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_add_and_get(self):
        lesson = Lesson.create("test", "descricao")
        self._registry.add(lesson)
        loaded = self._registry.get(lesson.lesson_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, "test")

    def test_get_nonexistent(self):
        self.assertIsNone(self._registry.get("nonexistent"))

    def test_list_all(self):
        self._registry.add(Lesson.create("a", "desc a"))
        self._registry.add(Lesson.create("b", "desc b"))
        self.assertEqual(self._registry.count(), 2)
        self.assertEqual(len(self._registry.list_all()), 2)

    def test_list_empty(self):
        self.assertEqual(self._registry.count(), 0)
        self.assertEqual(len(self._registry.list_all()), 0)


class TestImprovementEntry(unittest.TestCase):
    def test_create_entry(self):
        entry = ImprovementEntry.create(
            "melhoria", "desc", category="feature",
            status="approved", module="CORE", version="2.0.0",
        )
        self.assertTrue(len(entry.improvement_id) > 0)
        self.assertEqual(entry.title, "melhoria")
        self.assertEqual(entry.status, "approved")
        self.assertEqual(entry.module, "CORE")

    def test_default_status(self):
        entry = ImprovementEntry.create("test", "desc")
        self.assertEqual(entry.status, "pending")

    def test_to_dict(self):
        entry = ImprovementEntry.create("test", "desc")
        d = entry.to_dict()
        self.assertEqual(d["title"], "test")


class TestImprovementLog(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = FileStore(Path(self._tmp))
        self._log = ImprovementLog(self._store)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_add_and_get(self):
        entry = ImprovementEntry.create("test", "desc")
        self._log.add(entry)
        loaded = self._log.get(entry.improvement_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, "test")

    def test_list_by_status(self):
        self._log.add(ImprovementEntry.create("a", "desc a", status="approved"))
        self._log.add(ImprovementEntry.create("b", "desc b", status="rejected"))
        self._log.add(ImprovementEntry.create("c", "desc c", status="approved"))
        approved = self._log.list_by_status("approved")
        rejected = self._log.list_by_status("rejected")
        self.assertEqual(len(approved), 2)
        self.assertEqual(len(rejected), 1)

    def test_list_by_module(self):
        self._log.add(ImprovementEntry.create("a", "desc", module="CORE"))
        self._log.add(ImprovementEntry.create("b", "desc", module="MEMORY"))
        self.assertEqual(len(self._log.list_by_module("CORE")), 1)
        self.assertEqual(len(self._log.list_by_module("MEMORY")), 1)

    def test_count(self):
        self.assertEqual(self._log.count(), 0)
        self._log.add(ImprovementEntry.create("a", "desc"))
        self.assertEqual(self._log.count(), 1)


class TestParameterRecord(unittest.TestCase):
    def test_create_winning(self):
        record = ParameterRecord.create(
            "ema_cross",
            {"fast": 9, "slow": 21},
            result="winning",
            metric="profit_factor",
            metric_value=3.2,
        )
        self.assertTrue(len(record.param_id) > 0)
        self.assertEqual(record.result, "winning")
        self.assertEqual(record.parameters["fast"], 9)

    def test_create_with_backtest(self):
        record = ParameterRecord.create(
            "rsi_div", {"period": 14},
            backtest_id="bt_001",
        )
        self.assertEqual(record.backtest_id, "bt_001")

    def test_to_dict(self):
        record = ParameterRecord.create("strat", {"p1": 10})
        d = record.to_dict()
        self.assertEqual(d["strategy"], "strat")


class TestParameterHistory(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = FileStore(Path(self._tmp))
        self._history = ParameterHistory(self._store)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_add_and_get(self):
        record = ParameterRecord.create("strat", {"p": 1})
        self._history.add(record)
        loaded = self._history.get(record.param_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.strategy, "strat")

    def test_list_by_result(self):
        self._history.add(ParameterRecord.create("a", {}, result="winning"))
        self._history.add(ParameterRecord.create("b", {}, result="losing"))
        self.assertEqual(len(self._history.list_by_result("winning")), 1)
        self.assertEqual(len(self._history.list_by_result("losing")), 1)

    def test_list_by_strategy(self):
        self._history.add(ParameterRecord.create("strat_a", {}))
        self._history.add(ParameterRecord.create("strat_a", {}))
        self._history.add(ParameterRecord.create("strat_b", {}))
        self.assertEqual(len(self._history.list_by_strategy("strat_a")), 2)
        self.assertEqual(len(self._history.list_by_strategy("strat_b")), 1)


class TestBacktestRecord(unittest.TestCase):
    def test_create_passed(self):
        record = BacktestRecord.create(
            strategy="ema_cross",
            version="2.0.0",
            win_rate=65.0,
            profit_factor=3.0,
            max_drawdown=5.0,
        )
        self.assertTrue(record.passed)

    def test_create_failed_low_win_rate(self):
        record = BacktestRecord.create(
            strategy="test",
            version="1.0.0",
            win_rate=45.0,
            profit_factor=3.0,
            max_drawdown=5.0,
        )
        self.assertFalse(record.passed)

    def test_create_failed_low_pf(self):
        record = BacktestRecord.create(
            strategy="test",
            version="1.0.0",
            win_rate=65.0,
            profit_factor=1.5,
            max_drawdown=5.0,
        )
        self.assertFalse(record.passed)

    def test_create_failed_high_drawdown(self):
        record = BacktestRecord.create(
            strategy="test",
            version="1.0.0",
            win_rate=65.0,
            profit_factor=3.0,
            max_drawdown=15.0,
        )
        self.assertFalse(record.passed)

    def test_defaults(self):
        record = BacktestRecord.create(strategy="test", version="1.0.0")
        self.assertEqual(record.total_trades, 0)
        self.assertEqual(record.win_rate, 0.0)


class TestBacktestRecords(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = FileStore(Path(self._tmp))
        self._records = BacktestRecords(self._store)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_add_and_get(self):
        record = BacktestRecord.create(strategy="test", version="1.0.0")
        self._records.add(record)
        loaded = self._records.get(record.backtest_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.strategy, "test")

    def test_list_passed(self):
        self._records.add(BacktestRecord.create("a", "1.0", win_rate=70, profit_factor=3.0, max_drawdown=5))
        self._records.add(BacktestRecord.create("b", "1.0", win_rate=40, profit_factor=1.0, max_drawdown=20))
        self.assertEqual(len(self._records.list_passed()), 1)

    def test_best_by_metric(self):
        self._records.add(BacktestRecord.create("a", "1.0", profit_factor=2.0))
        self._records.add(BacktestRecord.create("b", "1.0", profit_factor=5.0))
        best = self._records.best_by_metric("profit_factor")
        self.assertIsNotNone(best)
        self.assertEqual(best.profit_factor, 5.0)

    def test_best_empty(self):
        self.assertIsNone(self._records.best_by_metric())

    def test_list_by_strategy(self):
        self._records.add(BacktestRecord.create("s1", "1.0"))
        self._records.add(BacktestRecord.create("s1", "1.0"))
        self._records.add(BacktestRecord.create("s2", "1.0"))
        self.assertEqual(len(self._records.list_by_strategy("s1")), 2)

    def test_count(self):
        self.assertEqual(self._records.count(), 0)
        self._records.add(BacktestRecord.create("t", "1.0"))
        self.assertEqual(self._records.count(), 1)


class TestChangeEntry(unittest.TestCase):
    def test_create(self):
        entry = ChangeEntry.create(
            "config", "CORE", "alterou timeout",
            previous_value="30", new_value="60",
            author="dev", version="2.0.0",
        )
        self.assertTrue(len(entry.change_id) > 0)
        self.assertEqual(entry.change_type, "config")
        self.assertEqual(entry.previous_value, "30")
        self.assertEqual(entry.new_value, "60")

    def test_defaults(self):
        entry = ChangeEntry.create("code", "CORE", "refatoracao")
        self.assertEqual(entry.author, "system")
        self.assertEqual(entry.previous_value, "")


class TestChangeLog(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = FileStore(Path(self._tmp))
        self._log = ChangeLog(self._store)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_log_and_get(self):
        entry = ChangeEntry.create("config", "CORE", "alteracao")
        self._log.log(entry)
        loaded = self._log.get(entry.change_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.description, "alteracao")

    def test_list_by_type(self):
        self._log.log(ChangeEntry.create("config", "CORE", "c1"))
        self._log.log(ChangeEntry.create("code", "CORE", "c2"))
        self._log.log(ChangeEntry.create("config", "CORE", "c3"))
        self.assertEqual(len(self._log.list_by_type("config")), 2)
        self.assertEqual(len(self._log.list_by_type("code")), 1)

    def test_list_by_module(self):
        self._log.log(ChangeEntry.create("code", "CORE", "c1"))
        self._log.log(ChangeEntry.create("code", "MEMORY", "c2"))
        self.assertEqual(len(self._log.list_by_module("CORE")), 1)

    def test_list_by_version(self):
        self._log.log(ChangeEntry.create("code", "CORE", "c1", version="1.0"))
        self._log.log(ChangeEntry.create("code", "CORE", "c2", version="2.0"))
        self.assertEqual(len(self._log.list_by_version("1.0")), 1)

    def test_count(self):
        self.assertEqual(self._log.count(), 0)
        self._log.log(ChangeEntry.create("code", "CORE", "c1"))
        self.assertEqual(self._log.count(), 1)


class TestFileStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = FileStore(Path(self._tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_save_and_load(self):
        self._store.save("test_col", "rec_001", {"key": "value", "num": 42})
        data = self._store.load("test_col", "rec_001")
        self.assertIsNotNone(data)
        self.assertEqual(data["key"], "value")
        self.assertEqual(data["num"], 42)

    def test_load_nonexistent(self):
        self.assertIsNone(self._store.load("test", "noexist"))

    def test_list_ids(self):
        self._store.save("col", "a", {"v": 1})
        self._store.save("col", "b", {"v": 2})
        ids = self._store.list_ids("col")
        self.assertEqual(len(ids), 2)
        self.assertIn("a", ids)
        self.assertIn("b", ids)

    def test_delete(self):
        self._store.save("col", "rec", {"v": 1})
        self.assertEqual(self._store.count("col"), 1)
        self._store.delete("col", "rec")
        self.assertEqual(self._store.count("col"), 0)

    def test_count_empty(self):
        self.assertEqual(self._store.count("empty"), 0)


class TestMemoryQuery(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._store = FileStore(Path(self._tmp))
        self._query = MemoryQuery(self._store)
        self._store.save("users", "1", {"name": "Alice", "role": "admin"})
        self._store.save("users", "2", {"name": "Bob", "role": "viewer"})
        self._store.save("users", "3", {"name": "Charlie", "role": "admin"})

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_find_exact(self):
        results = self._query.find("users", role="admin")
        self.assertEqual(len(results), 2)

    def test_find_no_match(self):
        results = self._query.find("users", role="god")
        self.assertEqual(len(results), 0)

    def test_search_text(self):
        results = self._query.search("users", "ali", fields=["name"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Alice")

    def test_search_case_insensitive(self):
        results = self._query.search("users", "ALICE", fields=["name"])
        self.assertEqual(len(results), 1)

    def test_aggregate(self):
        counts = self._query.aggregate("users", lambda d: d["role"])
        self.assertEqual(counts, {"admin": 2, "viewer": 1})


class TestMemoryEngine(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._engine = MemoryEngine(memory_dir=Path(self._tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_initialized(self):
        self.assertIsNotNone(self._engine.lessons)
        self.assertIsNotNone(self._engine.improvements)
        self.assertIsNotNone(self._engine.parameters)
        self.assertIsNotNone(self._engine.backtests)
        self.assertIsNotNone(self._engine.changes)
        self.assertIsNotNone(self._engine.query)
        self.assertIsNotNone(self._engine.report)

    def test_record_change(self):
        cid = self._engine.record_change("config", "CORE", "alterou timeout")
        self.assertTrue(len(cid) > 0)
        loaded = self._engine.changes.get(cid)
        self.assertIsNotNone(loaded)

    def test_record_lesson(self):
        lid = self._engine.record_lesson("lesson title", "lesson desc")
        self.assertTrue(len(lid) > 0)
        loaded = self._engine.lessons.get(lid)
        self.assertIsNotNone(loaded)

    def test_record_improvement(self):
        iid = self._engine.record_improvement("improvement", "desc")
        self.assertTrue(len(iid) > 0)

    def test_record_backtest(self):
        bid = self._engine.record_backtest(strategy="test", version="1.0")
        self.assertTrue(len(bid) > 0)

    def test_record_parameters(self):
        pid = self._engine.record_parameters("strategy", {"p": 1})
        self.assertTrue(len(pid) > 0)

    def test_report_summary(self):
        summary = self._engine.report.summary()
        self.assertIn("licoes", summary)
        self.assertIn("melhorias", summary)
        self.assertIn("parametros", summary)
        self.assertIn("backtests", summary)
        self.assertIn("mudancas", summary)

    def test_generate_report(self):
        report = self._engine.report.generate()
        self.assertIn("Relatorio da Memoria", report)


if __name__ == "__main__":
    unittest.main()
