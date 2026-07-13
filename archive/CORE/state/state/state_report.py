"""Relatórios de estado."""

import logging
from typing import Dict, Any

log = logging.getLogger(__name__)


class StateReport:
    def generate(self, data: Dict[str, Any]) -> str:
        lines = ["=== State Report ==="]
        if not data:
            lines.append("  (no state data)")
        else:
            for key, value in data.items():
                lines.append(f"  {key}: {value}")
        log.debug("Generated state report with %d keys", len(data))
        return "\n".join(lines)
