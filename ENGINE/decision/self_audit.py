import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .signal_decision import SignalDecision
from ENGINE.scanner.scanner_types import Signal, PatternType
from ENGINE.scanner.scanner_config import (
    ENTRY_ZONE_SCORE_MIN, CONSENSUS_MINIMUM_SCORE,
    QUALITY_GATE_MIN_SCORE, QUALITY_GATE_CONFIDENCE_MIN,
    QUALITY_GATE_RISK_MAX, HARD_MIN_STRUCTURE_STRENGTH,
)

log = logging.getLogger(__name__)

FAIL_SAFE_DIR = "MEMORY/failsafe"


@dataclass
class AuditEntry:
    check: str
    passed: bool
    expected: str = ""
    actual: str = ""
    detail: str = ""


@dataclass
class SelfAuditResult:
    passed: bool
    trace_id: str
    pair: str
    direction: str
    entries: List[AuditEntry] = field(default_factory=list)
    block_reason: str = ""
    snapshot_path: str = ""
    timestamp: str = ""

    def to_report(self) -> str:
        lines = [
            "=" * 56,
            "SELF AUDIT REPORT",
            "=" * 56,
            "",
            f"Trace ID:      {self.trace_id}",
            f"Pair:          {self.pair}",
            f"Direction:     {self.direction}",
            f"Timestamp:     {self.timestamp}",
            f"Result:        {'PASS' if self.passed else 'BLOCKED'}",
            "",
        ]
        if not self.passed:
            lines.append(f"Block Reason:  {self.block_reason}")
            if self.snapshot_path:
                lines.append(f"Snapshot:      {self.snapshot_path}")
            lines.append("")
        lines.append("Checks:")
        lines.append("-" * 56)
        for e in self.entries:
            icon = "\u2705" if e.passed else "\u274c"
            lines.append(f"  {icon} {e.check}")
            if not e.passed:
                lines.append(f"       Expected: {e.expected}")
                lines.append(f"       Actual:   {e.actual}")
                if e.detail:
                    lines.append(f"       Detail:   {e.detail}")
        lines.append("-" * 56)
        return "\n".join(lines)


class SelfAuditEngine:

    @staticmethod
    def audit(
        dr: SignalDecision,
        signal: Optional[Signal] = None,
    ) -> SelfAuditResult:
        entries: List[AuditEntry] = []
        trace_id = dr.trace_id or dr.decision_id
        pair = dr.symbol
        direction = dr.direction
        now_iso = datetime.now(timezone.utc).isoformat()

        if dr.approved:
            entries.append(SelfAuditEngine._check(
                "market_ok", dr.market_ok, True, "market_ok == True",
            ))
            entries.append(SelfAuditEngine._check(
                "trend_ok", dr.trend_ok, True, "trend_ok == True",
            ))
            entries.append(SelfAuditEngine._check(
                "structure_ok", dr.structure_ok, True, "structure_ok == True",
            ))
            entries.append(SelfAuditEngine._check(
                "entry_zone_ok", dr.entry_zone_ok, True, "entry_zone_ok == True",
            ))
            entries.append(SelfAuditEngine._check(
                "entry_score_ok", dr.entry_score_ok, True, "entry_score_ok == True",
            ))
            entries.append(SelfAuditEngine._check(
                "consensus_ok", dr.consensus_ok, True, "consensus_ok == True",
            ))
            entries.append(SelfAuditEngine._check(
                "quality_ok", dr.quality_ok, True, "quality_ok == True",
            ))
            entries.append(SelfAuditEngine._check(
                "confidence_ok", dr.confidence_ok, True, "confidence_ok == True",
            ))
            entries.append(SelfAuditEngine._check(
                "risk_ok", dr.risk_ok, True, "risk_ok == True",
            ))
            entries.append(SelfAuditEngine._check(
                "institutional_ok", dr.institutional_ok, True, "institutional_ok == True",
            ))
            entries.append(SelfAuditEngine._check(
                "selected_order_block != empty",
                bool(dr.selected_order_block and dr.selected_order_block != "none"),
                True, "selected_order_block deve ter valor",
            ))

            if signal:
                has_ob = any(p.type == PatternType.ORDER_BLOCK for p in signal.patterns)
                has_fvg = any(p.type == PatternType.FVG for p in signal.patterns)
                entries.append(SelfAuditEngine._check(
                    "has_ob_or_fvg", has_ob or has_fvg, True,
                    "sinal aprovado deve ter OB ou FVG",
                ))

                sig_dir = str(signal.direction.value) if hasattr(signal.direction, 'value') else str(signal.direction)
                entries.append(SelfAuditEngine._check(
                    "direction_consistent", dr.direction.lower() == sig_dir.lower(), dr.direction, sig_dir,
                ))

                if signal.signal_id:
                    entries.append(SelfAuditEngine._check(
                        "signal_id_match",
                        dr.signal_id == signal.signal_id,
                        signal.signal_id,
                        dr.signal_id,
                    ))

        else:
            any_filter_false = not dr.market_ok
            if dr.market_ok:
                any_filter_false = any_filter_false or not dr.trend_ok
            if dr.trend_ok:
                any_filter_false = any_filter_false or not dr.structure_ok
            if dr.structure_ok:
                any_filter_false = any_filter_false or not dr.entry_zone_ok
            if dr.entry_zone_ok:
                any_filter_false = any_filter_false or not dr.entry_score_ok
            if dr.entry_score_ok:
                any_filter_false = any_filter_false or not dr.consensus_ok
            if dr.consensus_ok:
                any_filter_false = any_filter_false or not dr.quality_ok
            if dr.quality_ok:
                any_filter_false = any_filter_false or not dr.confidence_ok
            if dr.confidence_ok:
                any_filter_false = any_filter_false or not dr.risk_ok
            if dr.risk_ok:
                any_filter_false = any_filter_false or not dr.institutional_ok
            entries.append(AuditEntry(
                check="rejected_has_at_least_one_false_filter",
                passed=any_filter_false,
                expected="pelo menos um filtro False",
                actual=f"market={dr.market_ok} trend={dr.trend_ok} struct={dr.structure_ok} "
                       f"entry_zone={dr.entry_zone_ok} entry_score={dr.entry_score_ok} "
                       f"consensus={dr.consensus_ok} quality={dr.quality_ok} "
                       f"conf={dr.confidence_ok} risk={dr.risk_ok} inst={dr.institutional_ok}",
            ))

        all_passed = all(e.passed for e in entries)
        block_reason = ""
        snapshot_path = ""

        if not all_passed:
            failed = [e for e in entries if not e.passed]
            block_reason = "; ".join(f"{e.check}: esperado={e.expected}, actual={e.actual}" for e in failed)
            snapshot_path = SelfAuditEngine._save_snapshot(dr, entries, signal)
            log.critical(
                "SELF-AUDIT BLOCKED [%s] %s %s | %s | snapshot=%s",
                trace_id, pair, direction, block_reason, snapshot_path,
            )

        return SelfAuditResult(
            passed=all_passed,
            trace_id=trace_id,
            pair=pair,
            direction=direction,
            entries=entries,
            block_reason=block_reason,
            snapshot_path=snapshot_path,
            timestamp=now_iso,
        )

    @staticmethod
    def _check(
        name: str, condition: bool, expected: Any, actual: Any, detail: str = "",
    ) -> AuditEntry:
        return AuditEntry(
            check=name,
            passed=bool(condition),
            expected=str(expected),
            actual=str(actual),
            detail=detail,
        )

    @staticmethod
    def _save_snapshot(
        dr: SignalDecision,
        entries: List[AuditEntry],
        signal: Optional[Signal] = None,
    ) -> str:
        os.makedirs(FAIL_SAFE_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        trace = dr.trace_id or "notrace"
        filename = f"audit_{trace}_{ts}.json"
        filepath = os.path.join(FAIL_SAFE_DIR, filename)

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace,
            "pair": dr.symbol,
            "direction": dr.direction,
            "approved": dr.approved,
            "reject_reason": dr.reject_reason,
            "decision_result": dr.to_dict(),
            "audit_entries": [asdict(e) for e in entries],
        }
        if signal:
            snapshot["signal_ticker"] = signal.ticker
            snapshot["signal_timeframe"] = signal.timeframe
            snapshot["signal_direction"] = str(signal.direction.value) if hasattr(signal.direction, 'value') else str(signal.direction)
            snapshot["signal_regime"] = signal.regime
            snapshot["signal_entry_price"] = signal.entry_price
            snapshot["signal_scores"] = signal.scores.to_dict() if signal.scores else {}
            snapshot["signal_patterns"] = [str(p.type.value) + "@" + str(p.price) for p in signal.patterns]
            snapshot["signal_rejection_reasons"] = signal.rejection_reasons

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            log.error("Falha ao salvar snapshot: %s", e)
            return f"FAILED_TO_SAVE: {e}"
        return filepath
