from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict


@dataclass
class Event:
    type: str
    data: Dict[str, Any] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        if self.data is None:
            self.data = {}


class EventTypes:
    ENGINE_START = "engine.start"
    ENGINE_STOP = "engine.stop"
    ENGINE_ERROR = "engine.error"
    SCAN_COMPLETE = "scan.complete"
    SIGNAL_GENERATED = "signal.generated"
    ORDER_EXECUTED = "order.executed"
    BASELINE_CREATED = "baseline.created"
    SYSTEM_BOOT = "system.boot"
    SYSTEM_SHUTDOWN = "system.shutdown"
    CONFIG_CHANGED = "config.changed"
    RECOVERY_ATTEMPTED = "recovery.attempted"
    RECOVERY_ROLLBACK = "recovery.rollback"
    METRICS_COLLECTED = "metrics.collected"
    AUDIT_COMPLETED = "audit.completed"
    NOTIFICATION_SENT = "notification.sent"
