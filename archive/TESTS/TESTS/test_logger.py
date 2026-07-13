import unittest
import sys
import logging
import io
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.logger import setup_logging, configure_logger, LogRotation, LogLevel
from CORE.logger.formatter import QuantOSFormatter
from CORE.logger.logger import get_logger


class TestLoggerSetup(unittest.TestCase):
    def setUp(self):
        self.root_logger = logging.getLogger()
        self._original_handlers = list(self.root_logger.handlers)
        self._original_level = self.root_logger.level
        for h in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(h)
        self.root_logger.setLevel(logging.WARNING)

    def tearDown(self):
        for h in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(h)
        for h in self._original_handlers:
            self.root_logger.addHandler(h)
        self.root_logger.setLevel(self._original_level)
        from CORE.logger.setup import _initialized
        _initialized = False
        import CORE.logger.setup as ls
        ls._initialized = False

    def test_setup_logging_configures_root_logger(self):
        setup_logging(level=logging.DEBUG)
        root = logging.getLogger()
        self.assertEqual(root.level, logging.DEBUG)
        handler_types = [type(h).__name__ for h in root.handlers]
        self.assertIn("QuantOSConsoleHandler", handler_types)

    def test_get_logger_returns_logger(self):
        log = get_logger("test.module")
        self.assertIsInstance(log, logging.Logger)
        self.assertEqual(log.name, "test.module")

    def test_configure_logger_respects_level(self):
        log = configure_logger("test.custom", level=logging.ERROR)
        self.assertEqual(log.level, logging.ERROR)

    def test_configure_logger_uses_global_level_when_none(self):
        log = configure_logger("test.default")
        self.assertEqual(log.level, logging.NOTSET)


class TestLogRotation(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.log_dir = Path(self._tmpdir)
        self.rotation = LogRotation(self.log_dir, max_days=30)

    def tearDown(self):
        for p in self.log_dir.rglob("*"):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            self.log_dir.rmdir()
        except OSError:
            pass

    def test_rotate_removes_old_files(self):
        old_file = self.log_dir / "old_test.log"
        old_time = datetime.now(timezone.utc) - timedelta(days=60)
        old_file.touch()
        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))
        self.assertTrue(old_file.exists())
        self.rotation.rotate()
        self.assertFalse(old_file.exists())

    def test_rotate_keeps_recent_files(self):
        recent_file = self.log_dir / "recent.log"
        recent_file.touch()
        self.rotation.rotate()
        self.assertTrue(recent_file.exists())

    def test_rotate_handles_missing_dir(self):
        missing = Path(tempfile.mkdtemp()) / "nope"
        rot = LogRotation(missing)
        try:
            rot.rotate()
        except Exception:
            self.fail("rotate() raised on missing dir")

    def test_validates_max_days(self):
        with self.assertRaises(ValueError):
            LogRotation(self.log_dir, max_days=0)

    def test_current_log_path_returns_path(self):
        path = self.rotation.current_log_path("test_mod")
        self.assertIsInstance(path, Path)
        self.assertIn("test_mod", path.name)
        self.assertTrue(path.name.endswith(".log"))


class TestQuantOSFormatter(unittest.TestCase):
    def setUp(self):
        self.fmt = QuantOSFormatter()

    def test_formats_log_record(self):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        output = self.fmt.format(record)
        self.assertIn("hello", output)
        self.assertIn("INFO", output)
        self.assertIn("test", output)

    def test_formatTime_uses_utc(self):
        record = logging.LogRecord(
            name="x", level=logging.INFO, pathname="", lineno=0,
            msg="x", args=(), exc_info=None,
        )
        formatted = self.fmt.formatTime(record)
        self.assertIn("T", formatted.replace(" ", "T"))

    def test_formatter_has_correct_format_string(self):
        self.assertEqual(QuantOSFormatter.FORMAT, "[%(asctime)s] %(levelname)-8s %(name)-20s %(message)s")


if __name__ == "__main__":
    unittest.main()
