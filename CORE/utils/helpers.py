import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def merge_dicts(base: dict, override: dict) -> dict:
    result = base.copy()
    result.update(override)
    return result


def safe_get(data: dict, key: str, default: Any = None) -> Any:
    return data.get(key, default)
