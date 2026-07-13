import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from ENGINE.core.state_config import (
    FINAL_STATES,
    FORWARD_MAP,
    INITIAL_STATE,
    MAX_RETRIES,
    MODULE_BY_STATE,
    RECOVERY_MAP,
    STATE_TIMEOUT_MS,
)
from ENGINE.core.state_types import StateContext, SystemState

log = logging.getLogger(__name__)


class StateMachine:

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus
        self._context: Optional[StateContext] = None
        self._history: List[StateContext] = []

    @property
    def context(self) -> Optional[StateContext]:
        return self._context

    @property
    def history(self) -> List[StateContext]:
        return list(self._history)

    def start(self, cycle_id: str) -> StateContext:
        now = datetime.now(timezone.utc)
        ctx = StateContext(
            cycle_id=cycle_id,
            state=INITIAL_STATE.value,
            started_at=now,
            updated_at=now,
            timeout_ms=STATE_TIMEOUT_MS.get(INITIAL_STATE, 30000),
            state_hash="",
        )
        final = StateContext(
            cycle_id=ctx.cycle_id,
            state=ctx.state,
            previous_state=ctx.previous_state,
            next_state=FORWARD_MAP.get(INITIAL_STATE, SystemState.MARKET_READY).value,
            started_at=ctx.started_at,
            updated_at=ctx.updated_at,
            execution_time_ms=ctx.execution_time_ms,
            retry_count=ctx.retry_count,
            timeout_ms=ctx.timeout_ms,
            module_name=MODULE_BY_STATE.get(INITIAL_STATE, ""),
            error_message=ctx.error_message,
            state_hash=StateContext.compute_hash(ctx),
        )
        self._context = final
        self._history.append(final)
        self._publish(EventTypes.STATE_CHANGED, final)
        return final

    def transition(self, target_state: SystemState) -> StateContext:
        if self._context is None:
            raise RuntimeError("StateMachine not started. Call start() first.")

        current = SystemState(self._context.state)

        if self._is_final(current):
            raise RuntimeError(f"Cannot transition from final state: {current.value}")

        if target_state == SystemState.ERROR:
            return self._enter_error()

        if current == SystemState.ERROR:
            if target_state == SystemState.RECOVERY:
                return self._enter_recovery()
            raise RuntimeError(f"Cannot transition from ERROR to {target_state.value}")

        if current == SystemState.RECOVERY:
            if target_state == SystemState.RETRY:
                return self._enter_retry()
            raise RuntimeError(f"Cannot transition from RECOVERY to {target_state.value}")

        if current == SystemState.RETRY:
            if target_state in FINAL_STATES:
                return self._enter_cancelled()
            if target_state in FORWARD_MAP.values() or target_state in FORWARD_MAP:
                return self._enter_forward(target_state)
            raise RuntimeError(f"Cannot transition from RETRY to {target_state.value}")

        expected = self._expected_next(current)
        if target_state != expected:
            raise RuntimeError(
                f"Invalid transition: {current.value} -> {target_state.value}. "
                f"Expected: {expected.value}"
            )

        return self._enter_forward(target_state)

    def transition_to(self, target_state_str: str) -> StateContext:
        return self.transition(SystemState(target_state_str))

    def _enter_forward(self, target: SystemState) -> StateContext:
        current = SystemState(self._context.state)
        now = datetime.now(timezone.utc)
        elapsed = 0.0
        if self._context.updated_at:
            elapsed = (now - self._context.updated_at).total_seconds() * 1000

        ctx = StateContext(
            cycle_id=self._context.cycle_id,
            state=target.value,
            previous_state=current.value,
            next_state=self._compute_next(target),
            started_at=self._context.started_at,
            updated_at=now,
            execution_time_ms=round(elapsed, 2),
            retry_count=self._context.retry_count,
            timeout_ms=STATE_TIMEOUT_MS.get(target, 30000),
            module_name=MODULE_BY_STATE.get(target, ""),
            error_message="",
            state_hash="",
        )
        final = StateContext(
            cycle_id=ctx.cycle_id,
            state=ctx.state,
            previous_state=ctx.previous_state,
            next_state=ctx.next_state,
            started_at=ctx.started_at,
            updated_at=ctx.updated_at,
            execution_time_ms=ctx.execution_time_ms,
            retry_count=ctx.retry_count,
            timeout_ms=ctx.timeout_ms,
            module_name=ctx.module_name,
            error_message=ctx.error_message,
            state_hash=StateContext.compute_hash(ctx),
        )
        self._context = final
        self._history.append(final)

        if target == SystemState.FINISHED:
            self._publish(EventTypes.STATE_FINISHED, final)
        else:
            self._publish(EventTypes.STATE_CHANGED, final)
        return final

    def _enter_error(self) -> StateContext:
        current = SystemState(self._context.state)
        now = datetime.now(timezone.utc)
        elapsed = 0.0
        if self._context.updated_at:
            elapsed = (now - self._context.updated_at).total_seconds() * 1000

        ctx = StateContext(
            cycle_id=self._context.cycle_id,
            state=SystemState.ERROR.value,
            previous_state=current.value,
            next_state=SystemState.RECOVERY.value,
            started_at=self._context.started_at,
            updated_at=now,
            execution_time_ms=round(elapsed, 2),
            retry_count=self._context.retry_count,
            timeout_ms=STATE_TIMEOUT_MS.get(SystemState.ERROR, 30000),
            module_name=MODULE_BY_STATE.get(current, ""),
            error_message=self._context.error_message or "Unknown error",
            state_hash="",
        )
        final = StateContext(
            cycle_id=ctx.cycle_id,
            state=ctx.state,
            previous_state=ctx.previous_state,
            next_state=ctx.next_state,
            started_at=ctx.started_at,
            updated_at=ctx.updated_at,
            execution_time_ms=ctx.execution_time_ms,
            retry_count=ctx.retry_count,
            timeout_ms=ctx.timeout_ms,
            module_name=ctx.module_name,
            error_message=ctx.error_message,
            state_hash=StateContext.compute_hash(ctx),
        )
        self._context = final
        self._history.append(final)
        self._publish(EventTypes.STATE_ERROR, final)
        return final

    def _enter_recovery(self) -> StateContext:
        now = datetime.now(timezone.utc)
        elapsed = 0.0
        if self._context.updated_at:
            elapsed = (now - self._context.updated_at).total_seconds() * 1000

        ctx = StateContext(
            cycle_id=self._context.cycle_id,
            state=SystemState.RECOVERY.value,
            previous_state=SystemState.ERROR.value,
            next_state=SystemState.RETRY.value,
            started_at=self._context.started_at,
            updated_at=now,
            execution_time_ms=round(elapsed, 2),
            retry_count=self._context.retry_count,
            timeout_ms=STATE_TIMEOUT_MS.get(SystemState.RECOVERY, 30000),
            module_name="RecoveryManager",
            error_message="",
            state_hash="",
        )
        final = StateContext(
            cycle_id=ctx.cycle_id,
            state=ctx.state,
            previous_state=ctx.previous_state,
            next_state=ctx.next_state,
            started_at=ctx.started_at,
            updated_at=ctx.updated_at,
            execution_time_ms=ctx.execution_time_ms,
            retry_count=ctx.retry_count,
            timeout_ms=ctx.timeout_ms,
            module_name=ctx.module_name,
            error_message=ctx.error_message,
            state_hash=StateContext.compute_hash(ctx),
        )
        self._context = final
        self._history.append(final)
        self._publish(EventTypes.STATE_RETRY, final)
        return final

    def _enter_retry(self) -> StateContext:
        new_retry = self._context.retry_count + 1
        now = datetime.now(timezone.utc)
        elapsed = 0.0
        if self._context.updated_at:
            elapsed = (now - self._context.updated_at).total_seconds() * 1000

        if new_retry > MAX_RETRIES:
            return self._enter_cancelled()

        previous = self._find_last_good_state()
        ctx = StateContext(
            cycle_id=self._context.cycle_id,
            state=SystemState.RETRY.value,
            previous_state=SystemState.RECOVERY.value,
            next_state=previous,
            started_at=self._context.started_at,
            updated_at=now,
            execution_time_ms=round(elapsed, 2),
            retry_count=new_retry,
            timeout_ms=STATE_TIMEOUT_MS.get(previous, 30000) if previous else 30000,
            module_name=MODULE_BY_STATE.get(previous, "Unknown") if previous else "Unknown",
            error_message="",
            state_hash="",
        )
        final = StateContext(
            cycle_id=ctx.cycle_id,
            state=ctx.state,
            previous_state=ctx.previous_state,
            next_state=ctx.next_state,
            started_at=ctx.started_at,
            updated_at=ctx.updated_at,
            execution_time_ms=ctx.execution_time_ms,
            retry_count=ctx.retry_count,
            timeout_ms=ctx.timeout_ms,
            module_name=ctx.module_name,
            error_message=ctx.error_message,
            state_hash=StateContext.compute_hash(ctx),
        )
        self._context = final
        self._history.append(final)
        self._publish(EventTypes.STATE_RETRY, final)
        return final

    def _enter_cancelled(self) -> StateContext:
        now = datetime.now(timezone.utc)
        elapsed = 0.0
        if self._context.updated_at:
            elapsed = (now - self._context.updated_at).total_seconds() * 1000

        ctx = StateContext(
            cycle_id=self._context.cycle_id,
            state=SystemState.CANCELLED.value,
            previous_state=self._context.state,
            next_state=None,
            started_at=self._context.started_at,
            updated_at=now,
            execution_time_ms=round(elapsed, 2),
            retry_count=self._context.retry_count,
            timeout_ms=STATE_TIMEOUT_MS.get(SystemState.CANCELLED, 5000),
            module_name="System",
            error_message="Max retries exceeded",
            state_hash="",
        )
        final = StateContext(
            cycle_id=ctx.cycle_id,
            state=ctx.state,
            previous_state=ctx.previous_state,
            next_state=ctx.next_state,
            started_at=ctx.started_at,
            updated_at=ctx.updated_at,
            execution_time_ms=ctx.execution_time_ms,
            retry_count=ctx.retry_count,
            timeout_ms=ctx.timeout_ms,
            module_name=ctx.module_name,
            error_message=ctx.error_message,
            state_hash=StateContext.compute_hash(ctx),
        )
        self._context = final
        self._history.append(final)
        self._publish(EventTypes.STATE_CANCELLED, final)
        return final

    def set_error(self, error_message: str) -> StateContext:
        if self._context is None:
            raise RuntimeError("StateMachine not started.")

        ctx = StateContext(
            cycle_id=self._context.cycle_id,
            state=self._context.state,
            previous_state=self._context.previous_state,
            next_state=self._context.next_state,
            started_at=self._context.started_at,
            updated_at=self._context.updated_at,
            execution_time_ms=self._context.execution_time_ms,
            retry_count=self._context.retry_count,
            timeout_ms=self._context.timeout_ms,
            module_name=self._context.module_name,
            error_message=error_message,
            state_hash=self._context.state_hash,
        )
        self._context = ctx
        self._history.append(ctx)
        return self.transition(SystemState.ERROR)

    def _find_last_good_state(self) -> Optional[str]:
        for ctx in reversed(self._history):
            s = ctx.state
            if s in [state.value for state in FORWARD_MAP]:
                return s
            if s == SystemState.INITIALIZING.value:
                return s
        return SystemState.INITIALIZING.value

    def _expected_next(self, state: SystemState) -> SystemState:
        return FORWARD_MAP.get(state, SystemState.FINISHED)

    def _compute_next(self, state: SystemState) -> Optional[str]:
        nxt = FORWARD_MAP.get(state)
        return nxt.value if nxt else None

    def _is_final(self, state: SystemState) -> bool:
        return state in FINAL_STATES

    def _publish(self, event_type: str, ctx: StateContext) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(Event(
                event_type,
                {
                    "cycle_id": ctx.cycle_id,
                    "state": ctx.state,
                    "previous_state": ctx.previous_state,
                    "state_hash": ctx.state_hash,
                    "retry_count": ctx.retry_count,
                },
            ))
        except Exception as e:
            log.error("Failed to publish %s: %s", event_type, e)

    def is_in_state(self, state: SystemState) -> bool:
        return self._context is not None and self._context.state == state.value

    def is_active(self) -> bool:
        return self._context is not None and not self._is_final(
            SystemState(self._context.state)
        )

    def clear(self) -> None:
        self._context = None
        self._history.clear()

    def get_pipeline_status(self) -> List[str]:
        return [h.state for h in self._history]
