import unittest
import sys

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.service_registry import (
    ServiceRegistry, ServiceLocator, ServiceFactory, ServiceValidator,
    ServiceMetadata,
)


class TestServiceRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = ServiceRegistry()

    def test_register_and_get(self):
        instance = {"service": "test"}
        self.registry.register("test_svc", instance)
        result = self.registry.get("test_svc")
        self.assertIs(result, instance)

    def test_exists(self):
        self.registry.register("svc", object())
        self.assertTrue(self.registry.exists("svc"))
        self.assertFalse(self.registry.exists("unknown"))

    def test_unregister(self):
        self.registry.register("svc", object())
        self.assertTrue(self.registry.exists("svc"))
        self.registry.unregister("svc")
        self.assertFalse(self.registry.exists("svc"))

    def test_get_returns_none_for_unknown(self):
        self.assertIsNone(self.registry.get("unknown"))

    def test_list_all_returns_names(self):
        self.registry.register("a", 1, {"desc": "first"})
        self.registry.register("b", 2, {"desc": "second"})
        all_svcs = self.registry.list_all()
        self.assertIn("a", all_svcs)
        self.assertIn("b", all_svcs)
        self.assertEqual(all_svcs["a"]["desc"], "first")


class TestServiceLocator(unittest.TestCase):
    def setUp(self):
        self.registry = ServiceRegistry()
        self.locator = ServiceLocator(self.registry)

    def test_locate_finds_service(self):
        obj = {"name": "my_service"}
        self.registry.register("my_service", obj)
        result = self.locator.locate("my_service")
        self.assertIs(result, obj)

    def test_locate_returns_none_for_missing(self):
        result = self.locator.locate("missing")
        self.assertIsNone(result)

    def test_available_checks_existence(self):
        self.registry.register("svc", object())
        self.assertTrue(self.locator.available("svc"))
        self.assertFalse(self.locator.available("no"))


class TestServiceFactory(unittest.TestCase):
    def setUp(self):
        self.factory = ServiceFactory()

    def test_create_service(self):
        self.factory.register_creator("my_svc", lambda **kw: {"created": True, **kw})
        result = self.factory.create("my_svc")
        self.assertEqual(result, {"created": True})

    def test_create_with_kwargs(self):
        self.factory.register_creator("cfg", lambda **kw: dict(kw))
        result = self.factory.create("cfg", host="localhost", port=8080)
        self.assertEqual(result["host"], "localhost")
        self.assertEqual(result["port"], 8080)

    def test_create_unknown_returns_none(self):
        result = self.factory.create("unknown")
        self.assertIsNone(result)


class TestServiceValidator(unittest.TestCase):
    def setUp(self):
        self.registry = ServiceRegistry()
        self.validator = ServiceValidator()

    def test_validate_passes_for_valid_services(self):
        self.registry.register("svc", object())
        self.assertTrue(self.validator.validate(self.registry))

    def test_validate_fails_for_empty_instance(self):
        self.registry.register("empty", None)
        result = self.validator.validate(self.registry)
        self.assertFalse(result)
        errors = self.validator.get_errors()
        self.assertTrue(any("empty" in e for e in errors))


class TestServiceMetadata(unittest.TestCase):
    def test_to_dict_includes_fields(self):
        meta = ServiceMetadata("test_svc", "1.0.0", "A test service")
        d = meta.to_dict()
        self.assertEqual(d["name"], "test_svc")
        self.assertEqual(d["version"], "1.0.0")
        self.assertEqual(d["description"], "A test service")
        self.assertEqual(d["status"], "registered")

    def test_created_at_set_on_init(self):
        meta = ServiceMetadata("x", "1", "desc")
        self.assertIsNotNone(meta.created_at)


if __name__ == "__main__":
    unittest.main()
