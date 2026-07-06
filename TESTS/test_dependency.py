import unittest
import sys

sys.path.insert(0, 'C:\\Users\\josue\\QuantOS')

from CORE.dependency import (
    DependencyGraph, DependencyManager, CompatibilityChecker,
    DependencyRegistry, DependencyValidator,
)


class TestDependencyGraph(unittest.TestCase):
    def test_has_cycle_no_cycle(self):
        graph = DependencyGraph()
        graph.add_module("a", ["b"])
        graph.add_module("b", ["c"])
        graph.add_module("c", [])
        self.assertFalse(graph.has_cycle())

    def test_has_cycle_detects_cycle(self):
        graph = DependencyGraph()
        graph.add_module("a", ["b"])
        graph.add_module("b", ["c"])
        graph.add_module("c", ["a"])
        self.assertTrue(graph.has_cycle())

    def test_has_cycle_self_reference(self):
        graph = DependencyGraph()
        graph.add_module("a", ["a"])
        self.assertTrue(graph.has_cycle())

    def test_get_dependents(self):
        graph = DependencyGraph()
        graph.add_module("a", ["b"])
        graph.add_module("b", [])
        graph.add_module("c", ["b"])
        deps = graph.get_dependents("b")
        self.assertIn("a", deps)
        self.assertIn("c", deps)
        self.assertEqual(len(deps), 2)

    def test_empty_graph_no_cycle(self):
        graph = DependencyGraph()
        self.assertFalse(graph.has_cycle())


class TestDependencyRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = DependencyRegistry()

    def test_register_and_get_dependencies(self):
        self.registry.register("mod", ["dep1", "dep2"])
        deps = self.registry.get_dependencies("mod")
        self.assertEqual(deps, ["dep1", "dep2"])

    def test_module_exists(self):
        self.registry.register("mod", [])
        self.assertTrue(self.registry.module_exists("mod"))
        self.assertFalse(self.registry.module_exists("unknown"))

    def test_list_modules(self):
        self.registry.register("a", [])
        self.registry.register("b", [])
        modules = self.registry.list_modules()
        self.assertIn("a", modules)
        self.assertEqual(len(modules), 2)


class TestDependencyValidator(unittest.TestCase):
    def setUp(self):
        self.registry = DependencyRegistry()
        self.graph = DependencyGraph()
        self.validator = DependencyValidator()

    def test_validate_passes_with_all_deps(self):
        self.registry.register("a", ["b"])
        self.registry.register("b", [])
        self.graph.add_module("a", ["b"])
        self.graph.add_module("b", [])
        self.assertTrue(self.validator.validate(self.registry, self.graph))

    def test_validate_fails_missing_dep(self):
        self.registry.register("a", ["missing"])
        self.graph.add_module("a", ["missing"])
        self.assertFalse(self.validator.validate(self.registry, self.graph))

    def test_validate_fails_cycle(self):
        self.registry.register("a", ["b"])
        self.registry.register("b", ["a"])
        self.graph.add_module("a", ["b"])
        self.graph.add_module("b", ["a"])
        self.assertFalse(self.validator.validate(self.registry, self.graph))

    def test_can_initialize_checks_deps(self):
        self.registry.register("a", ["b"])
        self.registry.register("b", [])
        self.assertTrue(self.validator.can_initialize("a", self.registry))

    def test_can_initialize_fails_missing_dep(self):
        self.registry.register("a", ["missing"])
        self.assertFalse(self.validator.can_initialize("a", self.registry))


class TestDependencyManager(unittest.TestCase):
    def setUp(self):
        self.manager = DependencyManager()

    def test_register_module(self):
        self.manager.register_module("mod", ["dep1"])
        result = self.manager.validate_all()
        self.assertFalse(result)

    def test_register_module_valid(self):
        self.manager.register_module("mod", [])
        result = self.manager.validate_all()
        self.assertTrue(result)

    def test_can_initialize(self):
        self.manager.register_module("mod", ["dep"])
        self.assertFalse(self.manager.can_initialize("mod"))


class TestCompatibilityChecker(unittest.TestCase):
    def setUp(self):
        self.checker = CompatibilityChecker()

    def test_version_satisfied_ge(self):
        self.checker.add_requirement("engine", "scanner", ">=1.0")
        self.assertTrue(self.checker.check("engine", "scanner", "2.0"))

    def test_version_not_satisfied_ge(self):
        self.checker.add_requirement("engine", "scanner", ">=2.0")
        self.assertFalse(self.checker.check("engine", "scanner", "1.0"))

    def test_version_satisfied_exact(self):
        self.checker.add_requirement("mod", "dep", "==1.0")
        self.assertTrue(self.checker.check("mod", "dep", "1.0"))

    def test_version_not_satisfied_exact(self):
        self.checker.add_requirement("mod", "dep", "==2.0")
        self.assertFalse(self.checker.check("mod", "dep", "1.0"))

    def test_no_requirement_returns_true(self):
        self.assertTrue(self.checker.check("a", "b", "1.0"))

    def test_check_all_passes(self):
        self.checker.add_requirement("mod", "dep1", ">=1.0")
        self.checker.add_requirement("mod", "dep2", ">=2.0")
        self.assertTrue(self.checker.check_all("mod", {"dep1": "1.5", "dep2": "2.5"}))

    def test_check_all_fails(self):
        self.checker.add_requirement("mod", "dep1", ">=2.0")
        self.assertFalse(self.checker.check_all("mod", {"dep1": "1.0"}))

    def test_version_comparison_le(self):
        self.checker.add_requirement("mod", "dep", "<=2.0")
        self.assertTrue(self.checker.check("mod", "dep", "1.0"))
        self.assertFalse(self.checker.check("mod", "dep", "3.0"))

    def test_version_comparison_lt(self):
        self.checker.add_requirement("mod", "dep", "<2.0")
        self.assertTrue(self.checker.check("mod", "dep", "1.0"))
        self.assertFalse(self.checker.check("mod", "dep", "2.0"))

    def test_version_comparison_gt(self):
        self.checker.add_requirement("mod", "dep", ">1.0")
        self.assertTrue(self.checker.check("mod", "dep", "2.0"))
        self.assertFalse(self.checker.check("mod", "dep", "1.0"))

    def test_version_spec_without_prefix(self):
        self.checker.add_requirement("mod", "dep", "1.0")
        self.assertTrue(self.checker.check("mod", "dep", "1.0"))
        self.assertFalse(self.checker.check("mod", "dep", "2.0"))

    def test_parse_version_handles_v_prefix(self):
        parsed = CompatibilityChecker._parse_version("v1.2.3")
        self.assertEqual(parsed, (1, 2, 3))

    def test_parse_version_handles_non_numeric(self):
        parsed = CompatibilityChecker._parse_version("1.a.3")
        self.assertEqual(parsed, (1, 0, 3))


if __name__ == "__main__":
    unittest.main()
