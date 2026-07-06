"""Relatórios de notificações."""

import logging
from typing import List, Dict, Any

log = logging.getLogger(__name__)


class NotificationReport:
    def generate(self, notifications: List[Dict[str, Any]]) -> str:
        lines = ["=== Notification Report ==="]
        if not notifications:
            lines.append("  (no notifications)")
        else:
            for n in notifications[-20:]:
                lines.append(f"  [{n['channel']}] {n['title']}")
        log.debug("Generated notification report with %d entries", min(len(notifications), 20))
        return "\n".join(lines)
