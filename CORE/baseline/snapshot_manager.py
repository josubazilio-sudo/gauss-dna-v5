import logging
from datetime import datetime, timezone
from typing import Dict, Any

log = logging.getLogger(__name__)


class SnapshotManager:
    def __init__(self):
        self._log = log
        self._snapshots: Dict[str, Any] = {}

    def create(self, name: str, version: str) -> str:
        now = datetime.now(timezone.utc)
        snapshot_id = f"{name}@{version}-{now.strftime('%Y%m%d%H%M%S')}"
        self._snapshots[snapshot_id] = {
            "name": name,
            "version": version,
            "created_at": now.isoformat(),
            "status": "active",
        }
        self._log.info(f"Snapshot criado: {snapshot_id}")
        return snapshot_id

    def get(self, snapshot_id: str) -> Dict[str, Any]:
        return self._snapshots.get(snapshot_id, {})
