
import unittest
import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes

# Import Decision Engine components
from ENGINE.decision.decision_types import DecisionContext, DecisionResult, DecisionStatus
from ENGINE.decision.decision_engine_v10 import DecisionEngineV10
from ENGINE.decision.decision_config import (
    DEFAULT_CONFIDENCE,
    DEFAULT_DECISION_SCORE,
    DEFAULT_UNCERTAINTY,
    VERSION_ARCH, 
    VERSION_CONTRACTS
)

# --- Mock Implementations for Dependencies ---

class MockWorkingMemory:
    def __init__(self, uncertainty_level: float = 0.5):
        self._uncertainty_level = uncertainty_level

    def get_uncertainty_level(self) -> float:
        return self._uncertainty_level

    def to_dict(self) -> Dict[str, Any]: return {"uncertainty_level": self._uncertainty_level}

class MockDecisionTrace:
    def __init__(self, trace_hash: str = "mock_trace_hash"):
        self._trace_hash = trace_hash

    def get_trace_hash(self) -> str: return self._trace_hash
    def set_trace_hash(self, h: str) -> None: self._trace_hash = h
    def to_dict(self) -> Dict[str, Any]: return {"hash": self._trace_hash}

class MockWorldModel:
    def __init__(self, quality: str = "medium", quality_reasoning: List[str] = None, quality_evidence: List[str] = None, quality_modules: List[str] = None, raise_exception: bool = False):
        self._quality = quality
        self._reasoning = quality_reasoning or ["Mock WM quality assessment"]
        self._evidence = quality_evidence or ["wm_data"]
        self._modules = quality_modules or ["WorldModel"]
        self._raise_exception = raise_exception

    def to_dict(self) -> Dict[str, Any]:
        return {"quality": self._quality, "reasoning": self._reasoning, "evidence": self._evidence, "modules": self._modules}

    def __eq__(self, other):
        if not isinstance(other, MockWorldModel):
            return NotImplemented
        return (
            self._quality == other._quality
            and self._reasoning == other._reasoning
            and self._evidence == other._evidence
            and self._modules == other._modules
            and self._raise_exception == other._raise_exception
        )

class MockSkillsEngine:
    def __init__(self, consistency: str = "medium", cons_reasoning: List[str] = None, cons_evidence: List[str] = None, cons_modules: List[str] = None, raise_exception: bool = False):
        self._consistency = consistency
        self._reasoning = cons_reasoning or ["Mock Skill consistency assessment"]
        self._evidence = cons_evidence or ["skill_data"]
        self._modules = cons_modules or ["SkillsEngine"]
        self._raise_exception = raise_exception

    def to_dict(self) -> Dict[str, Any]:
        return {"consistency": self._consistency, "reasoning": self._reasoning, "evidence": self._evidence, "modules": self._modules}

    def evaluate_consistency(self, context: DecisionContext) -> tuple[str, List[str], List[str], List[str]]:
        if self._raise_exception:
            raise RuntimeError("Mock SkillsEngine error")
        return self._consistency, self._reasoning, self._evidence, self._modules

class MockEvidenceGraph:
    def __init__(self, conflicts: str = "none", conf_reasoning: List[str] = None, conf_evidence: List[str] = None, conf_modules: List[str] = None, raise_exception: bool = False):
        self._conflicts = conflicts
        self._reasoning = conf_reasoning or ["Mock EvidenceGraph assessment"]
        self._evidence = conf_evidence or ["evidence_graph_data"]
        self._modules = conf_modules or ["EvidenceGraph"]
        self._raise_exception = raise_exception

    def to_dict(self) -> Dict[str, Any]:
        return {"conflicts": self._conflicts, "reasoning": self._reasoning, "evidence": self._evidence, "modules": self._modules}

    def evaluate_conflicts(self, context: DecisionContext) -> tuple[str, List[str], List[str], List[str]]:
        if self._raise_exception:
            raise RuntimeError("Mock EvidenceGraph error")
        return self._conflicts, self._reasoning, self._evidence, self._modules

    def has_critical_conflicts(self) -> bool: return self._conflicts == "critical"
    def has_moderate_conflicts(self) -> bool: return self._conflicts == "moderate"

class MockHealthMonitor:
    def __init__(self, global_health: float = 0.7):
        self._global_health = global_health

    def get_global_health_score(self, context: DecisionContext) -> float:
        if context.health_scores and "global_health" in context.health_scores:
            return context.health_scores["global_health"]
        return self._global_health

class MockWeightDistribution:
    def get_weight_distribution(self, context: DecisionContext) -> Dict[str, float]:
        return context.weight_distribution if context.weight_distribution else {"default_weight": 1.0}

class MockCouncilVerdict:
    def __init__(self, verdict: Optional[str] = "PROCEED"):
        self._verdict = verdict

    def get_verdict(self, context: DecisionContext) -> Optional[str]:
        return context.council_verdict if context.council_verdict else self._verdict

class MockMetaIntelligence:
    def __init__(self, verdict: Optional[str] = "PROCEED"):
        self._verdict = verdict

    def get_verdict(self, context: DecisionContext) -> Optional[str]:
        return context.meta_verdict if context.meta_verdict else self._verdict

class MockPolicyEngine:
    def __init__(self, verdict: Optional[str] = "APPROVED"):
        self._verdict = verdict

    def get_verdict(self, context: DecisionContext) -> Optional[str]:
        return context.policy_verdict if context.policy_verdict else self._verdict


# --- Mock methods for setting mock states --- 
def set_quality(self, quality: str): self._quality = quality
MockWorldModel.set_quality = set_quality
def set_consistency(self, consistency: str): self._consistency = consistency
MockSkillsEngine.set_consistency = set_consistency
def set_conflicts(self, conflicts: str): self._conflicts = conflicts
MockEvidenceGraph.set_conflicts = set_conflicts
def set_global_health(self, health: float): self._global_health = health
MockHealthMonitor.set_global_health = set_global_health
def set_uncertainty_level(self, level: float): self._uncertainty_level = level
MockWorkingMemory.set_uncertainty_level = set_uncertainty_level
def set_verdict(self, verdict: str): self._verdict = verdict
MockCouncilVerdict.set_verdict = set_verdict
MockMetaIntelligence.set_verdict = set_verdict
MockPolicyEngine.set_verdict = set_verdict

def set_raise_exception(self, raise_exception: bool): self._raise_exception = raise_exception
MockWorldModel.set_raise_exception = set_raise_exception
MockSkillsEngine.set_raise_exception = set_raise_exception
MockEvidenceGraph.set_raise_exception = set_raise_exception


# --- Test Class for Decision Engine V10 --- 

class TestDecisionEngineV10(unittest.TestCase):

    def setUp(self):
        """Set up common resources for tests."""
        # Common mocks, will be overridden in specific tests for scenario control
        self.mock_wm = MockWorkingMemory(uncertainty_level=0.5)
        self.mock_trace = MockDecisionTrace(trace_hash="test_trace_hash_default")
        self.mock_world_model = MockWorldModel(quality="medium")
        self.mock_skills_engine = MockSkillsEngine(consistency="medium")
        self.mock_evidence_graph = MockEvidenceGraph(conflicts="none")
        self.mock_health_monitor = MockHealthMonitor(global_health=0.7)
        self.mock_weight_dist = MockWeightDistribution()
        self.mock_council_verdict = MockCouncilVerdict(verdict="PROCEED")
        self.mock_meta_intelligence = MockMetaIntelligence(verdict="PROCEED")
        self.mock_policy_engine = MockPolicyEngine(verdict="APPROVED")

        # Default DecisionContext
        self.default_context = DecisionContext(
            cycle_id="test_cycle_default",
            timestamp=datetime.now(timezone.utc),
            world_model=MockWorldModel(),
            skill_opinions={},
            evidence_graph=MockEvidenceGraph(),
            health_scores={'global_health': 0.7},
            weight_distribution={},
            council_verdict="PROCEED",
            meta_verdict="PROCEED",
            policy_verdict="APPROVED",
            working_memory=MockWorkingMemory(),
            decision_trace=MockDecisionTrace()
        )

        # Instantiate DecisionEngineV10 with mocks
        self.decision_engine = DecisionEngineV10(
            world_model=self.mock_world_model, 
            skill_opinions=self.mock_skills_engine, 
            evidence_graph=self.mock_evidence_graph, 
            health_scores=self.mock_health_monitor, 
            weight_distribution=self.mock_weight_dist, 
            council_verdict=self.mock_council_verdict, 
            meta_intelligence=self.mock_meta_intelligence, 
            policy_engine=self.mock_policy_engine, 
            working_memory=self.mock_wm, 
            decision_trace=self.mock_trace
        )

    # --- Block 1, 2, 3, 4, 5: Assumed implemented from previous steps ---

    # --- Block 6: Consistency Tests ---

    def test_consistency_deterministic_output(self):
        """Test that identical inputs yield identical DecisionResults and trace hashes."""
        now = datetime.now(timezone.utc)
        trace_hash_val = "deterministic_trace_hash_123"

        # Create a controlled DecisionContext
        ctx1 = DecisionContext(
            cycle_id="consistency_test_cycle",
            timestamp=now,
            meta_verdict="PROCEED",
            policy_verdict="APPROVED",
            world_model=MockWorldModel(quality="high", quality_reasoning=["WM high quality"]),
            skill_opinions=MockSkillsEngine(consistency="high", cons_reasoning=["Skills agree high."]),
            evidence_graph=MockEvidenceGraph(conflicts="none"),
            health_scores={'global_health': 0.9},
            working_memory=MockWorkingMemory(uncertainty_level=0.1),
            council_verdict="PROCEED",
            decision_trace=MockDecisionTrace(trace_hash=trace_hash_val)
        )
        # Manually compute and set hash for deterministic context hash
        ctx1_dict = ctx1.to_dict()
        # Ensure mock WM and Trace are properly dictified if they have to_dict methods
        ctx1_dict['working_memory'] = {'uncertainty_level': 0.1} # Mock WorkingMemory to_dict
        ctx1_dict['decision_trace'] = {'hash': trace_hash_val} # Mock DecisionTrace to_dict
        ctx1_dict['timestamp'] = now.isoformat()
        # Manually set the data that compute_hash relies on, ensuring no dynamic aspects interfere
        ctx1_dict['world_model'] = {'quality': 'high', 'reasoning': ['WM high quality'], 'evidence': ['wm_data'], 'modules': ['WorldModel']}
        ctx1_dict['skill_opinions'] = {'consistency': 'high', 'reasoning': ['Skills agree high.'], 'evidence': ['skill_data'], 'modules': ['SkillsEngine']}
        ctx1_dict['evidence_graph'] = {'conflicts': 'none', 'reasoning': ['EvidenceGraph data is available.'], 'evidence': ['evidence_graph_data'], 'modules': ['EvidenceGraph']}
        ctx1_dict['health_scores'] = {'global_health': 0.9}
        ctx1_dict['council_verdict'] = 'PROCEED'
        ctx1_dict['meta_verdict'] = 'PROCEED'
        ctx1_dict['policy_verdict'] = 'APPROVED'
        
        computed_hash = DecisionContext.compute_hash(DecisionContext(**ctx1_dict))
        ctx1_dict['context_hash'] = computed_hash
        ctx1 = DecisionContext(**ctx1_dict)

        # --- First call to make_decision --- 
        # Need to ensure mocks are set up correctly for the engine to use them
        self.mock_wm.set_uncertainty_level(0.1)
        self.mock_world_model.set_quality("high")
        self.mock_skills_engine.set_consistency("high")
        self.mock_evidence_graph.set_conflicts("none")
        self.mock_health_monitor = MockHealthMonitor(global_health=0.9)
        self.mock_meta_intelligence.set_verdict("PROCEED")
        self.mock_policy_engine.set_verdict("APPROVED")
        self.mock_council_verdict.set_verdict("PROCEED")
        self.mock_trace.set_trace_hash(trace_hash_val)

        # Re-instantiate engine with controlled mocks for this test
        engine1 = DecisionEngineV10(
            world_model=self.mock_world_model, 
            skill_opinions=self.mock_skills_engine, 
            evidence_graph=self.mock_evidence_graph, 
            health_scores=self.mock_health_monitor, 
            weight_distribution=self.mock_weight_dist, 
            council_verdict=self.mock_council_verdict, 
            meta_intelligence=self.mock_meta_intelligence, 
            policy_engine=self.mock_policy_engine, 
            working_memory=self.mock_wm, 
            decision_trace=self.mock_trace
        )
        dr1 = engine1.make_decision(ctx1)

        # --- Second call to make_decision with identical context ---
        # Re-create mocks and context for the second call to ensure identical state
        now2 = datetime.now(timezone.utc) # Use same time for identical input for timestamp
        trace_hash_val2 = "deterministic_trace_hash_123"

        wm2 = MockWorkingMemory(uncertainty_level=0.1)
        trace2 = MockDecisionTrace(trace_hash=trace_hash_val2)
        wm2.set_uncertainty_level(0.1)
        trace2.set_trace_hash(trace_hash_val)

        ctx2 = DecisionContext(
            cycle_id="consistency_test_cycle", # Identical cycle_id
            timestamp=now, # Identical timestamp
            meta_verdict="PROCEED",
            policy_verdict="APPROVED",
            world_model=MockWorldModel(quality="high", quality_reasoning=["WM high quality"]),
            skill_opinions=MockSkillsEngine(consistency="high", cons_reasoning=["Skills agree high."]),
            evidence_graph=MockEvidenceGraph(conflicts="none"),
            health_scores={'global_health': 0.9},
            working_memory=wm2,
            council_verdict="PROCEED",
            decision_trace=trace2
        )
        ctx2_dict = ctx2.to_dict()
        ctx2_dict['working_memory'] = {'uncertainty_level': 0.1}
        ctx2_dict['decision_trace'] = {'hash': trace_hash_val}
        ctx2_dict['timestamp'] = now.isoformat()
        ctx2_dict['world_model'] = {'quality': 'high', 'reasoning': ['WM high quality'], 'evidence': ['wm_data'], 'modules': ['WorldModel']}
        ctx2_dict['skill_opinions'] = {'consistency': 'high', 'reasoning': ['Skills agree high.'], 'evidence': ['skill_data'], 'modules': ['SkillsEngine']}
        ctx2_dict['evidence_graph'] = {'conflicts': 'none', 'reasoning': ['EvidenceGraph data is available.'], 'evidence': ['evidence_graph_data'], 'modules': ['EvidenceGraph']}
        ctx2_dict['health_scores'] = {'global_health': 0.9}
        ctx2_dict['council_verdict'] = 'PROCEED'
        ctx2_dict['meta_verdict'] = 'PROCEED'
        ctx2_dict['policy_verdict'] = 'APPROVED'

        computed_hash2 = DecisionContext.compute_hash(DecisionContext(**ctx2_dict))
        ctx2_dict['context_hash'] = computed_hash2
        ctx2 = DecisionContext(**ctx2_dict)

        # Re-instantiate engine with controlled mocks for this test
        self.mock_wm = wm2 # Update mocks
        self.mock_trace = trace2
        self.mock_world_model = MockWorldModel(quality="high")
        self.mock_skills_engine = MockSkillsEngine(consistency="high")
        self.mock_evidence_graph = MockEvidenceGraph(conflicts="none")
        self.mock_health_monitor = MockHealthMonitor(global_health=0.9)
        self.mock_meta_intelligence.set_verdict("PROCEED")
        self.mock_policy_engine.set_verdict("APPROVED")
        self.mock_council_verdict.set_verdict("PROCEED")

        engine2 = DecisionEngineV10(
            world_model=self.mock_world_model, 
            skill_opinions=self.mock_skills_engine, 
            evidence_graph=self.mock_evidence_graph, 
            health_scores=self.mock_health_monitor, 
            weight_distribution=self.mock_weight_dist, 
            council_verdict=self.mock_council_verdict, 
            meta_intelligence=self.mock_meta_intelligence, 
            policy_engine=self.mock_policy_engine, 
            working_memory=self.mock_wm, 
            decision_trace=self.mock_trace
        )
        dr2 = engine2.make_decision(ctx2)

        # Assertions: Compare the DecisionResults
        self.assertEqual(dr1.decision, dr2.decision)
        self.assertEqual(dr1.confidence, dr2.confidence)
        self.assertEqual(dr1.decision_score, dr2.decision_score)
        self.assertEqual(dr1.uncertainty, dr2.uncertainty)
        self.assertEqual(dr1.trace_hash, dr2.trace_hash)
        # created_at will differ as it uses datetime.now() within _produce_result.
        # We are focusing on deterministic aspects like trace_hash and decision parameters.
        
        # Check that list contents are the same, ignoring order.
        self.assertCountEqual(dr1.reasoning, dr2.reasoning)
        self.assertCountEqual(dr1.blocking_reasons, dr2.blocking_reasons)
        self.assertCountEqual(dr1.supporting_reasons, dr2.supporting_reasons)
        self.assertCountEqual(dr1.evidence_used, dr2.evidence_used)
        self.assertCountEqual(dr1.modules_consulted, dr2.modules_consulted)

        # Explicitly check that the trace hash matches the computed hash from context
        self.assertEqual(dr1.trace_hash, ctx1.context_hash)
        self.assertEqual(dr2.trace_hash, ctx2.context_hash)

    def test_consistency_different_inputs_different_outputs(self):
        """Test that different inputs yield different DecisionResults."""
        now = datetime.now(timezone.utc)
        trace_hash_val1 = "trace_hash_1"
        trace_hash_val2 = "trace_hash_2"

        ctx1 = DecisionContext(
            cycle_id="consistency_diff_1",
            timestamp=now,
            meta_verdict="PROCEED", policy_verdict="APPROVED",
            world_model=MockWorldModel(quality="high"),
            skill_opinions=MockSkillsEngine(consistency="high"),
            evidence_graph=MockEvidenceGraph(conflicts="none"),
            health_scores={'global_health': 0.9},
            working_memory=MockWorkingMemory(uncertainty_level=0.1),
            council_verdict="PROCEED",
            decision_trace=MockDecisionTrace(trace_hash=trace_hash_val1)
        )
        # Ensure context hashes are computed
        ctx1_dict = ctx1.to_dict()
        computed_hash1 = DecisionContext.compute_hash(DecisionContext(**ctx1_dict))
        ctx1_dict['context_hash'] = computed_hash1
        ctx1 = DecisionContext(**ctx1_dict)

        dr1 = self.decision_engine.make_decision(ctx1)

        ctx2 = DecisionContext(
            cycle_id="consistency_diff_2", # Different cycle ID
            timestamp=now,
            meta_verdict="HOLD", # Different MetaVerdict
            policy_verdict="APPROVED",
            world_model=MockWorldModel(quality="medium"),
            skill_opinions=MockSkillsEngine(consistency="medium"),
            evidence_graph=MockEvidenceGraph(conflicts="moderate"),
            health_scores={'global_health': 0.7},
            working_memory=MockWorkingMemory(uncertainty_level=0.5),
            council_verdict="PROCEED",
            decision_trace=MockDecisionTrace(trace_hash=trace_hash_val2)
        )
        ctx2_dict = ctx2.to_dict()
        computed_hash2 = DecisionContext.compute_hash(DecisionContext(**ctx2_dict))
        ctx2_dict['context_hash'] = computed_hash2
        ctx2 = DecisionContext(**ctx2_dict)

        dr2 = self.decision_engine.make_decision(ctx2)

        # Assert that the results are different due to different inputs
        self.assertNotEqual(dr1.decision, dr2.decision)
        self.assertNotEqual(dr1.confidence, dr2.confidence)
        self.assertNotEqual(dr1.decision_score, dr2.decision_score)
        self.assertNotEqual(dr1.uncertainty, dr2.uncertainty)
        self.assertNotEqual(dr1.trace_hash, dr2.trace_hash)

    def test_consistency_deterministic_with_errors(self):
        """Test that failure handling is deterministic."""
        now = datetime.now(timezone.utc)
        trace_hash_val = "deterministic_error_trace"

        # --- First run with error ---
        failing_wm = MockWorkingMemory(uncertainty_level=0.5)
        failing_wm.get_uncertainty_level = lambda: 1/0

        ctx1 = DecisionContext(
            cycle_id="consistency_err_cycle_1",
            timestamp=now,
            meta_verdict="PROCEED", policy_verdict="APPROVED",
            working_memory=failing_wm,
            decision_trace=MockDecisionTrace(trace_hash=trace_hash_val),
            context_hash=hashlib.sha256(
                f"consistency_err_cycle_1|working_memory_error".encode()
            ).hexdigest(),
        )

        engine1 = DecisionEngineV10(
            world_model=MockWorldModel(),
            skill_opinions=MockSkillsEngine(),
            evidence_graph=MockEvidenceGraph(),
            health_scores=MockHealthMonitor(),
            weight_distribution=MockWeightDistribution(),
            council_verdict=MockCouncilVerdict(),
            meta_intelligence=MockMetaIntelligence(),
            policy_engine=MockPolicyEngine(),
            working_memory=failing_wm,
            decision_trace=MockDecisionTrace(trace_hash=trace_hash_val)
        )
        dr1 = engine1.make_decision(ctx1)
        self.assertEqual(dr1.decision, DecisionStatus.HOLD)
        self.assertTrue(any("Error getting uncertainty" in r for r in dr1.blocking_reasons))
        self.assertIn("WorkingMemory", dr1.modules_consulted)

        # --- Second run with the exact same error condition ---
        failing_wm2 = MockWorkingMemory(uncertainty_level=0.5)
        failing_wm2.get_uncertainty_level = lambda: 1/0

        ctx2 = DecisionContext(
            cycle_id="consistency_err_cycle_1",
            timestamp=now,
            meta_verdict="PROCEED", policy_verdict="APPROVED",
            working_memory=failing_wm2,
            decision_trace=MockDecisionTrace(trace_hash=trace_hash_val),
            context_hash=hashlib.sha256(
                f"consistency_err_cycle_1|working_memory_error".encode()
            ).hexdigest(),
        )

        engine2 = DecisionEngineV10(
            world_model=MockWorldModel(),
            skill_opinions=MockSkillsEngine(),
            evidence_graph=MockEvidenceGraph(),
            health_scores=MockHealthMonitor(),
            weight_distribution=MockWeightDistribution(),
            council_verdict=MockCouncilVerdict(),
            meta_intelligence=MockMetaIntelligence(),
            policy_engine=MockPolicyEngine(),
            working_memory=failing_wm2, # Use the failing mock
            decision_trace=MockDecisionTrace(trace_hash=trace_hash_val)
        )
        dr2 = engine2.make_decision(ctx2)

        # Assert that the results are identical for the same error condition
        self.assertEqual(dr1.decision, dr2.decision)
        self.assertEqual(dr1.confidence, dr2.confidence)
        self.assertEqual(dr1.decision_score, dr2.decision_score)
        self.assertEqual(dr1.uncertainty, dr2.uncertainty)
        self.assertEqual(dr1.trace_hash, dr2.trace_hash)
        self.assertCountEqual(dr1.blocking_reasons, dr2.blocking_reasons)
        self.assertCountEqual(dr1.modules_consulted, dr2.modules_consulted)


if __name__ == '__main__':
    unittest.main()
