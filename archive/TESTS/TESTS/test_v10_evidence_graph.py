import sys
import json
import time
from typing import List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest

from ENGINE.skills.skill_opinion import SkillOpinion, SkillMetrics
from ENGINE.council.evidence_types import (
    EvidenceNode,
    EvidenceCluster,
    EvidenceConflict,
    EvidenceGraph,
)
from ENGINE.council.evidence_graph import EvidenceGraphBuilder


def _make_opinion(
    name: str, conf: float, risk: float, prob: float,
    evidence: List[str], success: bool = True,
) -> SkillOpinion:
    return SkillOpinion(
        skill_name=name, confidence=conf, risk=risk,
        probability=prob, evidence=evidence, observations="",
        success=success,
    )


class TestEvidenceTypes(unittest.TestCase):

    def test_evidence_node_immutable(self):
        node = EvidenceNode(
            id="ev_0", evidence_text="teste",
            source_skills=("smc",), confidence=0.7,
            risk=0.3, probability=0.6, occurrences=1, weight=0.5,
        )
        with self.assertRaises(AttributeError):
            node.confidence = 0.9

    def test_evidence_cluster_immutable(self):
        cluster = EvidenceCluster(
            id="c0", topic="Estrutura",
            node_ids=("ev_0", "ev_1"),
            evidence_texts=("a", "b"),
            confidence=0.7, consistency=0.8, weight=0.6,
        )
        with self.assertRaises(AttributeError):
            cluster.confidence = 0.9

    def test_evidence_conflict_immutable(self):
        c = EvidenceConflict(source_id="ev_0", target_id="ev_1", severity=0.5, description="conflito")
        with self.assertRaises(AttributeError):
            c.severity = 0.9

    def test_graph_immutable(self):
        g = EvidenceGraph(
            nodes=(), clusters=(), contradictions=(),
            confidence=0.0, quality=0.0, consistency=0.0,
            graph_hash="abc", num_skills=0, num_duplicates_removed=0,
        )
        with self.assertRaises(AttributeError):
            g.confidence = 0.5

    def test_graph_to_dict(self):
        g = EvidenceGraph(
            nodes=(), clusters=(), contradictions=(),
            confidence=0.5, quality=0.6, consistency=0.7,
            graph_hash="abc123", num_skills=2, num_duplicates_removed=1,
        )
        d = g.to_dict()
        self.assertEqual(d["confidence"], 0.5)
        self.assertEqual(d["quality"], 0.6)
        self.assertEqual(d["graph_hash"], "abc123")
        self.assertIn("nodes", d)
        self.assertIn("clusters", d)

    def test_graph_to_json(self):
        g = EvidenceGraph(
            nodes=(), clusters=(), contradictions=(),
            confidence=0.5, quality=0.6, consistency=0.7,
            graph_hash="abc", num_skills=0, num_duplicates_removed=0,
        )
        j = g.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["confidence"], 0.5)
        self.assertEqual(parsed["graph_hash"], "abc")

    def test_graph_from_dict_roundtrip(self):
        original = EvidenceGraph(
            nodes=(
                EvidenceNode("ev_0", "teste", ("smc",), 0.7, 0.3, 0.6, 1, 0.5),
            ),
            clusters=(),
            contradictions=(),
            confidence=0.7, quality=0.8, consistency=1.0,
            graph_hash="hash1", num_skills=1, num_duplicates_removed=0,
        )
        d = original.to_dict()
        restored = EvidenceGraph.from_dict(d)
        self.assertEqual(restored.confidence, original.confidence)
        self.assertEqual(restored.graph_hash, original.graph_hash)
        self.assertEqual(len(restored.nodes), 1)
        self.assertEqual(restored.nodes[0].evidence_text, "teste")

    def test_graph_from_json_roundtrip(self):
        original = EvidenceGraph(
            nodes=(),
            clusters=(
                EvidenceCluster("c0", "Estrutura", ("ev_0",), ("texto",), 0.7, 0.8, 0.6),
            ),
            contradictions=(),
            confidence=0.7, quality=0.8, consistency=1.0,
            graph_hash="hash2", num_skills=1, num_duplicates_removed=0,
        )
        j = original.to_json()
        restored = EvidenceGraph.from_json(j)
        self.assertEqual(len(restored.clusters), 1)
        self.assertEqual(restored.clusters[0].topic, "Estrutura")
        self.assertEqual(restored.graph_hash, "hash2")


class TestEvidenceGraphContract(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()

    def test_empty_returns_empty_graph(self):
        g = self.builder.build([])
        self.assertEqual(g.num_skills, 0)
        self.assertEqual(len(g.nodes), 0)
        self.assertEqual(len(g.clusters), 0)
        self.assertEqual(len(g.contradictions), 0)
        self.assertEqual(g.confidence, 0.0)
        self.assertEqual(g.quality, 0.0)
        self.assertEqual(g.consistency, 0.0)
        self.assertTrue(isinstance(g.graph_hash, str))
        self.assertEqual(g.num_duplicates_removed, 0)

    def test_return_type(self):
        opinion = _make_opinion("smc", 0.7, 0.3, 0.6, ["teste"])
        g = self.builder.build([opinion])
        self.assertIsInstance(g, EvidenceGraph)

    def test_hash_is_deterministic(self):
        op = _make_opinion("smc", 0.7, 0.3, 0.6, ["BOS confirmado", "CHoCH alto"])
        g1 = self.builder.build([op])
        g2 = self.builder.build([op])
        self.assertEqual(g1.graph_hash, g2.graph_hash)

    def test_hash_changes_with_different_evidence(self):
        op1 = _make_opinion("smc", 0.7, 0.3, 0.6, ["BOS confirmado"])
        op2 = _make_opinion("smc", 0.7, 0.3, 0.6, ["Outra evidencia"])
        g1 = self.builder.build([op1])
        g2 = self.builder.build([op2])
        self.assertNotEqual(g1.graph_hash, g2.graph_hash)

    def test_node_has_correct_fields(self):
        op = _make_opinion("smc", 0.7, 0.3, 0.6, ["BOS confirmado"])
        g = self.builder.build([op])
        node = g.nodes[0]
        self.assertEqual(node.evidence_text, "BOS confirmado")
        self.assertEqual(node.source_skills, ("smc",))
        self.assertEqual(node.confidence, 0.7)
        self.assertEqual(node.occurrences, 1)
        self.assertGreater(node.weight, 0.0)

    def test_graph_quality_range(self):
        op = _make_opinion("smc", 0.7, 0.3, 0.6, ["teste"])
        g = self.builder.build([op])
        self.assertGreaterEqual(g.quality, 0.0)
        self.assertLessEqual(g.quality, 1.0)

    def test_graph_consistency_range(self):
        ops = [
            _make_opinion("a", 0.8, 0.2, 0.7, ["ev 1"]),
            _make_opinion("b", 0.2, 0.8, 0.2, ["ev 2"]),
        ]
        g = self.builder.build(ops)
        self.assertGreaterEqual(g.consistency, 0.0)
        self.assertLessEqual(g.consistency, 1.0)

    def test_graph_confidence_range(self):
        op = _make_opinion("smc", 0.7, 0.3, 0.6, ["teste"])
        g = self.builder.build([op])
        self.assertGreaterEqual(g.confidence, 0.0)
        self.assertLessEqual(g.confidence, 1.0)

    def test_graph_hash_string(self):
        op = _make_opinion("smc", 0.7, 0.3, 0.6, ["teste"])
        g = self.builder.build([op])
        self.assertIsInstance(g.graph_hash, str)
        self.assertEqual(len(g.graph_hash), 64)

    def test_num_skills_reported(self):
        ops = [
            _make_opinion("a", 0.5, 0.5, 0.5, ["x"]),
            _make_opinion("b", 0.5, 0.5, 0.5, ["y"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(g.num_skills, 2)


class TestEvidenceGraphBuild(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()

    def test_one_skill(self):
        op = _make_opinion("smc", 0.7, 0.3, 0.6, ["ev1", "ev2"])
        g = self.builder.build([op])
        self.assertEqual(g.num_skills, 1)
        self.assertEqual(len(g.nodes), 2)
        self.assertEqual(len(g.clusters), 0)
        self.assertEqual(len(g.contradictions), 0)

    def test_two_skills(self):
        ops = [
            _make_opinion("smc", 0.7, 0.3, 0.6, ["ev1", "ev2"]),
            _make_opinion("volume", 0.6, 0.4, 0.5, ["ev3"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(g.num_skills, 2)
        self.assertEqual(len(g.nodes), 3)

    def test_five_skills(self):
        ops = [_make_opinion(f"s{i}", 0.5, 0.5, 0.5, [f"ev_{i}"]) for i in range(5)]
        g = self.builder.build(ops)
        self.assertEqual(g.num_skills, 5)
        self.assertEqual(len(g.nodes), 5)

    def test_ten_skills(self):
        ops = [_make_opinion(f"s{i}", 0.5, 0.5, 0.5, [f"ev_{i}"]) for i in range(10)]
        g = self.builder.build(ops)
        self.assertEqual(g.num_skills, 10)
        self.assertEqual(len(g.nodes), 10)

    def test_opinion_without_evidence_no_nodes(self):
        op = _make_opinion("smc", 0.5, 0.5, 0.5, [])
        g = self.builder.build([op])
        self.assertEqual(len(g.nodes), 0)
        self.assertEqual(g.num_skills, 1)

    def test_skill_with_multiple_evidence(self):
        op = _make_opinion("smc", 0.7, 0.3, 0.6, ["a", "b", "c", "d", "e"])
        g = self.builder.build([op])
        self.assertEqual(len(g.nodes), 5)


class TestEvidenceGraphClusters(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()

    def test_estrutura_cluster(self):
        ops = [
            _make_opinion("smc", 0.8, 0.2, 0.7, ["BOS rompimento alta tendencia"]),
            _make_opinion("volume", 0.7, 0.3, 0.6, ["rompimento BOS tendencia alta"]),
        ]
        g = self.builder.build(ops)
        clusters = [c for c in g.clusters if c.topic == "Estrutura"]
        self.assertGreater(len(clusters), 0)

    def test_fluxo_cluster(self):
        ops = [
            _make_opinion("volume", 0.7, 0.3, 0.6, ["fluxo institucional positivo compra"]),
            _make_opinion("smc", 0.7, 0.3, 0.6, ["fluxo compra institucional positivo"]),
        ]
        g = self.builder.build(ops)
        clusters = [c for c in g.clusters if c.topic == "Fluxo"]
        self.assertGreater(len(clusters), 0)

    def test_liquidez_cluster(self):
        ops = [
            _make_opinion("smc", 0.7, 0.3, 0.6, ["sweep liquidity order block alta"]),
            _make_opinion("volume", 0.7, 0.3, 0.6, ["liquidity sweep block order alta"]),
        ]
        g = self.builder.build(ops)
        clusters = [c for c in g.clusters if c.topic == "Liquidez"]
        self.assertGreater(len(clusters), 0)

    def test_volume_cluster(self):
        ops = [
            _make_opinion("volume", 0.8, 0.2, 0.7, ["rvol elevado 2.5x compra"]),
            _make_opinion("smc", 0.6, 0.4, 0.5, ["volume rvol elevado compra"]),
        ]
        g = self.builder.build(ops)
        clusters = [c for c in g.clusters if c.topic == "Volume"]
        self.assertGreater(len(clusters), 0)

    def test_macro_cluster(self):
        ops = [
            _make_opinion("macro", 0.7, 0.3, 0.6, ["btc dominance alta favoravel"]),
            _make_opinion("volume", 0.6, 0.4, 0.5, ["dominance btc alta favoravel"]),
        ]
        g = self.builder.build(ops)
        clusters = [c for c in g.clusters if c.topic == "Macro"]
        self.assertGreater(len(clusters), 0)

    def test_cluster_confidence(self):
        ops = [
            _make_opinion("a", 0.9, 0.1, 0.8, ["BOS rompimento alta tendencia compra"]),
            _make_opinion("b", 0.7, 0.3, 0.6, ["rompimento BOS tendencia compra"]),
        ]
        g = self.builder.build(ops)
        if g.clusters:
            self.assertGreaterEqual(g.clusters[0].confidence, 0.0)
            self.assertLessEqual(g.clusters[0].confidence, 1.0)

    def test_cluster_consistency(self):
        ops = [
            _make_opinion("a", 0.8, 0.2, 0.7, ["BOS rompimento alta tendencia compra"]),
            _make_opinion("b", 0.8, 0.2, 0.7, ["rompimento BOS tendencia alta compra"]),
        ]
        g = self.builder.build(ops)
        if g.clusters:
            self.assertGreaterEqual(g.clusters[0].consistency, 0.0)
            self.assertLessEqual(g.clusters[0].consistency, 1.0)

    def test_no_cluster_when_unrelated(self):
        ops = [
            _make_opinion("a", 0.5, 0.5, 0.5, ["xylophone zebra quantum"]),
            _make_opinion("b", 0.5, 0.5, 0.5, ["banana apple orange"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(len(g.clusters), 0)

    def test_multiple_clusters_isolated(self):
        ops = [
            _make_opinion("a", 0.8, 0.2, 0.7,
                          ["BOS rompimento alta tendencia compra", "rvol elevado 2.5x"]),
            _make_opinion("b", 0.7, 0.3, 0.6,
                          ["tendencia alta BOS rompimento", "volume rvol elevado"]),
        ]
        g = self.builder.build(ops)
        topics = set(c.topic for c in g.clusters)
        self.assertIn("Estrutura", topics)
        self.assertIn("Volume", topics)


class TestEvidenceGraphContradictions(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()

    def test_conflicting_evidence_detected(self):
        ops = [
            _make_opinion("smc", 0.8, 0.2, 0.7, ["BOS rompimento alta tendencia compra"]),
            _make_opinion("volume", 0.2, 0.8, 0.2, ["rompimento BOS tendencia compra"]),
        ]
        g = self.builder.build(ops)
        self.assertGreater(len(g.contradictions), 0)

    def test_convergent_evidence_no_conflict(self):
        ops = [
            _make_opinion("smc", 0.8, 0.2, 0.7, ["evidencia 1"]),
            _make_opinion("volume", 0.8, 0.2, 0.7, ["evidencia 2"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(len(g.contradictions), 0)

    def test_conflict_severity(self):
        ops = [
            _make_opinion("smc", 0.9, 0.1, 0.8, ["BOS rompimento alta tendencia compra"]),
            _make_opinion("volume", 0.1, 0.9, 0.1, ["rompimento BOS tendencia compra"]),
        ]
        g = self.builder.build(ops)
        if g.contradictions:
            self.assertGreater(g.contradictions[0].severity, 0.0)
            self.assertLessEqual(g.contradictions[0].severity, 1.0)

    def test_conflict_description(self):
        ops = [
            _make_opinion("smc", 0.8, 0.2, 0.7, ["BOS rompimento alta tendencia compra"]),
            _make_opinion("volume", 0.2, 0.8, 0.2, ["rompimento BOS tendencia compra"]),
        ]
        g = self.builder.build(ops)
        if g.contradictions:
            self.assertIn("smc", g.contradictions[0].description)
            self.assertIn("volume", g.contradictions[0].description)

    def test_three_skills_two_conflicts(self):
        ops = [
            _make_opinion("a", 0.8, 0.2, 0.7, ["BOS rompimento alta tendencia compra"]),
            _make_opinion("b", 0.7, 0.3, 0.6, ["rompimento BOS tendencia compra"]),
            _make_opinion("c", 0.2, 0.8, 0.2, ["rompimento BOS tendencia compra"]),
        ]
        g = self.builder.build(ops)
        self.assertGreater(len(g.contradictions), 0)


class TestEvidenceGraphDuplicity(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()

    def test_same_evidence_two_skills_one_node(self):
        ops = [
            _make_opinion("smc", 0.7, 0.3, 0.6, ["BOS confirmado"]),
            _make_opinion("volume", 0.8, 0.2, 0.7, ["BOS confirmado"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(len(g.nodes), 1)
        self.assertEqual(g.nodes[0].occurrences, 2)
        self.assertIn("smc", g.nodes[0].source_skills)
        self.assertIn("volume", g.nodes[0].source_skills)

    def test_duplicate_counted(self):
        ops = [
            _make_opinion("smc", 0.7, 0.3, 0.6, ["BOS confirmado"]),
            _make_opinion("volume", 0.8, 0.2, 0.7, ["BOS confirmado"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(g.num_duplicates_removed, 1)

    def test_same_evidence_three_skills(self):
        ops = [
            _make_opinion("a", 0.7, 0.3, 0.6, ["BOS confirmado"]),
            _make_opinion("b", 0.8, 0.2, 0.7, ["BOS confirmado"]),
            _make_opinion("c", 0.9, 0.1, 0.8, ["BOS confirmado"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(len(g.nodes), 1)
        self.assertEqual(g.nodes[0].occurrences, 3)
        self.assertEqual(g.num_duplicates_removed, 2)

    def test_duplicate_confidence_averaged(self):
        ops = [
            _make_opinion("smc", 0.7, 0.3, 0.6, ["BOS confirmado"]),
            _make_opinion("volume", 0.9, 0.1, 0.8, ["BOS confirmado"]),
        ]
        g = self.builder.build(ops)
        expected = (0.7 + 0.9) / 2
        self.assertAlmostEqual(g.nodes[0].confidence, expected, places=4)

    def test_no_duplicates_with_different_text(self):
        ops = [
            _make_opinion("smc", 0.7, 0.3, 0.6, ["BOS confirmado"]),
            _make_opinion("volume", 0.8, 0.2, 0.7, ["RVOL elevado"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(len(g.nodes), 2)
        self.assertEqual(g.num_duplicates_removed, 0)

    def test_duplicate_does_not_affect_other_evidence(self):
        ops = [
            _make_opinion("smc", 0.7, 0.3, 0.6, ["BOS confirmado", "CHoCH alto"]),
            _make_opinion("volume", 0.8, 0.2, 0.7, ["BOS confirmado"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(len(g.nodes), 2)
        self.assertEqual(g.num_duplicates_removed, 1)

    def test_weight_higher_with_duplicates(self):
        op1 = _make_opinion("a", 0.5, 0.5, 0.5, ["evidencia unica"])
        g1 = self.builder.build([op1])
        w1 = g1.nodes[0].weight

        ops2 = [
            _make_opinion("a", 0.5, 0.5, 0.5, ["evidencia duplicada"]),
            _make_opinion("b", 0.5, 0.5, 0.5, ["evidencia duplicada"]),
        ]
        g2 = self.builder.build(ops2)
        w2 = g2.nodes[0].weight
        self.assertGreater(w2, w1)


class TestEvidenceGraphConsistency(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()

    def test_no_contradictions_consistency_one(self):
        ops = [
            _make_opinion("a", 0.7, 0.3, 0.6, ["ev1"]),
            _make_opinion("b", 0.7, 0.3, 0.6, ["ev2"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(g.consistency, 1.0)

    def test_contradictions_lower_consistency(self):
        aligned = [
            _make_opinion("a", 0.8, 0.2, 0.7, ["BOS rompimento alta tendencia compra"]),
            _make_opinion("b", 0.8, 0.2, 0.7, ["rompimento BOS tendencia alta compra"]),
        ]
        opposed = [
            _make_opinion("a", 0.8, 0.2, 0.7, ["BOS rompimento alta tendencia compra"]),
            _make_opinion("b", 0.2, 0.8, 0.2, ["rompimento BOS tendencia alta compra"]),
        ]
        g_ali = self.builder.build(aligned)
        g_opp = self.builder.build(opposed)
        self.assertGreaterEqual(g_ali.consistency, g_opp.consistency)


class TestEvidenceGraphQuality(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()

    def test_more_skills_higher_quality(self):
        single = self.builder.build([_make_opinion("a", 0.5, 0.5, 0.5, ["ev1"])])
        multi = self.builder.build([
            _make_opinion("a", 0.5, 0.5, 0.5, ["ev1"]),
            _make_opinion("b", 0.5, 0.5, 0.5, ["ev2"]),
        ])
        self.assertGreaterEqual(multi.quality, single.quality)

    def test_higher_confidence_higher_quality(self):
        low = self.builder.build([_make_opinion("a", 0.2, 0.8, 0.1, ["ev1"])])
        high = self.builder.build([_make_opinion("a", 0.9, 0.1, 0.9, ["ev1"])])
        self.assertGreaterEqual(high.quality, low.quality)

    def test_quality_range(self):
        ops = [_make_opinion(f"s{i}", 0.5, 0.5, 0.5, [f"ev_{i}"]) for i in range(5)]
        g = self.builder.build(ops)
        self.assertGreaterEqual(g.quality, 0.0)
        self.assertLessEqual(g.quality, 1.0)


class TestEvidenceGraphIntegration(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()
        self.smc = _make_opinion(
            "smc", 0.7, 0.3, 0.6,
            ["BOS confirmado em M15", "CHoCH para cima identificado", "OB formada na regiao"],
        )
        self.volume = _make_opinion(
            "volume", 0.65, 0.35, 0.55,
            ["RVOL 2.5x", "Fluxo institucional positivo", "ADX 28 tendencia moderada"],
        )
        self.macro = _make_opinion(
            "macro", 0.8, 0.2, 0.7,
            ["BTC dominancia favoravel", "Macro cenario positivo"],
        )

    def test_smc_and_volume_graph(self):
        g = self.builder.build([self.smc, self.volume])
        self.assertEqual(g.num_skills, 2)
        self.assertEqual(len(g.nodes), 6)
        self.assertGreater(g.confidence, 0.0)

    def test_three_skills_full_graph(self):
        g = self.builder.build([self.smc, self.volume, self.macro])
        self.assertEqual(g.num_skills, 3)
        self.assertEqual(len(g.nodes), 8)

    def test_serialization_roundtrip(self):
        g = self.builder.build([self.smc, self.volume])
        d = g.to_dict()
        restored = EvidenceGraph.from_dict(d)
        self.assertEqual(restored.confidence, g.confidence)
        self.assertEqual(restored.quality, g.quality)
        self.assertEqual(restored.graph_hash, g.graph_hash)
        self.assertEqual(len(restored.nodes), len(g.nodes))

    def test_json_roundtrip(self):
        g = self.builder.build([self.smc, self.volume])
        j = g.to_json()
        restored = EvidenceGraph.from_json(j)
        self.assertEqual(restored.graph_hash, g.graph_hash)
        self.assertEqual(restored.num_skills, g.num_skills)

    def test_with_failed_skill(self):
        failed = _make_opinion("broken", 0.0, 1.0, 0.0, ["falha critica"], success=False)
        g = self.builder.build([self.smc, failed])
        self.assertEqual(g.num_skills, 2)
        self.assertIn("smc", g.nodes[0].source_skills)

    def test_duplicates_across_all_skills(self):
        ops = [
            _make_opinion("smc", 0.7, 0.3, 0.6, ["BOS confirmado"]),
            _make_opinion("volume", 0.8, 0.2, 0.7, ["BOS confirmado"]),
            _make_opinion("macro", 0.6, 0.4, 0.5, ["BOS confirmado"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(len(g.nodes), 1)
        self.assertEqual(g.nodes[0].occurrences, 3)
        self.assertEqual(g.num_duplicates_removed, 2)

    def test_hash_reproduzivel(self):
        ops = [self.smc, self.volume]
        g1 = self.builder.build(ops)
        g2 = self.builder.build(ops)
        self.assertEqual(g1.graph_hash, g2.graph_hash)

    def test_hard_conflict_reduces_consistency(self):
        concord = [
            _make_opinion("a", 0.8, 0.2, 0.7, ["BOS rompimento alta tendencia compra"]),
            _make_opinion("b", 0.7, 0.3, 0.6, ["rompimento BOS tendencia alta compra"]),
        ]
        discord = [
            _make_opinion("a", 0.9, 0.1, 0.8, ["BOS rompimento alta tendencia compra"]),
            _make_opinion("b", 0.1, 0.9, 0.1, ["rompimento BOS tendencia alta compra"]),
        ]
        gc = self.builder.build(concord)
        gd = self.builder.build(discord)
        self.assertGreater(gc.consistency, gd.consistency)


class TestEvidenceGraphPerformance(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()

    def test_10_evidence(self):
        opinions = [_make_opinion(f"s{i}", 0.5, 0.5, 0.5, [f"evidencia_{j}" for j in range(5)]) for i in range(2)]
        t0 = time.perf_counter()
        g = self.builder.build(opinions)
        elapsed = time.perf_counter() - t0
        self.assertGreater(len(g.nodes), 0)
        self.assertLess(elapsed, 2.0)

    def test_100_evidence(self):
        opinions = [_make_opinion(f"s{i}", 0.5, 0.5, 0.5, [f"evidencia_{j}_{i}" for j in range(50)]) for i in range(2)]
        t0 = time.perf_counter()
        g = self.builder.build(opinions)
        elapsed = time.perf_counter() - t0
        self.assertGreater(len(g.nodes), 0)
        self.assertLess(elapsed, 3.0)

    def test_500_evidence(self):
        opinions = [_make_opinion(f"s{i}", 0.5, 0.5, 0.5, [f"evidencia_{j}_{i}" for j in range(250)]) for i in range(2)]
        t0 = time.perf_counter()
        g = self.builder.build(opinions)
        elapsed = time.perf_counter() - t0
        self.assertGreater(len(g.nodes), 0)
        self.assertLess(elapsed, 5.0)

    def test_1000_evidence(self):
        opinions = [_make_opinion(f"s{i}", 0.5, 0.5, 0.5, [f"evidencia_{j}_{i}" for j in range(500)]) for i in range(2)]
        t0 = time.perf_counter()
        g = self.builder.build(opinions)
        elapsed = time.perf_counter() - t0
        self.assertGreater(len(g.nodes), 0)
        self.assertLess(elapsed, 15.0)

    def test_5_skills_10_evidence_each(self):
        opinions = [_make_opinion(f"s{i}", 0.5, 0.5, 0.5, [f"ev_{j}_{i}" for j in range(10)]) for i in range(5)]
        t0 = time.perf_counter()
        g = self.builder.build(opinions)
        elapsed = time.perf_counter() - t0
        self.assertEqual(g.num_skills, 5)
        self.assertEqual(len(g.nodes), 50)
        self.assertLess(elapsed, 3.0)


class TestEvidenceGraphEdgeCases(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()

    def test_confidence_zero(self):
        ops = [
            _make_opinion("a", 0.0, 1.0, 0.0, ["ev1"]),
            _make_opinion("b", 0.0, 1.0, 0.0, ["ev2"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(g.confidence, 0.0)

    def test_confidence_one(self):
        ops = [
            _make_opinion("a", 1.0, 0.0, 1.0, ["ev1"]),
            _make_opinion("b", 1.0, 0.0, 1.0, ["ev2"]),
        ]
        g = self.builder.build(ops)
        self.assertGreater(g.confidence, 0.0)

    def test_confidence_exactly_05(self):
        ops = [
            _make_opinion("a", 0.5, 0.5, 0.5, ["ev1"]),
            _make_opinion("b", 0.5, 0.5, 0.5, ["ev2"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(g.confidence, 0.5)

    def test_identical_text_case_insensitive(self):
        ops = [
            _make_opinion("a", 0.7, 0.3, 0.6, ["BOS CONFIRMADO"]),
            _make_opinion("b", 0.8, 0.2, 0.7, ["bos confirmado"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(len(g.nodes), 1)
        self.assertEqual(g.nodes[0].occurrences, 2)

    def test_identical_text_with_spaces(self):
        ops = [
            _make_opinion("a", 0.7, 0.3, 0.6, ["  BOS confirmado  "]),
            _make_opinion("b", 0.8, 0.2, 0.7, ["BOS confirmado"]),
        ]
        g = self.builder.build(ops)
        self.assertEqual(len(g.nodes), 1)

    def test_single_skill_single_evidence(self):
        g = self.builder.build([_make_opinion("smc", 0.5, 0.5, 0.5, ["teste"])])
        self.assertEqual(len(g.nodes), 1)
        self.assertEqual(len(g.clusters), 0)
        self.assertEqual(len(g.contradictions), 0)
        self.assertEqual(g.consistency, 1.0)

    def test_same_skill_same_evidence_no_dedup(self):
        g = self.builder.build([_make_opinion("smc", 0.5, 0.5, 0.5, ["teste", "teste"])])
        self.assertEqual(len(g.nodes), 1)
        self.assertEqual(g.nodes[0].occurrences, 1)

    def test_all_skills_identical_evidence(self):
        ops = [_make_opinion(f"s{i}", 0.5, 0.5, 0.5, ["evidencia"]) for i in range(5)]
        g = self.builder.build(ops)
        self.assertEqual(len(g.nodes), 1)
        self.assertEqual(g.nodes[0].occurrences, 5)


class TestEvidenceGraphTopicInference(unittest.TestCase):

    def setUp(self):
        self.builder = EvidenceGraphBuilder()

    def _topic_for(self, text: str) -> str:
        ops = [
            _make_opinion("a", 0.5, 0.5, 0.5, [text]),
            _make_opinion("b", 0.5, 0.5, 0.5, [text + " repetido"]),
        ]
        g = self.builder.build(ops)
        if g.clusters:
            return g.clusters[0].topic
        return ""

    def test_estrutura_topic(self):
        self.assertEqual(self._topic_for("BOS rompimento tendencia alta"), "Estrutura")

    def test_liquidez_topic(self):
        self.assertEqual(self._topic_for("sweep liquidity order block"), "Liquidez")

    def test_fluxo_topic(self):
        self.assertEqual(self._topic_for("fluxo institucional positivo"), "Fluxo")

    def test_volume_topic(self):
        self.assertEqual(self._topic_for("RVOL elevado 2.5x"), "Volume")

    def test_macro_topic(self):
        self.assertEqual(self._topic_for("BTC dominancia alta"), "Macro")

    def test_risco_topic(self):
        self.assertEqual(self._topic_for("spread elevado volatilidade alta"), "Risco")

    def test_momentum_topic(self):
        self.assertEqual(self._topic_for("rsi momentum alta"), "Momentum")


if __name__ == "__main__":
    unittest.main()
