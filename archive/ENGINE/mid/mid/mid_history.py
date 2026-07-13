import json
import logging
import os
from typing import Dict, List, Optional

from .mid_config import MID_HISTORY_DIR, MID_MAX_HISTORY

log = logging.getLogger(__name__)


class MIDHistory:
    def __init__(self):
        self._snapshots: List[Dict] = []
        self._load()

    def _load(self):
        path = os.path.join(MID_HISTORY_DIR, "history.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._snapshots = json.load(f)[-MID_MAX_HISTORY:]
            except Exception as e:
                log.warning("MIDHistory: erro ao carregar historico: %s", e)
                self._snapshots = []

    def save(self, snapshot: Dict):
        self._snapshots.append(snapshot)
        if len(self._snapshots) > MID_MAX_HISTORY:
            self._snapshots = self._snapshots[-MID_MAX_HISTORY:]
        self._persist()

    def _persist(self):
        os.makedirs(MID_HISTORY_DIR, exist_ok=True)
        path = os.path.join(MID_HISTORY_DIR, "history.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._snapshots, f, indent=2, default=str)
        except Exception as e:
            log.warning("MIDHistory: erro ao salvar historico: %s", e)

    def get_recent(self, n: int = 10) -> List[Dict]:
        return self._snapshots[-n:]

    def all(self) -> List[Dict]:
        return self._snapshots
