
import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from CORE.events.event_bus import EventBus

log = logging.getLogger(__name__)
from CORE.events.events import Event, EventTypes

from ENGINE.decision.decision_types import DecisionContext, DecisionResult, DecisionStatus
from ENGINE.decision.decision_config import (
    DEFAULT_CONFIDENCE,
    DEFAULT_DECISION_SCORE,
    DEFAULT_UNCERTAINTY,
    VERSION_ARCH, 
    VERSION_CONTRACTS
)

# Placeholder classes for components --- 
# These are mock implementations for demonstration purposes.
# In a real scenario, these would be imported from their respective modules.

class WorldModel:
    def evaluate_quality(self, context: DecisionContext) -> tuple[str, List[str], List[str], List[str]]: # quality: high/medium/low, reasoning, evidence, modules
        quality = "medium"
        reasoning = ["WorldModel data is available."]
        evidence = ["world_model_data"]
        modules = ["WorldModel"]

        if context.world_model and hasattr(context.world_model, 'get_stability'):
            try:
                stability = context.world_model.get_stability()
                if stability > 0.8:
                    quality = "high"
                    reasoning.append("WorldModel reports high stability.")
                    evidence.append("world_model_stability")
                elif stability < 0.5:
                    quality = "low"
                    reasoning.append("WorldModel reports low stability.")
            except Exception as e:
                log.error(f"Error evaluating WorldModel quality: {e}")
                reasoning.append(f"Error evaluating WorldModel: {e}")
                quality = "low"
        
        if context.health_scores:
            avg_health = sum(context.health_scores.values()) / len(context.health_scores) if context.health_scores else 0.0
            if avg_health < 0.7:
                reasoning.append(f"HealthMonitor indicates low global health ({avg_health:.2f}).")
                quality = "low"
            elif avg_health >= 0.9:
                 reasoning.append(f"HealthMonitor indicates high global health ({avg_health:.2f}).")
        
        if context.council_verdict:
            modules.append("CouncilVerdict")
            evidence.append("council_verdict")
            if context.council_verdict.lower() == "unfavorable":
                quality = "low"
                reasoning.append("Council Verdict is unfavorable.")
            elif context.council_verdict.lower() == "favorable":
                if quality == "high":
                    reasoning.append("Council Verdict is favorable.")
        
        return quality, reasoning, evidence, modules

class SkillsEngine:
    def evaluate_consistency(self, context: DecisionContext) -> tuple[str, List[str], List[str], List[str]]:
        consistency = "medium"
        reasoning = ["Skill opinions data is available."]
        evidence = ["skill_opinions_data"]
        modules = ["SkillsEngine"]

        if context.skill_opinions:
            try:
                opinions = context.skill_opinions.get_opinions() # Assuming method exists
                if opinions:
                    num_opinions = len(opinions)
                    approved_count = sum(1 for op in opinions if op.get("decision") == "APPROVED")
                    hold_count = sum(1 for op in opinions if op.get("decision") == "HOLD")
                    rejected_count = sum(1 for op in opinions if op.get("decision") == "REJECTED")
                    
                    agreement_level = approved_count / num_opinions if num_opinions else 0
                    disagreement_level = (hold_count + rejected_count) / num_opinions if num_opinions else 0
                    
                    if agreement_level > 0.8:
                        consistency = "high"
                        reasoning.append(f"High agreement among {num_opinions} skill opinions.")
                        evidence.append("high_skill_agreement")
                    elif agreement_level < 0.5 or disagreement_level > 0.4:
                        consistency = "inconsistent_critical"
                        reasoning.append(f"Significant disagreement/rejection among {num_opinions} skill opinions.")
                        evidence.append("low_skill_agreement")
                    else:
                        reasoning.append(f"Moderate agreement among {num_opinions} skill opinions.")
            except Exception as e:
                log.error(f"Error evaluating SkillOpinions consistency: {e}")
                reasoning.append(f"Error evaluating SkillOpinions consistency: {e}")
                consistency = "inconsistent_critical"
        
        if context.evidence_graph:
            try:
                conflicts_val, conf_reason, conf_evid, conf_mods = context.evidence_graph.evaluate_conflicts(context)
                if conflicts_val == "critical":
                    consistency = "inconsistent_critical"
                    reasoning.append(f"EvidenceGraph reported critical conflicts: {conf_reason[0]}")
                    evidence.append("evidence_graph_critical_conflicts")
                elif conflicts_val == "moderate":
                    if consistency != "inconsistent_critical":
                        consistency = "inconsistent_warning"
                    reasoning.append("EvidenceGraph reported moderate conflicts.")
                else: # none
                    reasoning.append("EvidenceGraph reported no critical/moderate conflicts.")
                
                evidence.extend(conf_evid)
                modules.extend(conf_mods)
            except Exception as e:
                log.error(f"Error evaluating EvidenceGraph conflicts: {e}")
                reasoning.append(f"Error evaluating EvidenceGraph conflicts: {e}")
                consistency = "inconsistent_critical"

        return consistency, reasoning, evidence, modules

class EvidenceGraph:
    def evaluate_conflicts(self, context: DecisionContext) -> tuple[str, List[str], List[str], List[str]]:
        conflicts = "none"
        reasoning = ["EvidenceGraph data is available."]
        evidence = ["evidence_graph_data"]
        modules = ["EvidenceGraph"]
        
        if context.evidence_graph and context.evidence_graph.has_critical_conflicts():
            conflicts = "critical"
            reasoning.append("EvidenceGraph found critical conflicts.")
            evidence.append("evidence_graph_critical_conflicts")
        elif context.evidence_graph and context.evidence_graph.has_moderate_conflicts():
            conflicts = "moderate"
            reasoning.append("EvidenceGraph found moderate conflicts.")
            evidence.append("evidence_graph_moderate_conflicts")
        else:
            reasoning.append("EvidenceGraph found no critical or moderate conflicts.")
        return conflicts, reasoning, evidence, modules
    
    def has_critical_conflicts(self) -> bool: return False # Mock implementation
    def has_moderate_conflicts(self) -> bool: return False # Mock implementation

class HealthMonitor:
    def get_global_health_score(self, context: DecisionContext) -> float:
        return context.health_scores.get("global_health", 0.7) if context.health_scores else 0.7

class WeightDistribution:
    def get_weight_distribution(self, context: DecisionContext) -> Dict[str, float]:
        return context.weight_distribution if context.weight_distribution else {}

class CouncilVerdict:
    def get_verdict(self, context: DecisionContext) -> Optional[str]:
        return context.council_verdict

class MetaIntelligence:
    def get_verdict(self, context: DecisionContext) -> Optional[str]:
        return context.meta_verdict

class PolicyEngine:
    def get_verdict(self, context: DecisionContext) -> Optional[str]:
        return context.policy_verdict

class WorkingMemory:
    def get_uncertainty_level(self) -> float:
        # Simulating uncertainty level from working memory
        return 0.5 # Default if not found

class DecisionTrace:
    def get_trace_hash(self) -> str:
        return "simulated_trace_hash_12345"

# --- End of Placeholder classes ---


class DecisionEngineV10:

    def __init__(self, 
                 world_model: WorldModel, 
                 skill_opinions: SkillsEngine, 
                 evidence_graph: EvidenceGraph, 
                 health_scores: HealthMonitor, 
                 weight_distribution: WeightDistribution, 
                 council_verdict: CouncilVerdict, 
                 meta_intelligence: MetaIntelligence, 
                 policy_engine: PolicyEngine, 
                 working_memory: WorkingMemory, 
                 decision_trace: DecisionTrace):
        self.world_model = world_model
        self.skill_opinions = skill_opinions
        self.evidence_graph = evidence_graph
        self.health_scores = health_scores
        self.weight_distribution = weight_distribution
        self.council_verdict = council_verdict
        self.meta_intelligence = meta_intelligence
        self.policy_engine = policy_engine
        self.working_memory = working_memory
        self.decision_trace = decision_trace
        
        self.modules_consulted: List[str] = []
        self.evidence_used: List[str] = []
        self.reasoning: List[str] = []
        self.blocking_reasons: List[str] = []
        self.supporting_reasons: List[str] = []

    def make_decision(self, context: DecisionContext) -> DecisionResult:
        # Reseta o estado do ciclo anterior — sem isso, reasoning/evidencias
        # se acumulam indefinidamente e corrompem o resultado de ciclos futuros.
        self.modules_consulted = []
        self.evidence_used = []
        self.reasoning = []
        self.blocking_reasons = []
        self.supporting_reasons = []

        start_time = datetime.now(timezone.utc)
        trace_hash = context.context_hash or hashlib.sha256(str(start_time).encode()).hexdigest()[:12]

        # Rule 1: Validate integrity of DecisionContext.
        if not self._validate_context(context):
            self.blocking_reasons.append("DecisionContext validation failed.")
            return self._produce_result(DecisionStatus.REJECTED, 0.0, 0.0, 1.0, trace_hash, start_time)

        # Rule 2: Verify MetaVerdict.
        meta_decision = self._get_meta_decision(context)
        if meta_decision == DecisionStatus.HOLD:
            self.reasoning.append("Meta Verdict is HOLD. Final decision is HOLD.")
            return self._produce_result(DecisionStatus.HOLD, 0.5, 0.5, 0.5, trace_hash, start_time)
        elif meta_decision == DecisionStatus.REJECTED:
            self.blocking_reasons.append("Meta Verdict is REJECTED. Final decision is REJECTED.")
            return self._produce_result(DecisionStatus.REJECTED, 0.1, 0.05, 0.2, trace_hash, start_time)

        # Rule 3: Verify PolicyVerdict.
        policy_decision = self._get_policy_decision(context)
        if policy_decision == DecisionStatus.REJECTED:
            self.blocking_reasons.append("Policy Verdict is REJECTED. Final decision is REJECTED.")
            return self._produce_result(DecisionStatus.REJECTED, 0.1, 0.05, 0.2, trace_hash, start_time)
        elif policy_decision == DecisionStatus.HOLD and meta_decision != DecisionStatus.REJECTED:
            self.reasoning.append("Policy Verdict is HOLD. Final decision is HOLD.")
            return self._produce_result(DecisionStatus.HOLD, 0.5, 0.5, 0.5, trace_hash, start_time)

        # If we reach here, Meta is PROCEED and Policy is APPROVED (or default).
        # Gather inputs for Rules 4-7.
        decision_inputs = self._gather_decision_inputs(context)

        # Apply Rules 4-8 and Matrix to determine final decision.
        final_decision, confidence, decision_score, uncertainty = self._apply_core_logic(context, decision_inputs)

        # Rule 9: Produce DecisionResult.
        return self._produce_result(
            final_decision, confidence, decision_score, uncertainty, trace_hash, start_time
        )

    def _validate_context(self, context: DecisionContext) -> bool:
        """Rule 1: Validate integrity of DecisionContext."""
        if not context.cycle_id:
            log.error("DecisionContext missing cycle_id.")
            self.blocking_reasons.append("DecisionContext missing cycle_id.")
            return False
        if not context.timestamp:
            log.error("DecisionContext missing timestamp.")
            self.blocking_reasons.append("DecisionContext missing timestamp.")
            return False
        
        # Check for essential engine components. Their absence is a critical issue.
        required_sources = [
            'world_model', 'skill_opinions', 'evidence_graph', 'health_scores',
            'weight_distribution', 'council_verdict', 'meta_intelligence', 'policy_engine',
            'working_memory', 'decision_trace'
        ]
        
        for source in required_sources:
            if getattr(self, source) is None:
                log.error(f"DecisionEngineV10 instance missing essential component: {source}.")
                self.blocking_reasons.append(f"DecisionEngineV10 missing essential component: {source}.")
                return False
            # Also check if the component provides expected methods (basic check)
            if not hasattr(getattr(self, source), 'evaluate_quality') and source == 'world_model':
                 log.warning(f"WorldModel component missing expected 'evaluate_quality' method.")
            # Add similar checks for other components if needed

        self.modules_consulted.append("DecisionContextValidator")
        self.evidence_used.append("DecisionContext integrity checks")
        return True

    def _get_meta_decision(self, context: DecisionContext) -> DecisionStatus:
        meta = context.meta_verdict
        if meta == "HOLD":
            self.reasoning.append("Meta Verdict is HOLD.")
            return DecisionStatus.HOLD
        elif meta == "REJECTED":
            self.blocking_reasons.append("Meta Verdict is REJECTED.")
            return DecisionStatus.REJECTED
        elif meta == "PROCEED":
            self.supporting_reasons.append("Meta Verdict is PROCEED.")
            return DecisionStatus.APPROVED
        else:
            self.reasoning.append(f"Meta Verdict is unknown or not specified: {meta}. Defaulting to HOLD.")
            return DecisionStatus.HOLD
            
    def _get_policy_decision(self, context: DecisionContext) -> DecisionStatus:
        policy = context.policy_verdict
        if policy == "BLOCKED":
            self.blocking_reasons.append("Policy Verdict is BLOCKED.")
            return DecisionStatus.REJECTED
        elif policy == "REJECTED":
            self.blocking_reasons.append("Policy Verdict is REJECTED.")
            return DecisionStatus.REJECTED
        elif policy == "APPROVED":
            self.supporting_reasons.append("Policy Verdict is APPROVED.")
            return DecisionStatus.APPROVED
        else:
            self.reasoning.append(f"Policy Verdict is unknown or not specified: {policy}. Defaulting to APPROVED.")
            return DecisionStatus.APPROVED

    def _gather_decision_inputs(self, context: DecisionContext) -> Dict[str, Any]:
        """Gathers inputs for Rules 4-8 from DecisionContext only."""
        inputs = {}

        inputs['meta_decision'] = self._get_meta_decision(context)
        inputs['policy_decision'] = self._get_policy_decision(context)

        if context.world_model:
            self.modules_consulted.append("WorldModel")
            self.evidence_used.append("world_model")
        if context.skill_opinions:
            self.modules_consulted.append("SkillsEngine")
            self.evidence_used.append("skill_opinions")
        if context.evidence_graph:
            self.modules_consulted.append("EvidenceGraph")
            self.evidence_used.append("evidence_graph")
        if context.health_scores:
            self.modules_consulted.append("HealthMonitor")
            self.evidence_used.append("health_scores")
        if context.weight_distribution:
            self.modules_consulted.append("WeightDistribution")
            self.evidence_used.append("weight_distribution")
        if context.council_verdict:
            self.modules_consulted.append("CouncilVerdict")
            self.evidence_used.append("council_verdict")

        quality = "medium"
        q_reasoning = []

        if context.health_scores:
            scores = [v for v in context.health_scores.values() if isinstance(v, (int, float))]
            if scores:
                avg_health = sum(scores) / len(scores)
                if avg_health < 0.7:
                    q_reasoning.append(f"HealthMonitor indicates low global health ({avg_health:.2f}).")
                    self.blocking_reasons.append(f"Global health score too low: {avg_health:.2f}")
                    quality = "low"
                elif avg_health >= 0.9:
                    q_reasoning.append(f"HealthMonitor indicates high global health ({avg_health:.2f}).")
                    quality = "high"

        inputs['global_quality'] = quality
        self.reasoning.extend(q_reasoning)

        consistency = "medium"
        cons_reasoning = []

        if context.council_verdict:
            cv = str(context.council_verdict).lower()
            if cv in ("favorable", "proceed", "approve", "approved"):
                consistency = "consistent"
                cons_reasoning.append("CouncilVerdict indicates consistency.")
            elif "conflict" in cv or "disagree" in cv:
                consistency = "inconsistent_warning"
                cons_reasoning.append("CouncilVerdict indicates inconsistency.")

        inputs['consistency'] = consistency
        self.reasoning.extend(cons_reasoning)

        uncertainty_level = "low"
        unc_reasoning = []

        if context.working_memory is not None:
            try:
                if hasattr(context.working_memory, 'get_uncertainty_level'):
                    wm_uncertainty = context.working_memory.get_uncertainty_level()
                elif isinstance(context.working_memory, dict):
                    wm_uncertainty = context.working_memory.get('uncertainty_level', 0.5)
                else:
                    wm_uncertainty = 0.5

                if wm_uncertainty > 0.7:
                    uncertainty_level = "high"
                    unc_reasoning.append(f"High uncertainty from Working Memory: {wm_uncertainty:.2f}")
                else:
                    unc_reasoning.append(f"Working Memory indicates low uncertainty ({wm_uncertainty:.2f}).")
                self.modules_consulted.append("WorkingMemory")
            except Exception as e:
                log.error(f"Error getting uncertainty from WorkingMemory: {e}")
                self.blocking_reasons.append(f"Error getting uncertainty from WorkingMemory: {e}")
                uncertainty_level = "high"
                self.modules_consulted.append("WorkingMemory")

        inputs['uncertainty_level'] = uncertainty_level
        self.reasoning.extend(unc_reasoning)

        conflicts_level = "none"
        if self.blocking_reasons:
            conflicts_level = "moderate"
            if any("critical" in r.lower() for r in self.blocking_reasons):
                conflicts_level = "critical"

        inputs['conflicts'] = conflicts_level
        return inputs

    def _apply_core_logic(self, context: DecisionContext, inputs: Dict[str, Any]) -> tuple[DecisionStatus, float, float, float]:
        """Applies Rules 4-8 and the Decision Matrix to derive the final decision."""

        decision = None
        confidence = DEFAULT_CONFIDENCE
        decision_score = DEFAULT_DECISION_SCORE
        uncertainty = DEFAULT_UNCERTAINTY

        meta = inputs.get('meta_decision', DecisionStatus.HOLD)
        policy = inputs.get('policy_decision', DecisionStatus.APPROVED)

        if meta == DecisionStatus.HOLD:
            decision = DecisionStatus.HOLD
            self.reasoning.append("Meta Verdict is HOLD. Final decision is HOLD.")
        elif meta == DecisionStatus.REJECTED:
            decision = DecisionStatus.REJECTED
            self.blocking_reasons.append("Meta Verdict is REJECTED. Final decision is REJECTED.")

        if policy == DecisionStatus.REJECTED:
            decision = DecisionStatus.REJECTED
            self.blocking_reasons.append("Policy Verdict is REJECTED. Final decision is REJECTED.")
        elif policy == DecisionStatus.HOLD and decision != DecisionStatus.REJECTED:
            decision = DecisionStatus.HOLD
            self.reasoning.append("Policy Verdict is HOLD. Final decision is HOLD.")

        if decision is not None:
            return decision, confidence, decision_score, uncertainty

        # --- Apply Matrix and Rules 4-8 for PROCEED/APPROVED path ---       
        quality = inputs.get('global_quality', 'medium')
        consistency = inputs.get('consistency', 'medium')
        uncertainty_level = inputs.get('uncertainty_level', 'low')
        conflicts = inputs.get('conflicts', 'none')

        # Apply Matrix Logic based on quality, consistency, uncertainty, and conflicts.
        if quality == 'high' and uncertainty_level == 'low' and consistency == 'consistent' and conflicts == 'none':
            decision = DecisionStatus.APPROVED
            confidence = 0.95
            decision_score = 0.98
            uncertainty = 0.05
            self.supporting_reasons.append("Matrix Match: High quality, low uncertainty, consistent, no critical conflicts.")
        elif uncertainty_level == 'high':
            decision = DecisionStatus.HOLD
            confidence = 0.5
            decision_score = 0.5
            uncertainty = 0.8
            self.reasoning.append("Matrix Application: High uncertainty detected. Decision set to HOLD.")
        elif conflicts == 'critical':
            decision = DecisionStatus.HOLD # Critical conflicts should lead to HOLD or REJECTED
            confidence = 0.3
            decision_score = 0.3
            uncertainty = 0.9
            self.blocking_reasons.append("Matrix Application: Critical conflicts detected. Decision set to HOLD.")
        elif conflicts == 'moderate':
            decision = DecisionStatus.HOLD
            confidence = 0.4
            decision_score = 0.4
            uncertainty = 0.7
            self.reasoning.append("Matrix Application: Moderate conflicts detected. Decision set to HOLD.")
        elif quality == 'low' or consistency == 'inconsistent_warning':
            decision = DecisionStatus.HOLD
            confidence = 0.4
            decision_score = 0.4
            uncertainty = 0.7
            self.reasoning.append(f"Matrix Application: Low quality ({quality}) or inconsistency ({consistency}). Decision set to HOLD.")
        else: # Default for other mixed conditions or medium values not explicitly handled
            decision = DecisionStatus.HOLD
            self.reasoning.append("Matrix Application: Mixed or moderate conditions, defaulting to HOLD.")
            confidence = 0.5
            decision_score = 0.5
            uncertainty = 0.5

        # Rule Principle of Uncertainty: In any situation of doubt relevant, HOLD.
        if decision == DecisionStatus.APPROVED and uncertainty > 0.7:
            decision = DecisionStatus.HOLD
            self.reasoning.append("Principle of Uncertainty: High doubt (>0.7) overrides APPROVED. Decision downgraded to HOLD.")
            # Re-adjust parameters for HOLD if downgraded
            confidence = max(0.4, confidence * 0.7)
            decision_score = max(0.4, decision_score * 0.7)
            uncertainty = min(0.7, uncertainty + 0.1)
        
        # Rule 7: Conflicts critical status overrides other decisions to REJECTED.
        if conflicts == 'critical' and decision != DecisionStatus.REJECTED:
             decision = DecisionStatus.REJECTED
             self.blocking_reasons.append("Matrix Rule: Critical conflicts force REJECTED decision.")
        elif conflicts == 'moderate' and decision == DecisionStatus.APPROVED:
             decision = DecisionStatus.HOLD
             self.reasoning.append("Matrix Rule: Moderate conflicts downgrade APPROVED decision to HOLD.")

        return decision, confidence, decision_score, uncertainty

    def _produce_result(
        self,
        decision: DecisionStatus,
        confidence: float,
        decision_score: float,
        uncertainty: float,
        trace_hash: str,
        start_time: datetime
    ) -> DecisionResult:
        """Helper to create a DecisionResult object, consolidating all collected data."""
        
        # Rule 8: Consolidate justifications. Filter out generic or empty reasons.
        final_reasoning = list(set(r for r in self.reasoning if r and "default" not in r.lower() and "placeholder" not in r.lower()))
        final_blocking_reasons = list(set(r for r in self.blocking_reasons if r and "default" not in r.lower() and "placeholder" not in r.lower()))
        final_supporting_reasons = list(set(r for r in self.supporting_reasons if r and "default" not in r.lower() and "placeholder" not in r.lower()))
        final_evidence = list(set(e for e in self.evidence_used if e))
        final_modules = list(set(m for m in self.modules_consulted if m))

        # Rule 9: Produce DecisionResult.
        if not trace_hash or trace_hash == "placeholder_hash":
            trace_hash = hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:12]

        # Adjust final parameters based on decision and reasons, ensuring they are within [0, 1] bounds.
        # These adjustments are heuristic and should be refined with actual data.
        if decision == DecisionStatus.APPROVED:
            if confidence < 0.8 or uncertainty > 0.3 or len(final_blocking_reasons) > 0 or len(final_reasoning) > 5 or len(final_supporting_reasons) < 3:
                decision = DecisionStatus.HOLD
                confidence *= 0.8
                decision_score *= 0.8
                uncertainty = min(0.5, uncertainty + 0.2)
                final_reasoning.append("Downgraded to HOLD due to caveats on APPROVED state.")
        elif decision == DecisionStatus.REJECTED:
            confidence = max(0.05, confidence * 0.2) 
            decision_score = max(0.01, decision_score * 0.1)
            uncertainty = min(0.5, uncertainty + 0.3)
        else: # HOLD
            confidence = max(0.4, confidence * 0.7)
            decision_score = max(0.4, decision_score * 0.7)
            uncertainty = min(0.7, uncertainty + 0.1)

        # Re-apply Principle of Uncertainty if it wasn't already handled.
        if decision == DecisionStatus.APPROVED and uncertainty > 0.7:
            decision = DecisionStatus.HOLD
            final_reasoning.append("Principle of Uncertainty: High doubt (>0.7) resulted in HOLD decision.")
            # Re-adjust parameters for HOLD
            confidence = max(0.4, confidence * 0.7)
            decision_score = max(0.4, decision_score * 0.7)
            uncertainty = min(0.7, uncertainty + 0.1)

        # Ensure final parameters are within reasonable bounds [0, 1].
        confidence = max(0.0, min(confidence, 1.0))
        decision_score = max(0.0, min(decision_score, 1.0))
        uncertainty = max(0.0, min(uncertainty, 1.0))

        return DecisionResult(
            decision=decision,
            confidence=confidence,
            decision_score=decision_score,
            uncertainty=uncertainty,
            reasoning=final_reasoning,
            blocking_reasons=final_blocking_reasons,
            supporting_reasons=final_supporting_reasons,
            evidence_used=final_evidence,
            modules_consulted=final_modules,
            trace_hash=trace_hash,
            created_at=datetime.now(timezone.utc),
            version_arch=VERSION_ARCH, 
            version_contracts=VERSION_CONTRACTS
        )

