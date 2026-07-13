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
    DECISION_MADE = "decision.made"
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
    TRADE_OPENED = "trade.opened"
    TRADE_CLOSED = "trade.closed"

    MARKET_DATA_READY = "market.data_ready"
    WORLD_MODEL_UPDATED = "world.model_updated"
    SKILLS_OPINIONS_READY = "skills.opinions_ready"
    COUNCIL_VERDICT_READY = "council.verdict_ready"
    META_HOLD = "meta.hold"
    META_PROCEED = "meta.proceed"
    DECISION_MADE = "decision.made"
    EXECUTION_ORDER = "execution.order"
    POLICY_BLOCKED = "policy.blocked"
    POLICY_APPROVED = "policy.approved"

    WORKING_MEMORY_CREATED = "working_memory.created"
    DECISION_CONTEXT_CREATED = "decision.context.created"
    DECISION_TRACE_CREATED = "decision.trace.created"

    STATE_CHANGED = "state.changed"
    STATE_ERROR = "state.error"
    STATE_RETRY = "state.retry"
    STATE_FINISHED = "state.finished"
    STATE_CANCELLED = "state.cancelled"

    DECISION_APPROVED = "decision.approved"
    DECISION_REJECTED = "decision.rejected"
    DECISION_HOLD = "decision.hold"
