import unittest
import sys

sys.path.insert(0, 'C:\\Users\\josue\\QuantOS')

from CORE.config.constants import Constants
from CORE.config.schema import Schema, ConfigField
from CORE.config.rules import Rules
from CORE.config.validation import ConfigValidator
from CORE.config.validation_report import ValidationResult, ValidationReport
from CORE.config.loader import ConfigLoader


class TestConstants(unittest.TestCase):
    def test_project_name_exists(self):
        self.assertEqual(Constants.PROJECT_NAME, "QuantOS")

    def test_version_exists(self):
        self.assertEqual(Constants.VERSION, "1.0.0")

    def test_metrics_values_exist(self):
        self.assertAlmostEqual(Constants.Metrics.MIN_PROFIT_FACTOR, 2.50)
        self.assertAlmostEqual(Constants.Metrics.MIN_WIN_RATE, 60.0)
        self.assertAlmostEqual(Constants.Metrics.MAX_DRAWDOWN, 10.0)

    def test_paths_exist(self):
        self.assertEqual(Constants.Paths.BASELINES, "baselines")
        self.assertEqual(Constants.Paths.MEMORY, "memory")
        self.assertEqual(Constants.Paths.REPORTS, "reports")

    def test_default_config_path_exists(self):
        self.assertEqual(Constants.DEFAULT_CONFIG_PATH, "config.json")


class TestSchemaFieldValidation(unittest.TestCase):
    def setUp(self):
        self.schema = Schema()
        self.schema.add_field(ConfigField("host", str, required=True))
        self.schema.add_field(ConfigField("port", int, required=True, default=8080))
        self.schema.add_field(ConfigField("mode", str, required=False, default="auto", allowed=["auto", "manual"]))

    def test_get_field_returns_field(self):
        field = self.schema.get_field("host")
        self.assertIsNotNone(field)
        self.assertEqual(field.name, "host")
        self.assertEqual(field.field_type, str)

    def test_get_field_missing_returns_none(self):
        self.assertIsNone(self.schema.get_field("missing"))

    def test_list_fields_returns_all(self):
        fields = self.schema.list_fields()
        self.assertIn("host", fields)
        self.assertIn("port", fields)
        self.assertIn("mode", fields)

    def test_field_default_values(self):
        field = self.schema.get_field("port")
        self.assertEqual(field.default, 8080)

    def test_field_allowed_values(self):
        field = self.schema.get_field("mode")
        self.assertEqual(field.allowed, ["auto", "manual"])


class TestRules(unittest.TestCase):
    def setUp(self):
        self.schema = Schema()
        self.schema.add_field(ConfigField("host", str, required=True))
        self.schema.add_field(ConfigField("port", int, required=True))
        self.schema.add_field(ConfigField("mode", str, required=False, allowed=["auto", "manual"]))
        self.rules = Rules(self.schema)

    def test_check_required_missing(self):
        missing = self.rules.check_required({"mode": "auto"})
        self.assertIn("host", missing)
        self.assertIn("port", missing)

    def test_check_required_all_present(self):
        missing = self.rules.check_required({"host": "localhost", "port": 8080})
        self.assertEqual(missing, [])

    def test_check_types_valid(self):
        errors = self.rules.check_types({"host": "localhost", "port": 8080})
        self.assertEqual(errors, [])

    def test_check_types_invalid(self):
        errors = self.rules.check_types({"host": "localhost", "port": "not_a_number"})
        self.assertTrue(any("port" in e for e in errors))

    def test_check_allowed_valid(self):
        errors = self.rules.check_allowed({"mode": "auto"})
        self.assertEqual(errors, [])

    def test_check_allowed_invalid(self):
        errors = self.rules.check_allowed({"mode": "invalid_mode"})
        self.assertTrue(any("mode" in e for e in errors))


class TestConfigValidator(unittest.TestCase):
    def test_validate_valid_config(self):
        validator = ConfigValidator({"project_name": "Test", "version": "1.0", "environment": "development"})
        self.assertTrue(validator.validate())

    def test_validate_missing_required(self):
        validator = ConfigValidator({})
        self.assertFalse(validator.validate())

    def test_validate_debug_in_production(self):
        validator = ConfigValidator({
            "project_name": "Test", "version": "1.0",
            "environment": "production", "debug": True,
        })
        self.assertFalse(validator.validate())

    def test_validate_wrong_type(self):
        validator = ConfigValidator({
            "project_name": "Test", "version": "1.0",
            "environment": "dev", "debug": "yes",
        })
        self.assertFalse(validator.validate())


class TestValidationReport(unittest.TestCase):
    def test_generate_with_errors(self):
        result = ValidationResult()
        result.add_error("Missing host")
        report = ValidationReport(result)
        output = report.generate()
        self.assertIn("INVALID", output)
        self.assertIn("Missing host", output)

    def test_generate_with_warnings(self):
        result = ValidationResult()
        result.add_warning("Deprecated field")
        report = ValidationReport(result)
        output = report.generate()
        self.assertIn("VALID", output)
        self.assertIn("Deprecated field", output)

    def test_generate_valid(self):
        result = ValidationResult()
        report = ValidationReport(result)
        output = report.generate()
        self.assertIn("VALID", output)

    def test_validation_result_defaults(self):
        result = ValidationResult()
        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])


class TestConfigLoader(unittest.TestCase):
    def setUp(self):
        self.loader = ConfigLoader()

    def test_load_missing_file(self):
        import tempfile
        from pathlib import Path
        missing = Path(tempfile.gettempdir()) / "_nonexistent_quantos_test_.json"
        result = self.loader.load_from_file(missing)
        self.assertEqual(result, {})

    def test_merge_dicts(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        merged = self.loader.merge(base, override)
        self.assertEqual(merged["a"], 1)
        self.assertEqual(merged["b"], 3)
        self.assertEqual(merged["c"], 4)


if __name__ == "__main__":
    unittest.main()
