import time
import json
import pytest
from datetime import datetime, timezone
from dataclasses import FrozenInstanceError

from ENGINE.policy.policy_types import PolicyVerdict
from ENGINE.policy.policy_engine import PolicyEngine
from ENGINE.policy.policy_config import (
    MAX_POSITIONS, MAX_DAILY_OPERATIONS, MAX_DAILY_RISK,
    MAX_DAILY_DRAWDOWN, MAX_WEEKLY_DRAWDOWN, MAX_MONTHLY_DRAWDOWN,
    MAX_EXPOSURE_PER_ASSET, MAX_EXPOSURE_PER_SECTOR,
    MAX_EXPOSURE_PER_DIRECTION, MAX_CORRELATION, MAX_LEVERAGE,
    TRADING_HOURS_START, TRADING_HOURS_END,
)
from ENGINE.meta.meta_types import MetaVerdict
from ENGINE.council.council_types import CouncilVerdict
from ENGINE.world.world_types import WorldModel, MarketState, MarketQuality
from CORE.events.event_bus import EventBus
from CORE.events.events import EventTypes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _meta_verdict(proceed: bool = True) -> MetaVerdict:
    return MetaVerdict(
        proceed=proceed, decision="PROCEED" if proceed else "HOLD",
        confidence=0.8, reasoning_score=0.7, information_quality=0.8,
        uncertainty=0.2, detected_conflicts=[], blocking_reasons=[],
        recommendations=[], meta_hash="",
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


def _world_model() -> WorldModel:
    return WorldModel(
        state=MarketState.STRONG_TREND_UP,
        quality=MarketQuality.GOOD,
        confidence=0.80, health=0.90,
    )


def _good_context(**overrides) -> dict:
    ctx = dict(
        open_positions=[],
        daily_risk_used=100.0,
        daily_drawdown=50.0,
        weekly_drawdown=100.0,
        monthly_drawdown=200.0,
        exposure_by_asset={},
        exposure_by_sector={},
        exposure_long=0.2,
        exposure_short=0.1,
        avg_correlation=0.3,
        current_leverage=1.0,
        trading_hour=14,
        circuit_breaker_active=False,
        high_volatility=False,
        macro_event_block=False,
        daily_operations=2,
    )
    ctx.update(overrides)
    return ctx


# ===================================================================
# CONTRATO
# ===================================================================

class TestPolicyVerdictTypes:

    def test_immutable(self):
        v = PolicyVerdict(
            allowed=True, decision="ALLOWED", compliance_score=1.0,
            violated_rules=[], warnings=[], recommendations=[], policy_hash="abc",
        )
        with pytest.raises(FrozenInstanceError):
            v.allowed = False

    def test_to_dict(self):
        v = PolicyVerdict(
            allowed=True, decision="ALLOWED", compliance_score=0.85,
            violated_rules=[], warnings=["cuidado"], recommendations=[],
            policy_hash="h1",
        )
        d = v.to_dict()
        assert d["allowed"] is True
        assert d["compliance_score"] == 0.85
        assert "created_at" in d

    def test_to_json(self):
        v = PolicyVerdict(
            allowed=False, decision="BLOCKED", compliance_score=0.4,
            violated_rules=["risco"], warnings=[], recommendations=["reduzir"],
            policy_hash="h2",
        )
        j = v.to_json()
        d = json.loads(j)
        assert d["decision"] == "BLOCKED"

    def test_from_dict_roundtrip(self):
        v = PolicyVerdict(
            allowed=True, decision="ALLOWED", compliance_score=0.9,
            violated_rules=[], warnings=["monitorar"], recommendations=[],
            policy_hash="h3",
        )
        d = v.to_dict()
        v2 = PolicyVerdict.from_dict(d)
        assert v2.allowed == v.allowed
        assert v2.compliance_score == v.compliance_score
        assert v2.warnings == v.warnings

    def test_from_json_roundtrip(self):
        v = PolicyVerdict(
            allowed=False, decision="BLOCKED", compliance_score=0.3,
            violated_rules=["drawdown"], warnings=[], recommendations=["aguardar"],
            policy_hash="h4",
        )
        j = v.to_json()
        v2 = PolicyVerdict.from_json(j)
        assert v2.decision == "BLOCKED"
        assert v2.violated_rules == ["drawdown"]

    def test_hash_deterministic(self):
        v = PolicyVerdict(
            allowed=True, decision="ALLOWED", compliance_score=1.0,
            violated_rules=[], warnings=[], recommendations=[], policy_hash="",
        )
        h1 = PolicyVerdict.compute_hash(v)
        h2 = PolicyVerdict.compute_hash(v)
        assert h1 == h2

    def test_hash_changes(self):
        v1 = PolicyVerdict(
            allowed=True, decision="ALLOWED", compliance_score=1.0,
            violated_rules=[], warnings=[], recommendations=[], policy_hash="",
        )
        v2 = PolicyVerdict(
            allowed=False, decision="BLOCKED", compliance_score=1.0,
            violated_rules=[], warnings=[], recommendations=[], policy_hash="",
        )
        assert PolicyVerdict.compute_hash(v1) != PolicyVerdict.compute_hash(v2)


# ===================================================================
# REGRAS
# ===================================================================

class TestRules:

    def test_allowed_when_no_violations(self):
        engine = PolicyEngine()
        v = engine.evaluate(
            _meta_verdict(), _world_model(), _council_verdict(), _good_context(),
        )
        assert v.allowed is True
        assert v.decision == "ALLOWED"
        assert v.compliance_score > 0.8

    def test_max_positions_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(open_positions=[{"s": "a"}, {"s": "b"}, {"s": "c"},
                                             {"s": "d"}, {"s": "e"}])
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("posicoes" in r for r in v.violated_rules)

    def test_daily_operations_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(daily_operations=MAX_DAILY_OPERATIONS)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("diario" in r for r in v.violated_rules)

    def test_daily_risk_exceeded(self):
        engine = PolicyEngine()
        ctx = _good_context(daily_risk_used=MAX_DAILY_RISK + 100)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("Risco" in r for r in v.violated_rules)

    def test_daily_drawdown_exceeded(self):
        engine = PolicyEngine()
        ctx = _good_context(daily_drawdown=MAX_DAILY_DRAWDOWN + 50)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("Drawdown diario" in r for r in v.violated_rules)

    def test_weekly_drawdown_exceeded(self):
        engine = PolicyEngine()
        ctx = _good_context(weekly_drawdown=MAX_WEEKLY_DRAWDOWN + 100)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("Drawdown semanal" in r for r in v.violated_rules)

    def test_monthly_drawdown_exceeded(self):
        engine = PolicyEngine()
        ctx = _good_context(monthly_drawdown=MAX_MONTHLY_DRAWDOWN + 200)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("Drawdown mensal" in r for r in v.violated_rules)

    def test_exposure_per_asset_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(exposure_by_asset={"BTC": MAX_EXPOSURE_PER_ASSET + 0.1})
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("Exposicao" in r for r in v.violated_rules)

    def test_exposure_per_sector_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(exposure_by_sector={"DeFi": MAX_EXPOSURE_PER_SECTOR + 0.1})
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("Exposicao" in r for r in v.violated_rules)

    def test_exposure_long_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(exposure_long=MAX_EXPOSURE_PER_DIRECTION + 0.1)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("LONG" in r for r in v.violated_rules)

    def test_exposure_short_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(exposure_short=MAX_EXPOSURE_PER_DIRECTION + 0.1)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("SHORT" in r for r in v.violated_rules)

    def test_correlation_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(avg_correlation=MAX_CORRELATION + 0.1)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("Correlacao" in r for r in v.violated_rules)

    def test_leverage_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(current_leverage=MAX_LEVERAGE + 1)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("alavancagem" in r for r in v.violated_rules)

    def test_trading_hours_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(trading_hour=TRADING_HOURS_START - 1)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("Horario" in r for r in v.violated_rules)

    def test_trading_hours_end_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(trading_hour=TRADING_HOURS_END + 1)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("Horario" in r for r in v.violated_rules)

    def test_trading_hours_allowed(self):
        engine = PolicyEngine()
        ctx = _good_context(trading_hour=TRADING_HOURS_START + 2)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is True

    def test_circuit_breaker_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(circuit_breaker_active=True)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("Circuit Breaker" in r for r in v.violated_rules)

    def test_high_volatility_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(high_volatility=True)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("volatilidade" in r for r in v.violated_rules)

    def test_macro_event_blocked(self):
        engine = PolicyEngine()
        ctx = _good_context(macro_event_block=True)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert any("macro" in r for r in v.violated_rules)

    def test_multiple_violations(self):
        engine = PolicyEngine()
        ctx = _good_context(
            open_positions=[{"s": "a"}, {"s": "b"}, {"s": "c"},
                            {"s": "d"}, {"s": "e"}],
            daily_risk_used=MAX_DAILY_RISK + 100,
            circuit_breaker_active=True,
        )
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.allowed is False
        assert len(v.violated_rules) >= 3
        assert v.compliance_score < 0.7


# ===================================================================
# INTEGRACAO
# ===================================================================

class TestIntegration:

    def test_with_meta_verdict(self):
        engine = PolicyEngine()
        v = engine.evaluate(
            _meta_verdict(), _world_model(), _council_verdict(), _good_context(),
        )
        assert v.allowed is True

    def test_with_meta_hold(self):
        engine = PolicyEngine()
        v = engine.evaluate(
            _meta_verdict(proceed=False), _world_model(), _council_verdict(),
            _good_context(),
        )
        assert v.allowed is True

    def test_with_world_model(self):
        engine = PolicyEngine()
        wm = WorldModel(state=MarketState.UNCERTAIN, quality=MarketQuality.HOSTILE,
                        confidence=0.1, health=0.3)
        v = engine.evaluate(_meta_verdict(), wm, _council_verdict(), _good_context())
        assert v.allowed is True

    def test_without_context(self):
        engine = PolicyEngine()
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), None)
        assert isinstance(v, PolicyVerdict)
        assert v.decision in ("ALLOWED", "BLOCKED")
        assert 0.0 <= v.compliance_score <= 1.0

    def test_event_approved_published(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventTypes.POLICY_APPROVED, lambda e: received.append(e))
        engine = PolicyEngine(bus)
        engine.evaluate(
            _meta_verdict(), _world_model(), _council_verdict(), _good_context(),
        )
        assert len(received) == 1
        assert received[0].type == EventTypes.POLICY_APPROVED

    def test_event_blocked_published(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventTypes.POLICY_BLOCKED, lambda e: received.append(e))
        engine = PolicyEngine(bus)
        ctx = _good_context(circuit_breaker_active=True)
        engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert len(received) == 1
        assert received[0].type == EventTypes.POLICY_BLOCKED

    def test_event_not_published_without_bus(self):
        engine = PolicyEngine()
        v = engine.evaluate(
            _meta_verdict(), _world_model(), _council_verdict(), _good_context(),
        )
        assert v.allowed is True

    def test_policy_hash_present(self):
        engine = PolicyEngine()
        v = engine.evaluate(
            _meta_verdict(), _world_model(), _council_verdict(), _good_context(),
        )
        assert len(v.policy_hash) > 0

    def test_hash_deterministic_across_calls(self):
        engine = PolicyEngine()
        v1 = engine.evaluate(
            _meta_verdict(), _world_model(), _council_verdict(), _good_context(),
        )
        v2 = engine.evaluate(
            _meta_verdict(), _world_model(), _council_verdict(), _good_context(),
        )
        assert v1.policy_hash == v2.policy_hash


# ===================================================================
# PERFORMANCE
# ===================================================================

class TestPerformance:

    def test_10_scenarios(self):
        engine = PolicyEngine()
        scenarios = [
            _good_context(),
            _good_context(circuit_breaker_active=True),
            _good_context(daily_drawdown=MAX_DAILY_DRAWDOWN + 50),
            _good_context(open_positions=[{"s": "a"} for _ in range(MAX_POSITIONS)]),
            _good_context(exposure_by_asset={"BTC": 0.5}),
            _good_context(avg_correlation=0.9),
            _good_context(current_leverage=5.0),
            _good_context(trading_hour=23),
            _good_context(high_volatility=True),
            _good_context(macro_event_block=True),
        ]
        start = time.perf_counter()
        for ctx in scenarios:
            engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0

    def test_100_scenarios(self):
        engine = PolicyEngine()
        start = time.perf_counter()
        for i in range(100):
            ctx = _good_context(daily_risk_used=float(i * 10))
            engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0

    def test_1000_scenarios(self):
        engine = PolicyEngine()
        start = time.perf_counter()
        for i in range(1000):
            ctx = _good_context(daily_drawdown=float(i % 600))
            engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        elapsed = time.perf_counter() - start
        assert elapsed < 30.0


# ===================================================================
# ROBUSTEZ
# ===================================================================

class TestRobustness:

    def test_context_none(self):
        engine = PolicyEngine()
        v = engine.evaluate(None, None, None, None)
        assert isinstance(v, PolicyVerdict)
        assert v.decision in ("ALLOWED", "BLOCKED")
        assert 0.0 <= v.compliance_score <= 1.0

    def test_context_empty(self):
        engine = PolicyEngine()
        v = engine.evaluate(None, None, None, {})
        assert isinstance(v, PolicyVerdict)

    def test_no_open_positions(self):
        engine = PolicyEngine()
        v = engine.evaluate(None, None, None, {"open_positions": []})
        assert isinstance(v, PolicyVerdict)

    def test_missing_all_fields(self):
        engine = PolicyEngine()
        v = engine.evaluate(None, None, None, {"trading_hour": 3})
        assert isinstance(v, PolicyVerdict)

    def test_no_exceptions_on_empty(self):
        engine = PolicyEngine()
        try:
            engine.evaluate(None, None, None, None)
        except Exception:
            pytest.fail("PolicyEngine raised on empty input")

    def test_returns_valid_verdict_always(self):
        engine = PolicyEngine()
        for _ in range(20):
            v = engine.evaluate(None, None, None, {})
            assert isinstance(v, PolicyVerdict)
            assert v.decision in ("ALLOWED", "BLOCKED")
            assert 0.0 <= v.compliance_score <= 1.0


# ===================================================================
# COMPLIANCE SCORE
# ===================================================================

class TestComplianceScore:

    def test_perfect_score(self):
        engine = PolicyEngine()
        v = engine.evaluate(
            _meta_verdict(), _world_model(), _council_verdict(), _good_context(),
        )
        assert v.compliance_score == 1.0

    def test_penalty_per_violation(self):
        engine = PolicyEngine()
        ctx = _good_context(circuit_breaker_active=True, high_volatility=True)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.compliance_score < 1.0
        assert v.compliance_score > 0.0

    def test_score_never_negative(self):
        engine = PolicyEngine()
        ctx = _good_context(
            open_positions=[{"s": str(i)} for i in range(20)],
            daily_risk_used=99999,
            circuit_breaker_active=True,
            high_volatility=True,
            macro_event_block=True,
        )
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert v.compliance_score >= 0.0

    def test_warnings_generated(self):
        engine = PolicyEngine()
        ctx = _good_context(
            open_positions=[{"s": "a"}, {"s": "b"}, {"s": "c"}, {"s": "d"}],
        )
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert len(v.warnings) > 0

    def test_recommendations_present_on_block(self):
        engine = PolicyEngine()
        ctx = _good_context(circuit_breaker_active=True)
        v = engine.evaluate(_meta_verdict(), _world_model(), _council_verdict(), ctx)
        assert len(v.recommendations) > 0
