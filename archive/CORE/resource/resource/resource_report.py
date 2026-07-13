"""Relatórios de recursos."""

import logging
from typing import List, Dict, Any

log = logging.getLogger(__name__)


class ResourceReport:
    def generate(self, history: List[Dict[str, Any]]) -> str:
        lines = ["=== Resource Report ==="]
        if not history:
            lines.append("  (no data)")
            return "\n".join(lines)
        for entry in history[-10:]:
            lines.append(f"  {entry['timestamp']}: {entry['usage']}")
        log.debug("Generated report with %d entries", min(len(history), 10))
        return "\n".join(lines)
