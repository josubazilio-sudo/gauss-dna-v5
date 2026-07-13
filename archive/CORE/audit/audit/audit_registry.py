import logging
from datetime import datetime, timezone
from typing import Any, Dict
import uuid

log = logging.getLogger(__name__)


class AuditRegistry:
    def __init__(self):
        self._audits: Dict[str, Dict[str, Any]] = {}

    def create_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def register(self, audit_id: str, scope: str, status: str) -> None:
        self._audits[audit_id] = {
            "id": audit_id,
            "scope": scope,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get(self, audit_id: str) -> Dict[str, Any]:
        return self._audits.get(audit_id, {})

    def all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._audits)
