"""
Esquema oficial de configurações do QuantOS.

Define a estrutura, tipos e valores esperados para toda configuração.
"""

from typing import Dict, Any, List, Optional


class ConfigField:
    def __init__(self, name: str, field_type: type, required: bool = True,
                 default: Any = None, allowed: List[Any] = None):
        self.name = name
        self.field_type = field_type
        self.required = required
        self.default = default
        self.allowed = allowed


class Schema:
    def __init__(self):
        self._fields: Dict[str, ConfigField] = {}

    def add_field(self, field: ConfigField) -> None:
        self._fields[field.name] = field

    def get_field(self, name: str) -> Optional[ConfigField]:
        return self._fields.get(name)

    def list_fields(self) -> Dict[str, ConfigField]:
        return dict(self._fields)
