"""
Registro central de versões de módulos e componentes.
"""

from typing import Dict


class VersionRegistry:
    def __init__(self):
        self._versions: Dict[str, str] = {}

    def register(self, name: str, version: str = "1.0.0") -> None:
        self._versions[name] = version

    def get_version(self, name: str) -> str:
        return self._versions.get(name, "0.0.0")

    def bump_major(self, name: str) -> str:
        major, minor, patch = self._parse(name)
        new = f"{major + 1}.0.0"
        self._versions[name] = new
        return new

    def bump_minor(self, name: str) -> str:
        major, minor, patch = self._parse(name)
        new = f"{major}.{minor + 1}.0"
        self._versions[name] = new
        return new

    def bump_patch(self, name: str) -> str:
        major, minor, patch = self._parse(name)
        new = f"{major}.{minor}.{patch + 1}"
        self._versions[name] = new
        return new

    def _parse(self, name: str) -> tuple:
        version = self._versions.get(name, "1.0.0")
        parts = version.split(".")
        return int(parts[0]), int(parts[1]), int(parts[2])

    def all_versions(self) -> Dict[str, str]:
        return dict(self._versions)
