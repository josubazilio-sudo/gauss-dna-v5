import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class InstitutionalMemory:
    def __init__(self, storage_path: str = "MEMORY/institutional"):
        self._storage_path = storage_path
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        os.makedirs(self._storage_path, exist_ok=True)

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def store_decision(self, decision_id: str, data: Dict[str, Any]) -> str:
        data["stored_at"] = datetime.now(timezone.utc).isoformat()
        data_hash = self._compute_hash(data)
        data["decision_hash"] = data_hash
        file_path = os.path.join(self._storage_path, f"{decision_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        log.info("Decision stored: %s (hash=%s)", decision_id, data_hash)
        return data_hash

    def load_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        file_path = os.path.join(self._storage_path, f"{decision_id}.json")
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_decisions(self) -> List[str]:
        files = os.listdir(self._storage_path)
        return [f.replace(".json", "") for f in files if f.endswith(".json")]

    def verify_decision(self, decision_id: str) -> Optional[bool]:
        data = self.load_decision(decision_id)
        if data is None:
            return None
        original_hash = data.get("decision_hash")
        if original_hash is None:
            return None
        stored = {k: v for k, v in data.items() if k != "decision_hash"}
        computed = self._compute_hash(stored)
        return computed == original_hash

    def delete_decision(self, decision_id: str) -> bool:
        file_path = os.path.join(self._storage_path, f"{decision_id}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
