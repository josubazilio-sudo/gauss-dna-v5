import json
import unittest
from datetime import datetime, timezone
from typing import List

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from ENGINE.core.state_config import FORWARD_ORDER, INITIAL_STATE, MAX_RETRIES, STATE_TIMEOUT_MS
from ENGINE.core.state_machine import StateMachine
from ENGINE.core.state_types import StateContext, SystemState


class TestSystemState(unittest.TestCase):

    def test_all_states_defined(self):
        expected = [
            "INITIALIZING", "MARKET_READY", "WORLD_READY",
            "SKILLS_RUNNING", "SKILLS_READY", "GRAPH_BUILDING", "GRAPH_READY",
            "HEALTH_READY", "WEIGHTS_READY", "CONSENSUS_READY",
            "META_READY", "POLICY_READY", "WORKING_MEMORY_READY",
            "DECISION_CONTEXT_READY", "DECISION_READY", "RISK_READY",
            "EXECUTION_READY", "LEARNING_READY", "FINISHED",
            "ERROR", "RECOVERY", "RETRY", "CANCELLED",
        ]
        self.assertEqual(len(SystemState), len(expected))
        for s in expected:
            self.assertIn(s, [e.value for e in SystemState])

    def test_state_values_match_enum(self):
        for s in SystemState:
            self.assertEqual(s.value, s.name)


class TestStateContext(unittest.TestCase):

    def test_create_minimal(self):
        ctx = StateContext(cycle_id="c1", state="INITIALIZING")
        self.assertEqual(ctx.cycle_id, "c1")
        self.assertEqual(ctx.state, "INITIALIZING")
        self.assertIsNone(ctx.previous_state)
        self.assertEqual(ctx.retry_count, 0)

    def test_immutable(self):
        ctx = StateContext(cycle_id="c1", state="INITIALIZING")
        with self.assertRaises(Exception):
            ctx.state = "ERROR"

    def test_to_dict(self):
        ctx = StateContext(cycle_id="c1", state="MARKET_READY", previous_state="INITIALIZING")
        d = ctx.to_dict()
        self.assertEqual(d["cycle_id"], "c1")
        self.assertEqual(d["state"], "MARKET_READY")
        self.assertEqual(d["previous_state"], "INITIALIZING")
        self.assertIn("state_hash", d)
        self.assertIn("started_at", d)

    def test_to_json(self):
        ctx = StateContext(cycle_id="c1", state="INITIALIZING")
        j = ctx.to_json()
        d = json.loads(j)
        self.assertEqual(d["cycle_id"], "c1")
        self.assertEqual(d["state"], "INITIALIZING")

    def test_from_dict_roundtrip(self):
        ctx = StateContext(cycle_id="c1", state="CONSENSUS_READY", retry_count=2)
        d = ctx.to_dict()
        ctx2 = StateContext.from_dict(d)
        self.assertEqual(ctx2.cycle_id, ctx.cycle_id)
        self.assertEqual(ctx2.state, ctx.state)
        self.assertEqual(ctx2.retry_count, ctx.retry_count)

    def test_from_json_roundtrip(self):
        import json as jmod
        ctx = StateContext(cycle_id="c1", state="FINISHED")
        j = ctx.to_json()
        ctx2 = StateContext.from_json(j)
        self.assertEqual(ctx2.cycle_id, ctx.cycle_id)
        self.assertEqual(ctx2.state, ctx.state)
        self.assertEqual(ctx2.state_hash, ctx.state_hash)

    def test_hash_deterministic(self):
        now = datetime.now(timezone.utc)
        ctx1 = StateContext(cycle_id="c1", state="INITIALIZING", started_at=now, updated_at=now)
        ctx2 = StateContext(cycle_id="c1", state="INITIALIZING", started_at=now, updated_at=now)
        self.assertEqual(StateContext.compute_hash(ctx1), StateContext.compute_hash(ctx2))

    def test_hash_changes(self):
        ctx1 = StateContext(cycle_id="c1", state="INITIALIZING")
        ctx2 = StateContext(cycle_id="c1", state="MARKET_READY")
        self.assertNotEqual(StateContext.compute_hash(ctx1), StateContext.compute_hash(ctx2))

    def test_serialization_with_none_fields(self):
        ctx = StateContext(cycle_id="c1", state="INITIALIZING", previous_state=None, next_state=None)
        d = ctx.to_dict()
        self.assertIsNone(d["previous_state"])
        self.assertIsNone(d["next_state"])
        ctx2 = StateContext.from_dict(d)
        self.assertIsNone(ctx2.previous_state)


class TestStateMachineBasics(unittest.TestCase):

    def test_start_creates_context(self):
        sm = StateMachine()
        ctx = sm.start("cycle_1")
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.cycle_id, "cycle_1")
        self.assertEqual(ctx.state, SystemState.INITIALIZING.value)
        self.assertEqual(ctx.previous_state, None)
        self.assertEqual(ctx.next_state, SystemState.MARKET_READY.value)
        self.assertIsNotNone(ctx.state_hash)

    def test_start_makes_active(self):
        sm = StateMachine()
        sm.start("c1")
        self.assertTrue(sm.is_active())

    def test_is_in_state(self):
        sm = StateMachine()
        sm.start("c1")
        self.assertTrue(sm.is_in_state(SystemState.INITIALIZING))
        self.assertFalse(sm.is_in_state(SystemState.MARKET_READY))

    def test_context_property(self):
        sm = StateMachine()
        self.assertIsNone(sm.context)
        ctx = sm.start("c1")
        self.assertIs(sm.context, ctx)

    def test_not_started_raises(self):
        sm = StateMachine()
        with self.assertRaises(RuntimeError):
            sm.transition(SystemState.MARKET_READY)

    def test_history_on_start(self):
        sm = StateMachine()
        sm.start("c1")
        self.assertEqual(len(sm.history), 1)
        self.assertEqual(sm.history[0].state, SystemState.INITIALIZING.value)

    def test_get_pipeline_status(self):
        sm = StateMachine()
        sm.start("c1")
        status = sm.get_pipeline_status()
        self.assertEqual(status, [SystemState.INITIALIZING.value])


class TestStateMachineNormalFlow(unittest.TestCase):

    def _run_full_cycle(self, sm: StateMachine) -> List[str]:
        states = [s.value for s in FORWARD_ORDER]
        sm.start("full_cycle")
        for s in states[1:]:
            sm.transition(SystemState(s))
        return [h.state for h in sm.history]

    def test_full_forward_flow(self):
        sm = StateMachine()
        history = self._run_full_cycle(sm)
        expected = [s.value for s in FORWARD_ORDER]
        self.assertEqual(len(history), len(expected))
        for i, exp in enumerate(expected):
            self.assertEqual(history[i], exp)

    def test_ends_in_finished(self):
        sm = StateMachine()
        sm.start("c1")
        for s in FORWARD_ORDER[1:]:
            sm.transition(s)
        self.assertTrue(sm.is_in_state(SystemState.FINISHED))
        self.assertFalse(sm.is_active())

    def test_each_transition_valid(self):
        sm = StateMachine()
        sm.start("c1")
        for i, target in enumerate(FORWARD_ORDER[1:], 1):
            ctx = sm.transition(target)
            self.assertEqual(ctx.state, target.value)
            self.assertEqual(ctx.previous_state, FORWARD_ORDER[i - 1].value)

    def test_event_published_on_change(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventTypes.STATE_CHANGED, lambda e: events.append(e))
        sm = StateMachine(event_bus=bus)
        sm.start("c1")
        sm.transition(SystemState.MARKET_READY)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].data["state"], SystemState.INITIALIZING.value)
        self.assertEqual(events[1].data["state"], SystemState.MARKET_READY.value)

    def test_event_finished_published(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventTypes.STATE_FINISHED, lambda e: events.append(e))
        sm = StateMachine(event_bus=bus)
        sm.start("c1")
        for s in FORWARD_ORDER[1:]:
            sm.transition(s)
        self.assertGreaterEqual(len(events), 1)


class TestStateMachineInvalidTransitions(unittest.TestCase):

    def test_cannot_skip_state(self):
        sm = StateMachine()
        sm.start("c1")
        with self.assertRaises(RuntimeError) as cm:
            sm.transition(SystemState.WORLD_READY)
        self.assertIn("Invalid transition", str(cm.exception))

    def test_cannot_go_backwards(self):
        sm = StateMachine()
        sm.start("c1")
        sm.transition(SystemState.MARKET_READY)
        with self.assertRaises(RuntimeError):
            sm.transition(SystemState.INITIALIZING)

    def test_cannot_transition_from_finished(self):
        sm = StateMachine()
        sm.start("c1")
        for s in FORWARD_ORDER[1:]:
            sm.transition(s)
        with self.assertRaises(RuntimeError):
            sm.transition(SystemState.INITIALIZING)

    def test_cannot_transition_from_cancelled(self):
        sm = StateMachine()
        sm.start("c1")
        for _ in range(MAX_RETRIES + 1):
            sm.set_error("fail")
            sm.transition(SystemState.RECOVERY)
            sm.transition(SystemState.RETRY)
        self.assertTrue(sm.is_in_state(SystemState.CANCELLED))
        with self.assertRaises(RuntimeError):
            sm.transition(SystemState.INITIALIZING)

    def test_cannot_transition_from_error_to_arbitrary(self):
        sm = StateMachine()
        sm.start("c1")
        sm.set_error("fail")
        with self.assertRaises(RuntimeError):
            sm.transition(SystemState.MARKET_READY)

    def test_cannot_transition_from_recovery_to_arbitrary(self):
        sm = StateMachine()
        sm.start("c1")
        sm.set_error("fail")
        sm.transition(SystemState.RECOVERY)
        with self.assertRaises(RuntimeError):
            sm.transition(SystemState.MARKET_READY)

    def test_transition_to_invalid_string_raises(self):
        sm = StateMachine()
        sm.start("c1")
        with self.assertRaises(ValueError):
            sm.transition_to("INVALID_STATE")


class TestStateMachineErrorRecovery(unittest.TestCase):

    def test_set_error_goes_to_error(self):
        sm = StateMachine()
        sm.start("c1")
        ctx = sm.set_error("connection lost")
        self.assertEqual(ctx.state, SystemState.ERROR.value)
        self.assertIn("connection lost", ctx.error_message)

    def test_error_publishes_event(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventTypes.STATE_ERROR, lambda e: events.append(e))
        sm = StateMachine(event_bus=bus)
        sm.start("c1")
        sm.set_error("fail")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].data["state"], SystemState.ERROR.value)

    def test_recovery_from_error(self):
        sm = StateMachine()
        sm.start("c1")
        sm.set_error("fail")
        ctx = sm.transition(SystemState.RECOVERY)
        self.assertEqual(ctx.state, SystemState.RECOVERY.value)

    def test_retry_after_recovery(self):
        sm = StateMachine()
        sm.start("c1")
        sm.set_error("fail")
        sm.transition(SystemState.RECOVERY)
        ctx = sm.transition(SystemState.RETRY)
        self.assertEqual(ctx.state, SystemState.RETRY.value)
        self.assertEqual(ctx.retry_count, 1)

    def test_retry_publishes_event(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventTypes.STATE_RETRY, lambda e: events.append(e))
        sm = StateMachine(event_bus=bus)
        sm.start("c1")
        sm.set_error("fail")
        sm.transition(SystemState.RECOVERY)
        sm.transition(SystemState.RETRY)
        self.assertGreaterEqual(len(events), 1)

    def test_cancelled_after_max_retries(self):
        sm = StateMachine()
        sm.start("c1")
        for i in range(MAX_RETRIES + 1):
            sm.set_error(f"fail_{i}")
            sm.transition(SystemState.RECOVERY)
            sm.transition(SystemState.RETRY)
        self.assertTrue(sm.is_in_state(SystemState.CANCELLED))

    def test_cancelled_publishes_event(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventTypes.STATE_CANCELLED, lambda e: events.append(e))
        sm = StateMachine(event_bus=bus)
        sm.start("c1")
        for _ in range(MAX_RETRIES + 1):
            sm.set_error("fail")
            sm.transition(SystemState.RECOVERY)
            sm.transition(SystemState.RETRY)
        self.assertGreaterEqual(len(events), 1)

    def test_recovery_returns_to_last_good_state(self):
        sm = StateMachine()
        sm.start("c1")
        sm.transition(SystemState.MARKET_READY)
        sm.transition(SystemState.WORLD_READY)
        sm.set_error("fail")
        sm.transition(SystemState.RECOVERY)
        ctx = sm.transition(SystemState.RETRY)
        self.assertEqual(ctx.next_state, SystemState.WORLD_READY.value)

    def test_retry_from_initial_error(self):
        sm = StateMachine()
        sm.start("c1")
        sm.set_error("fail")
        sm.transition(SystemState.RECOVERY)
        ctx = sm.transition(SystemState.RETRY)
        self.assertEqual(ctx.next_state, SystemState.INITIALIZING.value)

    def test_no_event_without_bus(self):
        sm = StateMachine()
        sm.start("c1")
        sm.set_error("fail")
        sm.transition(SystemState.RECOVERY)
        sm.transition(SystemState.RETRY)
        self.assertTrue(sm.is_in_state(SystemState.RETRY))


class TestStateMachineClear(unittest.TestCase):

    def test_clear_resets_context(self):
        sm = StateMachine()
        sm.start("c1")
        self.assertIsNotNone(sm.context)
        sm.clear()
        self.assertIsNone(sm.context)

    def test_clear_resets_history(self):
        sm = StateMachine()
        sm.start("c1")
        sm.transition(SystemState.MARKET_READY)
        self.assertEqual(len(sm.history), 2)
        sm.clear()
        self.assertEqual(len(sm.history), 0)

    def test_can_restart_after_clear(self):
        sm = StateMachine()
        sm.start("c1")
        sm.clear()
        ctx = sm.start("c2")
        self.assertEqual(ctx.cycle_id, "c2")

    def test_clear_allows_new_cycle(self):
        sm = StateMachine()
        sm.start("c1")
        for s in FORWARD_ORDER[1:]:
            sm.transition(s)
        sm.clear()
        ctx = sm.start("c2")
        self.assertTrue(sm.is_active())


class TestStateMachinePerformance(unittest.TestCase):

    def test_100_cycles(self):
        for _ in range(100):
            sm = StateMachine()
            sm.start(f"c")
            for s in FORWARD_ORDER[1:]:
                sm.transition(s)
            sm.clear()
        self.assertTrue(True)

    def test_1000_cycles(self):
        for _ in range(1000):
            sm = StateMachine()
            sm.start(f"c")
            for s in FORWARD_ORDER[1:]:
                sm.transition(s)
            sm.clear()
        self.assertTrue(True)

    def test_10000_serializations(self):
        ctx = StateContext(cycle_id="c1", state="INITIALIZING")
        for _ in range(10000):
            d = ctx.to_dict()
            StateContext.from_dict(d)
        self.assertTrue(True)


class TestStateMachineRobustness(unittest.TestCase):

    def test_double_start_creates_separate_cycle(self):
        sm = StateMachine()
        ctx1 = sm.start("c1")
        sm.clear()
        ctx2 = sm.start("c2")
        self.assertEqual(ctx2.cycle_id, "c2")
        self.assertNotEqual(ctx1.cycle_id, ctx2.cycle_id)

    def test_set_error_before_start_raises(self):
        sm = StateMachine()
        with self.assertRaises(RuntimeError):
            sm.set_error("fail")

    def test_error_message_in_state(self):
        sm = StateMachine()
        sm.start("c1")
        ctx = sm.set_error("timeout occurred")
        self.assertEqual(ctx.state, SystemState.ERROR.value)
        self.assertEqual(ctx.error_message, "timeout occurred")
        self.assertEqual(ctx.previous_state, SystemState.INITIALIZING.value)

    def test_history_contains_all_states(self):
        sm = StateMachine()
        sm.start("c1")
        sm.transition(SystemState.MARKET_READY)
        sm.transition(SystemState.WORLD_READY)
        self.assertEqual(len(sm.history), 3)
        self.assertEqual(sm.history[0].state, SystemState.INITIALIZING.value)
        self.assertEqual(sm.history[1].state, SystemState.MARKET_READY.value)
        self.assertEqual(sm.history[2].state, SystemState.WORLD_READY.value)

    def test_pipeline_status_shows_all_states(self):
        sm = StateMachine()
        sm.start("c1")
        sm.transition(SystemState.MARKET_READY)
        sm.transition(SystemState.WORLD_READY)
        status = sm.get_pipeline_status()
        self.assertEqual(status, [
            SystemState.INITIALIZING.value,
            SystemState.MARKET_READY.value,
            SystemState.WORLD_READY.value,
        ])

    def test_recovery_no_error_message(self):
        sm = StateMachine()
        sm.start("c1")
        sm.set_error("disk full")
        ctx = sm.transition(SystemState.RECOVERY)
        self.assertEqual(ctx.error_message, "")
        self.assertEqual(ctx.state, SystemState.RECOVERY.value)

    def test_clear_then_start_new_cycle(self):
        sm = StateMachine()
        sm.start("old")
        sm.transition(SystemState.MARKET_READY)
        sm.clear()
        sm.start("new")
        self.assertEqual(sm.context.cycle_id, "new")

    def test_is_active_false_before_start(self):
        sm = StateMachine()
        self.assertFalse(sm.is_active())

    def test_is_active_false_after_finished(self):
        sm = StateMachine()
        sm.start("c1")
        for s in FORWARD_ORDER[1:]:
            sm.transition(s)
        self.assertFalse(sm.is_active())


if __name__ == '__main__':
    unittest.main()
