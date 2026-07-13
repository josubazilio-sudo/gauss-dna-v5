"""
Registro de Baselines certificadas.
"""

from typing import Dict, Any, Optional


class BaselineRegistry:
    def __init__(self):
        self._baselines: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, version: str, snapshot_id: str) -> None:
        key = f"{name}@{version}"
        self._baselines[key] = {
            "name": name,
            "version": version,
            "snapshot_id": snapshot_id,
            "status": "certified",
        }

    def get(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        return self._baselines.get(f"{name}@{version}")

    def list_by_name(self, name: str) -> list:
        return [
            v for k, v in self._baselines.items()
            if k.startswith(f"{name}@")
        ]

    def all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._baselines)
