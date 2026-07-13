import sys
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest

from ENGINE.skills.skill_opinion import SkillOpinion, SkillMetrics
from ENGINE.world.world_types import WorldModel, MarketState, MarketQuality
from ENGINE.council.health_types import HealthScore, HealthStatus
from ENGINE.council.evidence_types import (
    EvidenceNode, EvidenceCluster, EvidenceConflict, EvidenceGraph,
)
from ENGINE.council.weight_types import SkillWeight, WeightDistribution
from ENGINE.council.council_types import CouncilVerdict
from ENGINE.council.council_config import (
    CONSENSUS_HIGH, CONSENSUS_MODERATE,
)
from ENGINE.council.consensus_engine import SkillConsensusEngine
from CORE.events.event_bus import EventBus


def _opinion(name: str, conf: float = 0.7, risk: float = 0.3,
             prob: float = 0.6, evidence: Optional[List[str]] = None,
             obs: str = "", success: bool = True) -> SkillOpinion:
    return SkillOpinion(
        skill_name=name, confidence=conf, risk=risk,
        probability=prob, evidence=evidence or ["evidencia generica"],
        observations=obs, success=success,
    )


def _health(score: float) -> HealthScore:
    if score >= 0.9:
        st = HealthStatus.EXCELLENT
    elif score >= 0.7:
        st = HealthStatus.GOOD
    elif score >= 0.5:
        st = HealthStatus.FAIR
    elif score >= 0.3:
        st = HealthStatus.DEGRADED
    else:
        st = HealthStatus.CRITICAL
    return HealthScore(
        skill_name="x", score=score, availability=min(1.0, score),
        reliability=min(1.0, score), precision=min(1.0, score),
        latency_score=1.0, stability=1.0, timeout_penalty=0.0,
        error_penalty=0.0, status=st, recommendations=[],
    )


def _weight(name: str, fw: float = 0.5) -> SkillWeight:
    return SkillWeight(
        skill_name=name, final_weight=fw, base_weight=0.5,
        regime_multiplier=1.0, health_multiplier=1.0,
        performance_multiplier=1.0, confidence_multiplier=1.0,
        specialization_multiplier=1.0, normalization_factor=1.0,
        reasons=[],
    )


def _weights(map: Dict[str, float]) -> WeightDistribution:
    sw = {n: _weight(n, fw) for n, fw in map.items()}
    total = sum(fw for fw in map.values())
    raw = f"{[f'{n}|{w.final_weight}' for n,w in sorted(sw.items())]}"
    import hashlib
    return WeightDistribution(
        weights=sw, total_weight=total, normalized=True,
        distribution_hash=hashlib.sha256(raw.encode()).hexdigest(),
    )


def _empty_graph() -> EvidenceGraph:
    return EvidenceGraph(
        nodes=(), clusters=(), contradictions=(),
        confidence=0.0, quality=0.0, consistency=0.0,
        graph_hash="empty", num_skills=0, num_duplicates_removed=0,
    )


def _graph_with_nodes(
    nodes: tuple, clusters: tuple = (), contradictions: tuple = (),
    quality: float = 0.7, consistency: float = 0.8,
) -> EvidenceGraph:
    conv = 0.0
    div = 0.0
    if contradictions:
        div = 0.3 * len(contradictions)
    else:
        conv = 0.8

    return EvidenceGraph(
        nodes=nodes, clusters=clusters, contradictions=contradictions,
        confidence=0.0, quality=quality, consistency=consistency,
        graph_hash="test", num_skills=len(nodes),
        num_duplicates_removed=0,
    )


class TestCouncilVerdictTypes(unittest.TestCase):

    def test_immutable(self):
        v = CouncilVerdict(
            consensus_score=0.5, global_confidence=0.6, global_risk=0.3,
            global_probability=0.5, evidence_quality=0.7,
            evidence_consistency=0.8, agreement_level=0.7,
            disagreement_level=0.1, participating_skills=["smc"],
            conflicting_skills=[], supporting_clusters=[],
            conflicting_clusters=[], strongest_evidence=[],
            weakest_evidence=[], summary="teste", council_hash="abc",
        )
        with self.assertRaises(AttributeError):
            v.consensus_score = 0.9

    def test_to_dict(self):
        v = CouncilVerdict(
            consensus_score=0.5, global_confidence=0.6, global_risk=0.3,
            global_probability=0.5, evidence_quality=0.7,
            evidence_consistency=0.8, agreement_level=0.7,
            disagreement_level=0.1, participating_skills=["smc"],
            conflicting_skills=[], supporting_clusters=["Estrutura"],
            conflicting_clusters=[], strongest_evidence=["BOS"],
            weakest_evidence=["sinal fraco"], summary="ok",
            council_hash="h1",
        )
        d = v.to_dict()
        self.assertEqual(d["consensus_score"], 0.5)
        self.assertEqual(d["summary"], "ok")
        self.assertIn("created_at", d)

    def test_to_json_roundtrip(self):
        v = CouncilVerdict(
            consensus_score=0.7, global_confidence=0.8, global_risk=0.2,
            global_probability=0.7, evidence_quality=0.9,
            evidence_consistency=0.9, agreement_level=0.9,
            disagreement_level=0.0, participating_skills=["a", "b"],
            conflicting_skills=[], supporting_clusters=["X"],
            conflicting_clusters=[], strongest_evidence=["e1"],
            weakest_evidence=["e2"], summary="teste", council_hash="h2",
        )
        j = v.to_json()
        restored = CouncilVerdict.from_json(j)
        self.assertEqual(restored.consensus_score, 0.7)
        self.assertEqual(restored.summary, "teste")
        self.assertEqual(restored.participating_skills, ["a", "b"])

    def test_hash_deterministic(self):
        v1 = CouncilVerdict(
            consensus_score=0.5, global_confidence=0.6, global_risk=0.3,
            global_probability=0.5, evidence_quality=0.7,
            evidence_consistency=0.8, agreement_level=0.7,
            disagreement_level=0.1, participating_skills=[],
            conflicting_skills=[], supporting_clusters=[],
            conflicting_clusters=[], strongest_evidence=[],
            weakest_evidence=[], summary="x", council_hash="",
        )
        h1 = CouncilVerdict.compute_hash(v1)
        h2 = CouncilVerdict.compute_hash(v1)
        self.assertEqual(h1, h2)

    def test_hash_changes(self):
        v1 = CouncilVerdict(
            consensus_score=0.5, global_confidence=0.6, global_risk=0.3,
            global_probability=0.5, evidence_quality=0.7,
            evidence_consistency=0.8, agreement_level=0.7,
            disagreement_level=0.1, participating_skills=[],
            conflicting_skills=[], supporting_clusters=[],
            conflicting_clusters=[], strongest_evidence=[],
            weakest_evidence=[], summary="x", council_hash="",
        )
        v2 = CouncilVerdict(
            consensus_score=0.9, global_confidence=0.6, global_risk=0.3,
            global_probability=0.5, evidence_quality=0.7,
            evidence_consistency=0.8, agreement_level=0.7,
            disagreement_level=0.1, participating_skills=[],
            conflicting_skills=[], supporting_clusters=[],
            conflicting_clusters=[], strongest_evidence=[],
            weakest_evidence=[], summary="x", council_hash="",
        )
        self.assertNotEqual(
            CouncilVerdict.compute_hash(v1),
            CouncilVerdict.compute_hash(v2),
        )

    def test_from_dict_roundtrip(self):
        v = CouncilVerdict(
            consensus_score=0.5, global_confidence=0.6, global_risk=0.3,
            global_probability=0.5, evidence_quality=0.7,
            evidence_consistency=0.8, agreement_level=0.7,
            disagreement_level=0.1, participating_skills=["smc"],
            conflicting_skills=[], supporting_clusters=[],
            conflicting_clusters=[], strongest_evidence=["a"],
            weakest_evidence=["b"], summary="teste", council_hash="h",
        )
        d = v.to_dict()
        restored = CouncilVerdict.from_dict(d)
        self.assertEqual(restored.consensus_score, v.consensus_score)
        self.assertEqual(restored.participating_skills, ["smc"])


class TestEmptyAndEdgeCases(unittest.TestCase):

    def setUp(self):
        self.engine = SkillConsensusEngine()

    def test_no_opinions_returns_empty(self):
        v = self.engine.evaluate([], _empty_graph(), _weights({}), {})
        self.assertEqual(v.consensus_score, 0.0)
        self.assertEqual(v.global_risk, 1.0)
        self.assertEqual(v.participating_skills, [])
        self.assertIn("Nenhuma Skill", v.summary)

    def test_single_skill(self):
        op = _opinion("smc", conf=0.8, risk=0.2, prob=0.7)
        w = _weights({"smc": 1.0})
        h = {"smc": _health(0.95)}
        g = _empty_graph()
        v = self.engine.evaluate([op], g, w, h)
        self.assertAlmostEqual(v.global_confidence, 0.8, places=4)
        self.assertAlmostEqual(v.global_risk, 0.2, places=4)
        self.assertAlmostEqual(v.global_probability, 0.7, places=4)
        self.assertIn("smc", v.participating_skills)

    def test_failed_skill_excluded(self):
        op = _opinion("broken", conf=0.0, risk=1.0, prob=0.0, success=False)
        v = self.engine.evaluate([op], _empty_graph(), _weights({"broken": 1.0}), {})
        self.assertEqual(v.participating_skills, [])

    def test_no_health_map(self):
        op = _opinion("smc", conf=0.7)
        v = self.engine.evaluate([op], _empty_graph(), _weights({"smc": 1.0}), {})
        self.assertGreater(v.global_confidence, 0.0)

    def test_no_weights(self):
        op = _opinion("smc", conf=0.7)
        v = self.engine.evaluate([op], _empty_graph(), _weights({}), {})
        self.assertGreater(v.global_confidence, 0.0)

    def test_no_exceptions(self):
        try:
            v = self.engine.evaluate([], _empty_graph(), _weights({}), {})
            self.assertIsNotNone(v)
        except Exception:
            self.fail("SkillConsensusEngine raised unexpected exception")


class TestConsensusTwoSkills(unittest.TestCase):

    def setUp(self):
        self.engine = SkillConsensusEngine()

    def test_two_skills_agreeing(self):
        ops = [_opinion("smc", 0.8, 0.2, 0.7), _opinion("volume", 0.8, 0.2, 0.7)]
        w = _weights({"smc": 0.5, "volume": 0.5})
        h = {"smc": _health(0.95), "volume": _health(0.95)}
        g = _graph_with_nodes(
            nodes=(
                EvidenceNode("ev_0", "BOS", ("smc",), 0.8, 0.2, 0.7, 1, 0.6),
                EvidenceNode("ev_1", "RVOL", ("volume",), 0.8, 0.2, 0.7, 1, 0.6),
            ),
            quality=0.8, consistency=0.9,
        )
        v = self.engine.evaluate(ops, g, w, h)
        self.assertGreater(v.consensus_score, 0.6)
        self.assertGreater(v.agreement_level, 0.7)
        self.assertEqual(len(v.participating_skills), 2)

    def test_two_skills_diverging(self):
        ops = [_opinion("smc", 0.8, 0.2, 0.7), _opinion("volume", 0.2, 0.8, 0.2)]
        w = _weights({"smc": 0.5, "volume": 0.5})
        h = {"smc": _health(0.95), "volume": _health(0.95)}
        g = _graph_with_nodes(
            nodes=(
                EvidenceNode("ev_0", "BOS alta", ("smc",), 0.8, 0.2, 0.7, 1, 0.6),
                EvidenceNode("ev_1", "BOS alta", ("volume",), 0.2, 0.8, 0.2, 1, 0.6),
            ),
            contradictions=(
                EvidenceConflict("ev_0", "ev_1", 0.6, "Conflito smc vs volume"),
            ),
            quality=0.5, consistency=0.4,
        )
        v = self.engine.evaluate(ops, g, w, h)
        self.assertGreater(v.disagreement_level, 0.3)

    def test_two_skills_agreement_level_high(self):
        ops = [_opinion("a", 0.7), _opinion("b", 0.7)]
        g = _graph_with_nodes(
            nodes=(
                EvidenceNode("ev_0", "ev1", ("a",), 0.7, 0.3, 0.6, 1, 0.5),
                EvidenceNode("ev_1", "ev2", ("b",), 0.7, 0.3, 0.6, 1, 0.5),
            ),
            quality=0.8, consistency=0.9,
        )
        v = self.engine.evaluate(ops, g, _weights({"a": 0.5, "b": 0.5}),
                                 {"a": _health(0.9), "b": _health(0.9)})
        self.assertGreater(v.agreement_level, 0.7)

    def test_conflicting_skills_detected(self):
        ops = [_opinion("smc", 0.8), _opinion("volume", 0.2)]
        g = _graph_with_nodes(
            nodes=(
                EvidenceNode("ev_0", "BOS", ("smc",), 0.8, 0.2, 0.7, 1, 0.6),
                EvidenceNode("ev_1", "BOS", ("volume",), 0.2, 0.8, 0.2, 1, 0.6),
            ),
            contradictions=(
                EvidenceConflict("ev_0", "ev_1", 0.6, "conflito"),
            ),
            quality=0.5, consistency=0.5,
        )
        v = self.engine.evaluate(ops, g, _weights({"smc": 0.5, "volume": 0.5}),
                                 {"smc": _health(0.9), "volume": _health(0.9)})
        self.assertIn("smc", v.conflicting_skills)
        self.assertIn("volume", v.conflicting_skills)


class TestMultipleSkills(unittest.TestCase):

    def setUp(self):
        self.engine = SkillConsensusEngine()

    def _build_scenario(self, n: int, conf: float = 0.7):
        ops = [_opinion(f"s{i}", conf, 0.3, 0.6) for i in range(n)]
        w = _weights({f"s{i}": 1.0 / n for i in range(n)})
        h = {f"s{i}": _health(0.9) for i in range(n)}
        g = _graph_with_nodes(
            nodes=tuple(
                EvidenceNode(f"ev_{i}", f"ev_{i}", (f"s{i}",), conf, 0.3, 0.6, 1, 0.5)
                for i in range(n)
            ),
            quality=0.7, consistency=0.8,
        )
        return ops, g, w, h

    def test_5_skills(self):
        ops, g, w, h = self._build_scenario(5)
        v = self.engine.evaluate(ops, g, w, h)
        self.assertEqual(len(v.participating_skills), 5)
        self.assertGreater(v.consensus_score, 0.0)

    def test_10_skills(self):
        ops, g, w, h = self._build_scenario(10)
        v = self.engine.evaluate(ops, g, w, h)
        self.assertEqual(len(v.participating_skills), 10)

    def test_50_skills(self):
        ops, g, w, h = self._build_scenario(50)
        v = self.engine.evaluate(ops, g, w, h)
        self.assertEqual(len(v.participating_skills), 50)


class TestWeightsAndHealth(unittest.TestCase):

    def setUp(self):
        self.engine = SkillConsensusEngine()

    def test_health_affects_confidence(self):
        op = _opinion("smc", 0.8)
        g = _graph_with_nodes(
            nodes=(EvidenceNode("ev_0", "test", ("smc",), 0.8, 0.2, 0.6, 1, 0.5),),
            quality=0.7, consistency=0.8,
        )

        v_high = self.engine.evaluate([op], g, _weights({"smc": 1.0}),
                                      {"smc": _health(0.95)})
        v_low = self.engine.evaluate([op], g, _weights({"smc": 1.0}),
                                     {"smc": _health(0.1)})
        self.assertGreaterEqual(v_high.global_confidence, v_low.global_confidence)

    def test_weight_affects_consensus(self):
        ops = [_opinion("a", 0.9), _opinion("b", 0.3)]
        g = _graph_with_nodes(
            nodes=(
                EvidenceNode("ev_0", "a", ("a",), 0.9, 0.1, 0.8, 1, 0.5),
                EvidenceNode("ev_1", "b", ("b",), 0.3, 0.7, 0.2, 1, 0.5),
            ),
            quality=0.7, consistency=0.8,
        )
        h = {"a": _health(0.9), "b": _health(0.9)}

        v_a = self.engine.evaluate(ops, g, _weights({"a": 0.9, "b": 0.1}), h)
        v_b = self.engine.evaluate(ops, g, _weights({"a": 0.1, "b": 0.9}), h)
        self.assertGreater(v_a.global_confidence, v_b.global_confidence)

    def test_evidence_quality_affects_consensus(self):
        op = [_opinion("smc", 0.7)]
        w = _weights({"smc": 1.0})
        h = {"smc": _health(0.9)}
        n = (EvidenceNode("ev_0", "test", ("smc",), 0.7, 0.3, 0.6, 1, 0.5),)

        v_high = self.engine.evaluate(op, _graph_with_nodes(n, quality=0.9, consistency=0.9), w, h)
        v_low = self.engine.evaluate(op, _graph_with_nodes(n, quality=0.1, consistency=0.1), w, h)
        self.assertGreater(v_high.consensus_score, v_low.consensus_score)


class TestStrongestWeakestEvidence(unittest.TestCase):

    def setUp(self):
        self.engine = SkillConsensusEngine()

    def test_strongest_evidence_returned(self):
        node_a = EvidenceNode("ev_0", "forte", ("smc",), 0.9, 0.1, 0.8, 1, 0.9)
        node_b = EvidenceNode("ev_1", "fraco", ("volume",), 0.1, 0.9, 0.1, 1, 0.1)
        g = _graph_with_nodes(nodes=(node_a, node_b), quality=0.7, consistency=0.8)
        v = self.engine.evaluate([_opinion("smc"), _opinion("volume")], g,
                                 _weights({"smc": 0.5, "volume": 0.5}),
                                 {"smc": _health(0.9), "volume": _health(0.9)})
        self.assertIn("forte", v.strongest_evidence)
        self.assertIn("fraco", v.weakest_evidence)


class TestSummary(unittest.TestCase):

    def setUp(self):
        self.engine = SkillConsensusEngine()

    def test_summary_contains_skill_count(self):
        ops = [_opinion("smc", 0.8), _opinion("volume", 0.7)]
        g = _graph_with_nodes(
            nodes=(
                EvidenceNode("ev_0", "BOS", ("smc",), 0.8, 0.2, 0.7, 1, 0.6),
                EvidenceNode("ev_1", "RVOL", ("volume",), 0.7, 0.3, 0.6, 1, 0.6),
            ),
            quality=0.7, consistency=0.8,
        )
        v = self.engine.evaluate(ops, g, _weights({"smc": 0.5, "volume": 0.5}),
                                 {"smc": _health(0.9), "volume": _health(0.9)})
        self.assertIn("2 skill(s)", v.summary)

    def test_summary_no_opinions(self):
        v = self.engine.evaluate([], _empty_graph(), _weights({}), {})
        self.assertIn("Nenhuma Skill", v.summary)


class TestEventBus(unittest.TestCase):

    def test_event_published(self):
        received = []

        def handler(event):
            received.append(event)

        bus = EventBus()
        bus.subscribe("council.verdict_ready", handler)
        engine = SkillConsensusEngine(event_bus=bus)

        op = _opinion("smc", 0.7)
        v = engine.evaluate([op], _empty_graph(), _weights({"smc": 1.0}),
                            {"smc": _health(0.9)})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].type, "council.verdict_ready")
        self.assertIn("verdict", received[0].data)

    def test_event_not_published_without_bus(self):
        engine = SkillConsensusEngine()
        op = _opinion("smc", 0.7)
        v = engine.evaluate([op], _empty_graph(), _weights({"smc": 1.0}),
                            {"smc": _health(0.9)})
        self.assertIsNotNone(v)

    def test_council_hash_present(self):
        engine = SkillConsensusEngine()
        op = _opinion("smc", 0.7)
        v = engine.evaluate([op], _empty_graph(), _weights({"smc": 1.0}),
                            {"smc": _health(0.9)})
        self.assertTrue(len(v.council_hash) > 0)

    def test_hash_deterministic_across_calls(self):
        engine = SkillConsensusEngine()
        op = _opinion("smc", 0.7)
        v1 = engine.evaluate([op], _empty_graph(), _weights({"smc": 1.0}),
                             {"smc": _health(0.9)})
        v2 = engine.evaluate([op], _empty_graph(), _weights({"smc": 1.0}),
                             {"smc": _health(0.9)})
        self.assertEqual(v1.council_hash, v2.council_hash)


class TestPerformance(unittest.TestCase):

    def setUp(self):
        self.engine = SkillConsensusEngine()

    def _build_scenario(self, n: int):
        opinions = [_opinion(f"s{i}", 0.5 + (i % 5) * 0.1) for i in range(n)]
        w = _weights({f"s{i}": 1.0 / n for i in range(n)})
        h = {f"s{i}": _health(0.5 + (i % 5) * 0.1) for i in range(n)}
        nodes = tuple(
            EvidenceNode(f"ev_{i}", f"evidence_{i}", (f"s{i}",),
                         0.5 + (i % 5) * 0.1, 0.3, 0.5, 1, 0.5)
            for i in range(n)
        )
        g = _graph_with_nodes(nodes=nodes, quality=0.7, consistency=0.8)
        return opinions, g, w, h

    def test_10_skills(self):
        ops, g, w, h = self._build_scenario(10)
        t0 = time.perf_counter()
        v = self.engine.evaluate(ops, g, w, h)
        elapsed = time.perf_counter() - t0
        self.assertEqual(len(v.participating_skills), 10)
        self.assertLess(elapsed, 2.0)

    def test_100_skills(self):
        ops, g, w, h = self._build_scenario(100)
        t0 = time.perf_counter()
        v = self.engine.evaluate(ops, g, w, h)
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 3.0)

    def test_500_skills(self):
        ops, g, w, h = self._build_scenario(500)
        t0 = time.perf_counter()
        v = self.engine.evaluate(ops, g, w, h)
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 5.0)


class TestRobustness(unittest.TestCase):

    def setUp(self):
        self.engine = SkillConsensusEngine()

    def test_missing_skill_in_health_map(self):
        ops = [_opinion("smc"), _opinion("volume")]
        g = _graph_with_nodes(
            nodes=(
                EvidenceNode("ev_0", "a", ("smc",), 0.7, 0.3, 0.6, 1, 0.5),
                EvidenceNode("ev_1", "b", ("volume",), 0.7, 0.3, 0.6, 1, 0.5),
            ),
            quality=0.7, consistency=0.8,
        )
        v = self.engine.evaluate(ops, g, _weights({"smc": 0.5, "volume": 0.5}),
                                 {"smc": _health(0.9)})
        self.assertGreater(v.consensus_score, 0.0)

    def test_missing_skill_in_weights(self):
        ops = [_opinion("smc"), _opinion("volume")]
        v = self.engine.evaluate(ops, _empty_graph(),
                                 _weights({"smc": 1.0}),
                                 {"smc": _health(0.9), "volume": _health(0.9)})
        self.assertGreater(v.consensus_score, 0.0)

    def test_empty_evidence_graph(self):
        ops = [_opinion("smc", 0.7)]
        v = self.engine.evaluate(ops, _empty_graph(), _weights({"smc": 1.0}),
                                 {"smc": _health(0.9)})
        self.assertGreater(v.consensus_score, 0.0)


class TestConsensusScoreRanges(unittest.TestCase):

    def setUp(self):
        self.engine = SkillConsensusEngine()

    def test_consensus_score_range(self):
        ops = [_opinion("a", 0.5), _opinion("b", 0.5)]
        g = _graph_with_nodes(
            nodes=(
                EvidenceNode("ev_0", "x", ("a",), 0.5, 0.5, 0.5, 1, 0.5),
                EvidenceNode("ev_1", "y", ("b",), 0.5, 0.5, 0.5, 1, 0.5),
            ),
            quality=0.5, consistency=0.5,
        )
        v = self.engine.evaluate(ops, g, _weights({"a": 0.5, "b": 0.5}),
                                 {"a": _health(0.5), "b": _health(0.5)})
        self.assertGreaterEqual(v.consensus_score, 0.0)
        self.assertLessEqual(v.consensus_score, 1.0)

    def test_high_consensus_with_good_input(self):
        ops = [_opinion("a", 0.9, 0.1, 0.85), _opinion("b", 0.85, 0.15, 0.8)]
        g = _graph_with_nodes(
            nodes=(
                EvidenceNode("ev_0", "forte", ("a",), 0.9, 0.1, 0.85, 1, 0.8),
                EvidenceNode("ev_1", "forte b", ("b",), 0.85, 0.15, 0.8, 1, 0.8),
            ),
            quality=0.9, consistency=0.95,
        )
        v = self.engine.evaluate(ops, g, _weights({"a": 0.5, "b": 0.5}),
                                 {"a": _health(1.0), "b": _health(1.0)})
        self.assertGreater(v.consensus_score, 0.7)

    def test_low_consensus_with_poor_input(self):
        ops = [_opinion("a", 0.2, 0.8, 0.1), _opinion("b", 0.3, 0.7, 0.2)]
        g = _graph_with_nodes(
            nodes=(
                EvidenceNode("ev_0", "fraco", ("a",), 0.2, 0.8, 0.1, 1, 0.2),
                EvidenceNode("ev_1", "fraco b", ("b",), 0.3, 0.7, 0.2, 1, 0.2),
            ),
            quality=0.2, consistency=0.3,
        )
        v = self.engine.evaluate(ops, g, _weights({"a": 0.5, "b": 0.5}),
                                 {"a": _health(0.2), "b": _health(0.2)})
        self.assertLess(v.consensus_score, 0.5)


if __name__ == "__main__":
    unittest.main()
