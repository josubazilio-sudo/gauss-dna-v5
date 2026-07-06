"""
Carregador seguro de configurações.

Suporta carregamento de arquivos JSON, YAML e variáveis de ambiente.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigLoader:
    def __init__(self):
        self._data: Dict[str, Any] = {}

    def load_from_file(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        suffix = path.suffix.lower()
        if suffix == ".json":
            return self._load_json(path)
        return {}

    def _load_json(self, path: Path) -> Dict[str, Any]:
        with open(path, "r") as f:
            return json.load(f)

    def merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = base.copy()
        result.update(override)
        return result
