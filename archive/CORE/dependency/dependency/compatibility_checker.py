import logging
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


class CompatibilityChecker:
    def __init__(self):
        self._compatibility_map: Dict[str, Dict[str, str]] = {}

    def add_requirement(self, module: str, dependency: str, version_spec: str) -> None:
        if module not in self._compatibility_map:
            self._compatibility_map[module] = {}
        self._compatibility_map[module][dependency] = version_spec
        log.debug(f"Requirement added: {module} requires {dependency}{version_spec}")

    def check(self, module: str, dependency: str, version: str) -> bool:
        module_reqs = self._compatibility_map.get(module, {})
        required_spec = module_reqs.get(dependency)
        if required_spec is None:
            log.debug(f"No requirement for {dependency} in {module}, assuming compatible")
            return True
        result = self._version_satisfied(version, required_spec)
        if not result:
            log.warning(f"Incompatible: {module} requires {dependency}{required_spec}, got {version}")
        return result

    def check_all(self, module: str, dependency_versions: Dict[str, str]) -> bool:
        for dep, ver in dependency_versions.items():
            if not self.check(module, dep, ver):
                return False
        return True

    @staticmethod
    def _parse_version(version: str) -> tuple:
        parts = version.lstrip("vV").split(".")
        parsed = []
        for p in parts:
            try:
                parsed.append(int(p))
            except ValueError:
                parsed.append(0)
        return tuple(parsed)

    @staticmethod
    def _version_satisfied(version: str, spec: str) -> bool:
        if spec.startswith(">="):
            min_ver = spec[2:]
            return CompatibilityChecker._parse_version(version) >= CompatibilityChecker._parse_version(min_ver)
        elif spec.startswith("<="):
            max_ver = spec[2:]
            return CompatibilityChecker._parse_version(version) <= CompatibilityChecker._parse_version(max_ver)
        elif spec.startswith(">"):
            min_ver = spec[1:]
            return CompatibilityChecker._parse_version(version) > CompatibilityChecker._parse_version(min_ver)
        elif spec.startswith("<"):
            max_ver = spec[1:]
            return CompatibilityChecker._parse_version(version) < CompatibilityChecker._parse_version(max_ver)
        elif spec.startswith("=="):
            exact = spec[2:]
            return CompatibilityChecker._parse_version(version) == CompatibilityChecker._parse_version(exact)
        elif spec.startswith("!="):
            not_ver = spec[2:]
            return CompatibilityChecker._parse_version(version) != CompatibilityChecker._parse_version(not_ver)
        else:
            return CompatibilityChecker._parse_version(version) == CompatibilityChecker._parse_version(spec)
