import logging
from datetime import datetime, timezone
from typing import Dict, Any

log = logging.getLogger(__name__)


class ServiceMetadata:
    def __init__(self, name: str, version: str, description: str):
        self.name = name
        self.version = version
        self.description = description
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        self.status = "registered"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status,
        }
