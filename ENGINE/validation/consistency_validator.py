"""
DecisionConsistencyValidator — Validador de Coerencia do Motor de Decisao.

Executado imediatamente antes do Telegram.
Garante que todos os componentes do sinal contam a mesma historia.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple

from ENGINE.scanner.scanner_types import (
    SignalClassification, SignalDirection, PatternType,
)
from ENGINE.decision.signal_decision import SignalDecision

log = logging.getLogger(__name__)


@dataclass
class ConsistencyReport:
    passed: bool = True
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    critical: List[str] = field(default_factory=list)

    def add_violation(self, rule: str, detail: str):
        self.passed = False
        self.violations.append(f"[{rule}] {detail}")

    def add_warning(self, rule: str, detail: str):
        self.warnings.append(f"[{rule}] {detail}")

    def add_critical(self, rule: str, detail: str):
        self.passed = False
        self.critical.append(f"[CRITICAL][{rule}] {detail}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": self.violations,
            "warnings": self.warnings,
            "critical": self.critical,
        }


class DecisionConsistencyValidator:

    def validate(self, sd: SignalDecision) -> ConsistencyReport:
        report = ConsistencyReport()

        self._check_score_conviction_coherence(sd, report)
        self._check_classification_integrity(sd, report)
        self._check_flow_timing_alignment(sd, report)
        self._check_structural_consistency(sd, report)
        self._check_momentum_trend_alignment(sd, report)
        self._check_risk_reward_quality(sd, report)
        self._check_kalman_alignment(sd, report)
        self._check_entry_zone_consistency(sd, report)
        self._check_no_contradictory_messages(sd, report)

        return report

    def _check_score_conviction_coherence(self, sd: SignalDecision, report: ConsistencyReport):
        q = sd.quality
        c = sd.quality_score
        conv = getattr(sd, 'conviction_ok', False)
        conv_val = sd.institutional_score

        for score_name, score_val in [("quality", q), ("quality_score", c)]:
            if score_val < 0 or score_val > 1.0:
                report.add_violation(
                    "SCORE_RANGE",
                    f"{score_name}={score_val:.4f} fora do range [0, 1]"
                )

        if q >= 0.80 and conv_val < 0.50:
            report.add_violation(
                "SCORE_CONVICTION_GAP",
                f"quality={q:.2f} mas conviction={conv_val:.2f} — gap > 0.30"
            )

        if conv_val >= 0.80:
            if q < 0.65:
                report.add_violation(
                    "HIGH_CONVICTION_LOW_QUALITY",
                    f"conviction={conv_val:.2f} mas quality={q:.2f} — incoerente"
                )

    def _check_classification_integrity(self, sd: SignalDecision, report: ConsistencyReport):
        q = sd.quality
        cls_label = getattr(sd, 'classification_label', 'reprovado').lower()
        inv_score = sd.institutional_score
        flow = getattr(sd, 'flow_ok', False)
        conv = getattr(sd, 'conviction_ok', False)

        if cls_label == "ouro":
            if q < 0.70:
                report.add_violation(
                    "CLASSIFICATION_MISMATCH",
                    f"Ouro mas quality={q:.2f} < 0.70"
                )
            if inv_score < 0.65:
                report.add_violation(
                    "CLASSIFICATION_MISMATCH",
                    f"Ouro mas institutional={inv_score:.2f} < 0.65"
                )
            if not conv:
                report.add_warning(
                    "CLASSIFICATION_WEAK",
                    "Ouro mas conviction_ok=False"
                )

        elif cls_label == "prata":
            if q < 0.60:
                report.add_violation(
                    "CLASSIFICATION_MISMATCH",
                    f"Prata mas quality={q:.2f} < 0.60"
                )
            if inv_score < 0.55:
                report.add_warning(
                    "CLASSIFICATION_WEAK",
                    f"Prata mas institutional={inv_score:.2f} < 0.55"
                )

        elif cls_label == "bronze":
            if q >= 0.85 and inv_score >= 0.80 and flow and conv:
                report.add_warning(
                    "CLASSIFICATION_UNDERRATED",
                    f"Bronze com quality={q:.2f}, institutional={inv_score:.2f} — pode ser Prata+"
                )

    def _check_flow_timing_alignment(self, sd: SignalDecision, report: ConsistencyReport):
        flow_ok = getattr(sd, 'flow_ok', False)
        timing_ok = getattr(sd, 'timing_ok', False)
        approved = sd.approved

        if approved and not flow_ok:
            report.add_violation(
                "APPROVED_NO_FLOW",
                "Signal approved mas flow_ok=False"
            )
        if approved and not timing_ok:
            report.add_violation(
                "APPROVED_NO_TIMING",
                "Signal approved mas timing_ok=False"
            )

    def _check_structural_consistency(self, sd: SignalDecision, report: ConsistencyReport):
        bos_count = sd.bos
        choch_count = sd.choch
        struct_ok = sd.structure_ok

        if bos_count == 0 and choch_count == 0 and struct_ok:
            report.add_warning(
                "STRUCTURE_NO_BREAK",
                "structure_ok=True mas sem BOS ou CHOCH"
            )

        has_inv_patterns = (
            sd.institutional_score > 0.60 or
            sd.structural_score > 0.55
        )
        has_no_break_patterns = bos_count == 0 and choch_count == 0

        if has_inv_patterns and has_no_break_patterns:
            report.add_warning(
                "INSTITUTIONAL_NO_PATTERN",
                f"institutional={sd.institutional_score:.2f} mas sem BOS/CHOCH"
            )

    def _check_momentum_trend_alignment(self, sd: SignalDecision, report: ConsistencyReport):
        trend_ok = sd.trend_ok
        rvol_ok = getattr(sd, 'rvol_ok', False)
        adx_ok = getattr(sd, 'adx_ok', False)

        if trend_ok and not rvol_ok:
            report.add_violation(
                "TREND_OK_NO_RVOL",
                "trend_ok=True mas rvol_ok=False"
            )

        if trend_ok and not adx_ok:
            report.add_violation(
                "TREND_OK_NO_ADX",
                "trend_ok=True mas adx_ok=False"
            )

    def _check_risk_reward_quality(self, sd: SignalDecision, report: ConsistencyReport):
        rr = sd.risk_reward
        approval_reason = sd.reject_reason or ""

        if "RR" in approval_reason and rr > 1.0:
            report.add_violation(
                "RR_MISMATCH",
                f"Rejeitado por RR mas rr={rr:.2f} > 1.0"
            )

    def _check_kalman_alignment(self, sd: SignalDecision, report: ConsistencyReport):
        kalman_dir = getattr(sd, 'kalman_direction', 'UNKNOWN')
        kalman_conf = getattr(sd, 'kalman_confidence', 0.0)
        signal_dir = sd.direction.lower() if sd.direction else ""
        approved = sd.approved

        if approved and kalman_dir == "REVERSAL" and kalman_conf > 0.6:
            report.add_warning(
                "KALMAN_REVERSAL_APPROVED",
                f"Kalman em reversao (conf={kalman_conf:.2f}) mas signal aprovado"
            )

        if approved and kalman_dir == "SIDE" and kalman_conf > 0.7:
            report.add_warning(
                "KALMAN_SIDE_APPROVED",
                "Kalman lateral mas signal aprovado"
            )

    def _check_entry_zone_consistency(self, sd: SignalDecision, report: ConsistencyReport):
        entry_zone_ok = sd.entry_zone_ok
        entry_score_ok = sd.entry_score_ok
        entry_score = sd.entry_score

        if entry_zone_ok and not entry_score_ok:
            report.add_violation(
                "ENTRY_ZONE_INCONSISTENT",
                f"entry_zone_ok=True mas entry_score_ok=False (score={entry_score:.2f})"
            )

        if entry_score_ok and not entry_zone_ok:
            report.add_violation(
                "ENTRY_ZONE_INCONSISTENT",
                f"entry_score_ok=True mas entry_zone_ok=False (score={entry_score:.2f})"
            )

    def _check_no_contradictory_messages(self, sd: SignalDecision, report: ConsistencyReport):
        explanations = []
        if sd.reject_reason:
            explanations.append(sd.reject_reason.lower())

        contradictory_pairs = [
            ("aprovado", "rejeitado"),
            ("estrutura insuficiente", "estrutura forte"),
            ("fluxo insuficiente", "fluxo favoravel"),
            ("timing insuficiente", "timing excelente"),
            ("risco elevado", "risco baixo"),
            ("momentum fraco", "momentum forte"),
        ]

        for a, b in contradictory_pairs:
            has_a = any(a in e for e in explanations)
            has_b = any(b in e for e in explanations)
            if has_a and has_b:
                report.add_violation(
                    "CONTRADICTORY_MESSAGE",
                    f"Mensagens conflitantes: '{a}' e '{b}'"
                )


def validate_decision(sd: SignalDecision) -> ConsistencyReport:
    validator = DecisionConsistencyValidator()
    return validator.validate(sd)


def validate_and_block(sd: SignalDecision) -> Tuple[bool, ConsistencyReport]:
    """Validate and return (should_block, report)."""
    report = validate_decision(sd)

    if report.critical or report.violations:
        log.error(
            "CONSISTENCY BLOCK [%s] %s: %d violations, %d critical",
            getattr(sd, 'trace_id', '?'),
            getattr(sd, 'symbol', '?'),
            len(report.violations),
            len(report.critical),
        )
        for v in report.violations:
            log.error("  VIOLATION: %s", v)
        for c in report.critical:
            log.error("  CRITICAL: %s", c)
        return True, report

    if report.warnings:
        for w in report.warnings:
            log.warning("  WARNING: %s", w)

    return False, report
