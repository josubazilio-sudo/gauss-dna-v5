import time
import json
import pytest
from datetime import datetime, timezone
from dataclasses import FrozenInstanceError

from ENGINE.memory.working_memory_types import WorkingMemory
from ENGINE.memory.working_memory import WorkingMemoryManager
from ENGINE.decision.decision_context import WorkingMemoryContext, DecisionContextBuilder
from ENGINE.decision.decision_trace import (
    DecisionTrace, DecisionTraceRecorder, StepRecord,
)
from ENGINE.council.council_types import CouncilVerdict
from ENGINE.council.evidence_types import EvidenceGraph
from ENGINE.council.health_types import HealthScore, HealthStatus
from ENGINE.council.weight_types import WeightDistribution, SkillWeight
from ENGINE.meta.meta_types import MetaVerdict
from ENGINE.policy.policy_types import PolicyVerdict
from ENGINE.market.market_types import MarketContext, TechnicalIndicators, TrendDirection, MarketRegime
from ENGINE.skills.skill_opinion import SkillOpinion
from ENGINE.world.world_types import WorldModel, MarketState, MarketQuality
from CORE.events.event_bus import EventBus
from CORE.events.events import EventTypes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _market_context() -> MarketContext:
    ind = TechnicalIndicators(atr_percent=0.5, rsi=55.0, rvol=1.2, adx=25.0)
    return MarketContext(
        pair="BTCUSDT", timestamp=datetime.now(timezone.utc), price=50000.0,
        indicators=ind, trend=TrendDirection.BULLISH, trend_strength=0.7,
        regime=MarketRegime.TRENDING_UP, regime_confidence=0.8,
    )


def _world_model() -> WorldModel:
    return WorldModel(
        state=MarketState.STRONG_TREND_UP, quality=MarketQuality.GOOD,
        confidence=0.80, health=0.90,
    )


def _skill_opinions() -> dict:
    return {
        "smc": SkillOpinion(
            skill_name="smc", confidence=0.8, risk=0.2, probability=0.7,
            evidence=["forte tendencia"], observations="ok", success=True,
        ),
        "volume": SkillOpinion(
            skill_name="volume", confidence=0.7, risk=0.3, probability=0.6,
            evidence=["volume elevado"], observations="ok", success=True,
        ),
    }


def _evidence_graph() -> EvidenceGraph:
    return EvidenceGraph(
        nodes=(), clusters=(), contradictions=(),
        confidence=0.8, quality=0.8, consistency=0.9,
        graph_hash="g1", num_skills=2, num_duplicates_removed=0,
    )


def _health_scores() -> dict:
    return {
        "smc": HealthScore(
            skill_name="smc", score=0.9, availability=0.95, reliability=0.9,
            precision=0.85, latency_score=0.9, stability=0.9,
            timeout_penalty=0.0, error_penalty=0.0,
            status=HealthStatus.EXCELLENT, recommendations=[],
        ),
    }


def _weight_distribution() -> WeightDistribution:
    sw = SkillWeight(
        skill_name="smc", final_weight=0.5, base_weight=0.5,
        regime_multiplier=1.0, health_multiplier=1.0,
        performance_multiplier=1.0, confidence_multiplier=1.0,
        specialization_multiplier=1.0, normalization_factor=1.0,
        reasons=[],
    )
    return WeightDistribution(
        weights={"smc": sw}, total_weight=1.0, normalized=True,
        distribution_hash="wd1",
    )


def _council_verdict() -> CouncilVerdict:
    v = CouncilVerdict(
        consensus_score=0.8, global_confidence=0.8, global_risk=0.2,
        global_probability=0.7, evidence_quality=0.8, evidence_consistency=0.8,
        agreement_level=0.8, disagreement_level=0.1, participating_skills=["smc"],
        conflicting_skills=[], supporting_clusters=[], conflicting_clusters=[],
        strongest_evidence=[], weakest_evidence=[], summary="ok", council_hash="",
    )
    return CouncilVerdict(
        consensus_score=v.consensus_score,
        global_confidence=v.global_confidence,
        global_risk=v.global_risk,
        global_probability=v.global_probability,
        evidence_quality=v.evidence_quality,
        evidence_consistency=v.evidence_consistency,
        agreement_level=v.agreement_level,
        disagreement_level=v.disagreement_level,
        participating_skills=v.participating_skills,
        conflicting_skills=v.conflicting_skills,
        supporting_clusters=v.supporting_clusters,
        conflicting_clusters=v.conflicting_clusters,
        strongest_evidence=v.strongest_evidence,
        weakest_evidence=v.weakest_evidence,
        summary=v.summary,
        council_hash=CouncilVerdict.compute_hash(v),
    )


def _meta_verdict() -> MetaVerdict:
    return MetaVerdict(
        proceed=True, decision="PROCEED", confidence=0.8,
        reasoning_score=0.7, information_quality=0.8, uncertainty=0.2,
        detected_conflicts=[], blocking_reasons=[], recommendations=[],
        meta_hash="mv1",
    )


def _policy_verdict() -> PolicyVerdict:
    return PolicyVerdict(
        allowed=True, decision="ALLOWED", compliance_score=1.0,
        violated_rules=[], warnings=[], recommendations=[], policy_hash="pv1",
    )


# ===================================================================
# WORKING MEMORY
# ===================================================================

class TestWorkingMemory:

    def test_create(self):
        wm = WorkingMemory(cycle_id="c1")
        assert wm.cycle_id == "c1"
        assert wm.market_context is None
        assert wm.metadata == {}

    def test_immutable(self):
        wm = WorkingMemory(cycle_id="c1")
        with pytest.raises(FrozenInstanceError):
            wm.cycle_id = "c2"

    def test_with_all_fields(self):
        mc = _market_context()
        wm = _world_model()
        ops = list(_skill_opinions().values())
        eg = _evidence_graph()
        hs = _health_scores()
        wd = _weight_distribution()
        cv = _council_verdict()
        mv = _meta_verdict()
        pv = _policy_verdict()

        wm = WorkingMemory(
            cycle_id="c1", market_context=mc, world_model=wm,
            skill_opinions=ops, evidence_graph=eg, health_scores=hs,
            weight_distribution=wd, council_verdict=cv,
            meta_verdict=mv, policy_verdict=pv,
            metadata={"source": "test"},
        )
        assert wm.cycle_id == "c1"
        assert wm.market_context.pair == "BTCUSDT"
        assert wm.world_model.state == MarketState.STRONG_TREND_UP
        assert len(wm.skill_opinions) == 2
        assert wm.evidence_graph.graph_hash == "g1"
        assert wm.health_scores["smc"].score == 0.9
        assert wm.weight_distribution.distribution_hash == "wd1"
        assert wm.council_verdict.consensus_score == 0.8
        assert wm.meta_verdict.proceed is True
        assert wm.policy_verdict.allowed is True
        assert wm.metadata["source"] == "test"

    def test_hash_deterministic(self):
        now = datetime.now(timezone.utc)
        wm1 = WorkingMemory(cycle_id="c1", timestamp=now)
        wm2 = WorkingMemory(cycle_id="c1", timestamp=now)
        assert WorkingMemory.compute_hash(wm1) == WorkingMemory.compute_hash(wm2)

    def test_hash_changes(self):
        wm1 = WorkingMemory(cycle_id="c1")
        wm2 = WorkingMemory(cycle_id="c2")
        assert WorkingMemory.compute_hash(wm1) != WorkingMemory.compute_hash(wm2)

    def test_to_dict(self):
        wm = WorkingMemory(cycle_id="c1", metadata={"env": "test"})
        d = wm.to_dict()
        assert d["cycle_id"] == "c1"
        assert d["metadata"]["env"] == "test"
        assert "timestamp" in d

    def test_to_json(self):
        wm = WorkingMemory(cycle_id="c1")
        j = wm.to_json()
        d = json.loads(j)
        assert d["cycle_id"] == "c1"


# ===================================================================
# WORKING MEMORY MANAGER
# ===================================================================

class TestWorkingMemoryManager:

    def test_create_empty(self):
        mgr = WorkingMemoryManager()
        wm = mgr.create(cycle_id="c1")
        assert wm.cycle_id == "c1"
        assert mgr.current.cycle_id == "c1"

    def test_create_with_fields(self):
        mgr = WorkingMemoryManager()
        wm = mgr.create(
            cycle_id="c2",
            market_context=_market_context(),
            world_model=_world_model(),
            skill_opinions=_skill_opinions(),
            evidence_graph=_evidence_graph(),
            health_scores=_health_scores(),
            weight_distribution=_weight_distribution(),
            council_verdict=_council_verdict(),
            meta_verdict=_meta_verdict(),
            policy_verdict=_policy_verdict(),
            metadata={"test": True},
        )
        assert wm.cycle_id == "c2"
        assert wm.world_model is not None
        assert len(wm.skill_opinions) == 2

    def test_auto_cycle_id(self):
        mgr = WorkingMemoryManager()
        wm = mgr.create()
        assert len(wm.cycle_id) > 0
        assert mgr.current.cycle_id == wm.cycle_id

    def test_clear(self):
        mgr = WorkingMemoryManager()
        mgr.create(cycle_id="c1")
        assert mgr.current is not None
        mgr.clear()
        assert mgr.current is None

    def test_event_published(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventTypes.WORKING_MEMORY_CREATED, lambda e: received.append(e))
        mgr = WorkingMemoryManager(bus)
        mgr.create(cycle_id="c1")
        assert len(received) == 1
        assert received[0].type == EventTypes.WORKING_MEMORY_CREATED

    def test_event_not_published_without_bus(self):
        mgr = WorkingMemoryManager()
        mgr.create(cycle_id="c1")
        # no exception

    def test_from_dict_roundtrip(self):
        mgr = WorkingMemoryManager()
        wm = mgr.create(
            cycle_id="c3",
            market_context=_market_context(),
            world_model=_world_model(),
            metadata={"src": "roundtrip"},
        )
        d = wm.to_dict()
        wm2 = WorkingMemoryManager.from_dict(d)
        assert wm2.cycle_id == wm.cycle_id
        assert wm2.metadata["src"] == "roundtrip"

    def test_from_json_roundtrip(self):
        mgr = WorkingMemoryManager()
        wm = mgr.create(cycle_id="c4")
        j = wm.to_json()
        wm2 = WorkingMemoryManager.from_json(j)
        assert wm2.cycle_id == "c4"


# ===================================================================
# DECISION CONTEXT
# ===================================================================

class TestDecisionContext:

    def test_from_memory(self):
        wm = WorkingMemory(cycle_id="c1")
        ctx = WorkingMemoryContext.from_memory(wm)
        assert ctx.cycle_id == "c1"
        assert ctx.memory.cycle_id == "c1"
        assert len(ctx.context_hash) > 0

    def test_immutable(self):
        ctx = WorkingMemoryContext(cycle_id="c1")
        with pytest.raises(FrozenInstanceError):
            ctx.cycle_id = "c2"

    def test_hash_deterministic(self):
        wm = WorkingMemory(cycle_id="c1")
        ctx1 = WorkingMemoryContext.from_memory(wm)
        ctx2 = WorkingMemoryContext.from_memory(wm)
        assert ctx1.context_hash == ctx2.context_hash

    def test_hash_changes(self):
        wm1 = WorkingMemory(cycle_id="c1")
        wm2 = WorkingMemory(cycle_id="c2")
        ctx1 = WorkingMemoryContext.from_memory(wm1)
        ctx2 = WorkingMemoryContext.from_memory(wm2)
        assert ctx1.context_hash != ctx2.context_hash

    def test_to_dict(self):
        wm = WorkingMemory(cycle_id="c1")
        ctx = WorkingMemoryContext.from_memory(wm)
        d = ctx.to_dict()
        assert d["cycle_id"] == "c1"
        assert d["memory"]["cycle_id"] == "c1"
        assert "context_hash" in d

    def test_to_json(self):
        wm = WorkingMemory(cycle_id="c1")
        ctx = WorkingMemoryContext.from_memory(wm)
        j = ctx.to_json()
        d = json.loads(j)
        assert d["cycle_id"] == "c1"

    def test_from_dict_roundtrip(self):
        wm = WorkingMemory(cycle_id="c1")
        ctx = WorkingMemoryContext.from_memory(wm)
        d = ctx.to_dict()
        ctx2 = WorkingMemoryContext.from_dict(d)
        assert ctx2.cycle_id == ctx.cycle_id
        assert ctx2.memory.cycle_id == "c1"

    def test_from_json_roundtrip(self):
        wm = WorkingMemory(cycle_id="c1")
        ctx = WorkingMemoryContext.from_memory(wm)
        j = ctx.to_json()
        ctx2 = WorkingMemoryContext.from_json(j)
        assert ctx2.cycle_id == "c1"

    def test_to_dict_with_full_memory(self):
        mc = _market_context()
        wm_obj = _world_model()
        wm = WorkingMemory(
            cycle_id="c1", market_context=mc, world_model=wm_obj,
        )
        ctx = WorkingMemoryContext.from_memory(wm)
        d = ctx.to_dict()
        assert d["memory"]["market_context"]["pair"] == "BTCUSDT"
        assert d["memory"]["world_model"]["state"] == "strong_trend_up"


class TestDecisionContextBuilder:

    def test_build(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventTypes.DECISION_CONTEXT_CREATED, lambda e: received.append(e))
        builder = DecisionContextBuilder(bus)
        wm = WorkingMemory(cycle_id="c1")
        ctx = builder.build(wm)
        assert ctx.cycle_id == "c1"
        assert len(received) == 1
        assert received[0].type == EventTypes.DECISION_CONTEXT_CREATED

    def test_build_without_bus(self):
        builder = DecisionContextBuilder()
        wm = WorkingMemory(cycle_id="c1")
        ctx = builder.build(wm)
        assert ctx.cycle_id == "c1"


# ===================================================================
# DECISION TRACE
# ===================================================================

class TestStepRecord:

    def test_create(self):
        now = datetime.now(timezone.utc)
        s = StepRecord(
            step_name="world_model", timestamp=now, duration_ms=10.5,
            result="ok", step_hash="h1", module_version="10.0.0",
            observations="model built",
        )
        assert s.step_name == "world_model"
        assert s.duration_ms == 10.5

    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        s = StepRecord(
            step_name="skills", timestamp=now, duration_ms=5.0,
            result="ok", step_hash="h2", module_version="10.0.0",
            observations="",
        )
        d = s.to_dict()
        assert d["step_name"] == "skills"


class TestDecisionTrace:

    def test_create_empty(self):
        t = DecisionTrace(cycle_id="c1")
        assert t.cycle_id == "c1"
        assert t.steps == []

    def test_immutable(self):
        t = DecisionTrace(cycle_id="c1")
        with pytest.raises(FrozenInstanceError):
            t.cycle_id = "c2"

    def test_hash_deterministic(self):
        t1 = DecisionTrace(cycle_id="c1")
        t2 = DecisionTrace(cycle_id="c1")
        assert DecisionTrace.compute_hash(t1) == DecisionTrace.compute_hash(t2)

    def test_hash_changes_with_steps(self):
        now = datetime.now(timezone.utc)
        s = StepRecord(
            step_name="skills", timestamp=now, duration_ms=5.0,
            result="ok", step_hash="h1", module_version="10.0.0",
            observations="",
        )
        t1 = DecisionTrace(cycle_id="c1", steps=[s])
        t2 = DecisionTrace(cycle_id="c1", steps=[])
        assert DecisionTrace.compute_hash(t1) != DecisionTrace.compute_hash(t2)

    def test_to_dict(self):
        t = DecisionTrace(cycle_id="c1")
        d = t.to_dict()
        assert d["cycle_id"] == "c1"
        assert d["steps"] == []

    def test_to_json(self):
        t = DecisionTrace(cycle_id="c1")
        j = t.to_json()
        d = json.loads(j)
        assert d["cycle_id"] == "c1"

    def test_from_dict_roundtrip(self):
        now = datetime.now(timezone.utc)
        s = StepRecord(
            step_name="test", timestamp=now, duration_ms=1.0,
            result="pass", step_hash="h3", module_version="1.0",
            observations="ok",
        )
        t = DecisionTrace(cycle_id="c1", steps=[s])
        d = t.to_dict()
        t2 = DecisionTrace.from_dict(d)
        assert t2.cycle_id == "c1"
        assert len(t2.steps) == 1
        assert t2.steps[0].step_name == "test"

    def test_from_json_roundtrip(self):
        t = DecisionTrace(cycle_id="c1")
        j = t.to_json()
        t2 = DecisionTrace.from_json(j)
        assert t2.cycle_id == "c1"


class TestDecisionTraceRecorder:

    def test_start_cycle(self):
        rec = DecisionTraceRecorder()
        t = rec.start_cycle("c1")
        assert t.cycle_id == "c1"
        assert rec.current.cycle_id == "c1"

    def test_record_step(self):
        rec = DecisionTraceRecorder()
        rec.start_cycle("c1")
        t = rec.record_step("world_model", "ok", step_hash="h1")
        assert len(t.steps) == 1
        assert t.steps[0].step_name == "world_model"
        assert t.steps[0].result == "ok"

    def test_pipeline_order(self):
        rec = DecisionTraceRecorder()
        rec.start_cycle("c1")
        for step in ["world_model", "skills", "evidence_graph", "consensus", "meta"]:
            rec.record_step(step, "ok")
        assert len(rec.current.steps) == 5
        names = [s.step_name for s in rec.current.steps]
        assert names == ["world_model", "skills", "evidence_graph", "consensus", "meta"]

    def test_get_pipeline_status(self):
        rec = DecisionTraceRecorder()
        assert rec.get_pipeline_status() == []
        rec.start_cycle("c1")
        rec.record_step("world_model", "ok")
        assert rec.get_pipeline_status() == ["world_model"]

    def test_hash_changes_after_step(self):
        rec = DecisionTraceRecorder()
        t1 = rec.start_cycle("c1")
        h1 = t1.trace_hash
        t2 = rec.record_step("world_model", "ok")
        h2 = t2.trace_hash
        assert h1 != h2

    def test_clear(self):
        rec = DecisionTraceRecorder()
        rec.start_cycle("c1")
        assert rec.current is not None
        rec.clear()
        assert rec.current is None

    def test_record_without_start_raises(self):
        rec = DecisionTraceRecorder()
        with pytest.raises(RuntimeError):
            rec.record_step("test", "ok")

    def test_event_published(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventTypes.DECISION_TRACE_CREATED, lambda e: received.append(e))
        rec = DecisionTraceRecorder(bus)
        rec.start_cycle("c1")
        assert len(received) >= 1
        assert received[0].type == EventTypes.DECISION_TRACE_CREATED

    def test_full_pipeline_recording(self):
        rec = DecisionTraceRecorder()
        rec.start_cycle("c1")
        steps = DecisionTraceRecorder.PIPELINE_ORDER
        for s in steps:
            rec.record_step(s, "ok", module_version="10.0.0")
        assert len(rec.current.steps) == len(steps)
        names = [s.step_name for s in rec.current.steps]
        assert names == steps
        assert len(rec.current.trace_hash) > 0

    def test_duration_populated(self):
        rec = DecisionTraceRecorder()
        rec.start_cycle("c1")
        t = rec.record_step("test", "ok")
        assert t.steps[0].duration_ms >= 0


# ===================================================================
# INTEGRATION
# ===================================================================

class TestIntegration:

    def test_working_memory_with_all_layers(self):
        mc = _market_context()
        wm = _world_model()
        ops = _skill_opinions()
        eg = _evidence_graph()
        hs = _health_scores()
        wd = _weight_distribution()
        cv = _council_verdict()
        mv = _meta_verdict()
        pv = _policy_verdict()

        mgr = WorkingMemoryManager()
        memory = mgr.create(
            cycle_id="integ1",
            market_context=mc, world_model=wm,
            skill_opinions=ops, evidence_graph=eg,
            health_scores=hs, weight_distribution=wd,
            council_verdict=cv, meta_verdict=mv,
            policy_verdict=pv,
        )
        assert memory is not None

        builder = DecisionContextBuilder()
        ctx = builder.build(memory)
        assert ctx.cycle_id == "integ1"
        assert ctx.memory.world_model.state == MarketState.STRONG_TREND_UP
        assert ctx.memory.council_verdict.consensus_score == 0.8
        assert ctx.memory.meta_verdict.proceed is True
        assert ctx.memory.policy_verdict.allowed is True

    def test_decision_trace_with_layers(self):
        rec = DecisionTraceRecorder()
        rec.start_cycle("integ2")
        rec.record_step("world_model", "ok", module_version="10.0.0")
        rec.record_step("skills", "2 opinioes", module_version="10.0.0")
        rec.record_step("evidence_graph", "3 clusters", module_version="10.0.0")
        rec.record_step("health_score", "0.9 medio", module_version="10.0.0")
        rec.record_step("dynamic_weights", "normalizado", module_version="10.0.0")
        rec.record_step("consensus", "score 0.8", module_version="10.0.0")
        rec.record_step("meta", "PROCEED", module_version="10.0.0")
        rec.record_step("policy", "ALLOWED", module_version="10.0.0")
        assert len(rec.current.steps) == 8
        assert rec.current.trace_hash is not None

    def test_full_cycle_consistency(self):
        bus = EventBus()
        wm_events = []
        dc_events = []
        dt_events = []
        bus.subscribe(EventTypes.WORKING_MEMORY_CREATED, lambda e: wm_events.append(e))
        bus.subscribe(EventTypes.DECISION_CONTEXT_CREATED, lambda e: dc_events.append(e))
        bus.subscribe(EventTypes.DECISION_TRACE_CREATED, lambda e: dt_events.append(e))

        mgr = WorkingMemoryManager(bus)
        memory = mgr.create(cycle_id="cycle1", metadata={"full": True})

        builder = DecisionContextBuilder(bus)
        ctx = builder.build(memory)

        rec = DecisionTraceRecorder(bus)
        rec.start_cycle("cycle1")
        rec.record_step("world_model", "ok")

        assert len(wm_events) == 1
        assert len(dc_events) == 1
        assert len(dt_events) >= 1
        assert ctx.cycle_id == "cycle1"

    def test_events_not_published_without_bus(self):
        mgr = WorkingMemoryManager()
        memory = mgr.create(cycle_id="c1")
        builder = DecisionContextBuilder()
        ctx = builder.build(memory)
        rec = DecisionTraceRecorder()
        rec.start_cycle("c1")
        assert ctx.cycle_id == "c1"


# ===================================================================
# PERFORMANCE
# ===================================================================

class TestPerformance:

    def test_100_cycles(self):
        mgr = WorkingMemoryManager()
        rec = DecisionTraceRecorder()
        start = time.perf_counter()
        for i in range(100):
            wm = mgr.create(cycle_id=f"p{i}")
            _ = WorkingMemoryContext.from_memory(wm)
            rec.start_cycle(f"p{i}")
            rec.record_step("test", "ok")
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0

    def test_1000_cycles(self):
        mgr = WorkingMemoryManager()
        rec = DecisionTraceRecorder()
        start = time.perf_counter()
        for i in range(1000):
            wm = mgr.create(cycle_id=f"p{i}")
            ctx = WorkingMemoryContext.from_memory(wm)
            rec.start_cycle(f"p{i}")
            rec.record_step("test", "ok")
            _ = ctx.to_dict()
        elapsed = time.perf_counter() - start
        assert elapsed < 30.0

    def test_10000_serializations(self):
        wm = WorkingMemory(
            cycle_id="c1",
            market_context=_market_context(),
            world_model=_world_model(),
        )
        start = time.perf_counter()
        for _ in range(10000):
            _ = wm.to_dict()
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0


# ===================================================================
# ROBUSTEZ
# ===================================================================

class TestRobustness:

    def test_empty_memory_no_error(self):
        wm = WorkingMemory(cycle_id="c1")
        assert wm.cycle_id == "c1"

    def test_decision_context_no_memory(self):
        ctx = WorkingMemoryContext(cycle_id="c1")
        assert ctx.context_hash == ""
        assert ctx.memory is None

    def test_decision_trace_no_steps(self):
        t = DecisionTrace(cycle_id="c1")
        assert t.steps == []

    def test_manager_create_twice(self):
        mgr = WorkingMemoryManager()
        mgr.create(cycle_id="c1")
        mgr.create(cycle_id="c2")
        assert mgr.current.cycle_id == "c2"

    def test_recorder_clear_and_restart(self):
        rec = DecisionTraceRecorder()
        rec.start_cycle("c1")
        rec.record_step("test", "ok")
        rec.clear()
        rec.start_cycle("c2")
        assert rec.current.cycle_id == "c2"
        assert len(rec.current.steps) == 0

    def test_no_exceptions(self):
        try:
            wm = WorkingMemory(cycle_id="c1")
            _ = wm.to_dict()
            _ = wm.to_json()
            _ = WorkingMemory.compute_hash(wm)
        except Exception:
            pytest.fail("Unexpected exception")

    def test_serialization_with_none_fields(self):
        wm = WorkingMemory(cycle_id="c1", market_context=None, world_model=None)
        d = wm.to_dict()
        assert d["market_context"] is None
        assert d["world_model"] is None


# ===================================================================
# EVENT TYPES EXISTENCE
# ===================================================================

class TestEventTypes:

    def test_events_registered(self):
        assert EventTypes.WORKING_MEMORY_CREATED == "working_memory.created"
        assert EventTypes.DECISION_CONTEXT_CREATED == "decision.context.created"
        assert EventTypes.DECISION_TRACE_CREATED == "decision.trace.created"
