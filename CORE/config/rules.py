"""
Regras oficiais de validação de configurações.
"""

from typing import Dict, Any, List
from .schema import Schema


class Rules:
    def __init__(self, schema: Schema):
        self._schema = schema

    def check_required(self, config: Dict[str, Any]) -> List[str]:
        missing = []
        for name, field in self._schema.list_fields().items():
            if field.required and name not in config:
                missing.append(name)
        return missing

    def check_types(self, config: Dict[str, Any]) -> List[str]:
        errors = []
        for name, value in config.items():
            field = self._schema.get_field(name)
            if field and not isinstance(value, field.field_type):
                errors.append(f"{name}: esperado {field.field_type.__name__}")
        return errors

    def check_allowed(self, config: Dict[str, Any]) -> List[str]:
        errors = []
        for name, value in config.items():
            field = self._schema.get_field(name)
            if field and field.allowed and value not in field.allowed:
                errors.append(f"{name}: valor {value} nao permitido")
        return errors
