import unittest
import sys

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.interfaces import (
    BaseModule, BaseService, BaseEngine,
    BaseRepository, BaseProvider, BaseValidator, BaseStrategy,
)


class TestBaseModule(unittest.TestCase):
    def test_cannot_instantiate_abstract(self):
        with self.assertRaises(TypeError):
            BaseModule()

    def test_concrete_implementation_works(self):
        class MyModule(BaseModule):
            def initialize(self):
                pass
        module = MyModule(name="test", version="1.0")
        self.assertEqual(module.name, "test")
        self.assertEqual(module.version, "1.0")

    def test_start_sets_status(self):
        class MyModule(BaseModule):
            def initialize(self):
                pass
        module = MyModule()
        self.assertEqual(module.status, "created")
        module.start()
        self.assertEqual(module.status, "running")

    def test_stop_sets_status(self):
        class MyModule(BaseModule):
            def initialize(self):
                pass
        module = MyModule()
        module.start()
        module.stop()
        self.assertEqual(module.status, "stopped")

    def test_get_status_returns_dict(self):
        class MyModule(BaseModule):
            def initialize(self):
                pass
        module = MyModule(name="my_mod", version="2.0")
        status = module.get_status()
        self.assertEqual(status["name"], "my_mod")
        self.assertEqual(status["version"], "2.0")
        self.assertEqual(status["status"], "created")

    def test_initialize_raises_not_implemented_error(self):
        class Incomplete(BaseModule):
            pass
        with self.assertRaises(TypeError):
            Incomplete()


class TestBaseService(unittest.TestCase):
    def test_cannot_instantiate_abstract(self):
        with self.assertRaises(TypeError):
            BaseService()

    def test_concrete_implementation_works(self):
        class MyService(BaseService):
            def initialize(self):
                pass
            def shutdown(self):
                pass
            def status(self):
                return {"status": "ok"}
        svc = MyService()
        self.assertEqual(svc.status(), {"status": "ok"})

    def test_abstract_methods_raise(self):
        class Incomplete(BaseService):
            pass
        with self.assertRaises(TypeError):
            Incomplete()


class TestBaseEngine(unittest.TestCase):
    def test_concrete_implementation(self):
        class MyEngine(BaseEngine):
            def initialize(self):
                pass
            def shutdown(self):
                pass
            def status(self):
                return {}
            def execute(self, **kwargs):
                return {"result": "done"}
            def validate(self, **kwargs):
                return True
        engine = MyEngine()
        self.assertEqual(engine.execute(), {"result": "done"})
        self.assertTrue(engine.validate())


class TestBaseRepository(unittest.TestCase):
    def test_concrete_implementation(self):
        class MyRepo(BaseRepository):
            def __init__(self):
                self._data = {}
            def save(self, key, value):
                self._data[key] = value
            def load(self, key):
                return self._data.get(key)
            def delete(self, key):
                self._data.pop(key, None)
            def exists(self, key):
                return key in self._data
        repo = MyRepo()
        repo.save("k1", "v1")
        self.assertEqual(repo.load("k1"), "v1")
        self.assertTrue(repo.exists("k1"))
        repo.delete("k1")
        self.assertFalse(repo.exists("k1"))


class TestBaseValidator(unittest.TestCase):
    def test_concrete_implementation(self):
        class MyValidator(BaseValidator):
            def __init__(self):
                self._errors = []
            def validate(self, data):
                return len(data) > 0
            def get_errors(self):
                return self._errors
            def clear(self):
                self._errors.clear()
        v = MyValidator()
        self.assertTrue(v.validate([1]))
        self.assertFalse(v.validate([]))
        self.assertEqual(v.get_errors(), [])


class TestBaseStrategy(unittest.TestCase):
    def test_concrete_implementation(self):
        class MyStrategy(BaseStrategy):
            def initialize(self):
                pass
            def analyze(self, data):
                return {"signal": "buy"}
            def score(self, data):
                return 85.0
        s = MyStrategy()
        self.assertEqual(s.analyze({}), {"signal": "buy"})
        self.assertEqual(s.score({}), 85.0)


class TestBaseProvider(unittest.TestCase):
    def test_concrete_implementation(self):
        class MyProvider(BaseProvider):
            def initialize(self):
                pass
            def connect(self):
                return True
            def disconnect(self):
                pass
            def fetch(self, resource, **kwargs):
                return {"data": resource}
        p = MyProvider()
        self.assertTrue(p.connect())
        self.assertEqual(p.fetch("price"), {"data": "price"})


if __name__ == "__main__":
    unittest.main()
