"""
FORENSIC TEST — QUANTOS V4.0 ARCHITECTURE VERIFICATION

Reproduces exactly: ADAUSDT, 30m, SHORT, Entry Zone FAIL, Consensus 45%, Entry Score 0.40
Verifies that ALL modules use SignalDecision as single source of truth.
"""
import unittest
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ENGINE.scanner.scanner_types import (
    Signal, ScannerScore, SignalDirection, SignalClassification,
    Pattern, PatternType, MarketStructure, StructureType,
    SwingPoint, EntryZone, EntryDetails,
)
from ENGINE.decision.decision_engine import DecisionEngine, SignalDecision
from ENGINE.decision.self_audit import SelfAuditEngine
from ENGINE.decision.signal_decision import SignalDecision as SD
from ENGINE.scanner.scanner_config import (
    ENTRY_ZONE_SCORE_MIN, CONSENSUS_MINIMUM_SCORE,
    QUALITY_GATE_MIN_SCORE, QUALITY_GATE_CONFIDENCE_MIN, QUALITY_GATE_RISK_MAX,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("FORENSIC")


def _make_adausdt(
    entry_score: float = 0.40,
    consensus_score: float = 0.45,
    quality_score: float = 0.50,
    confidence_score: float = 0.50,
    risk_score: float = 0.30,
    direction: SignalDirection = SignalDirection.SHORT,
    regime: str = "downtrend",
    entry_zone_approved: bool = False,
) -> Signal:
    scores = ScannerScore(
        institutional_score=0.5, structural_score=0.5, market_score=0.5,
        momentum_score=0.5, liquidity_score=0.5, risk_score=risk_score,
        confidence_score=confidence_score, quality_score=quality_score,
        entry_score=entry_score, consensus_score=consensus_score,
        conviction_score=0.5, flow_score=0.5, follow_through=0.5,
        timing_index=0.5,
    )
    patterns = [
        Pattern(type=PatternType.ORDER_BLOCK, direction=direction,
                timeframe="30m", price=1.15, confidence=0.8, strength=0.7,
                description="OB ADA",
                metadata={"upper": 1.20, "lower": 1.10, "index": 10}),
        Pattern(type=PatternType.BOS, direction=direction,
                timeframe="30m", price=1.14, confidence=0.7, strength=0.6,
                description="BOS ADA", metadata={"index": 12}),
    ]
    structure = MarketStructure(
        structure_type=StructureType.DOWNTREND, swing_highs=[], swing_lows=[],
        structure_strength=0.5,
    )
    entry_details = EntryDetails(entry_zone=EntryZone(1.20, 1.10, 1.15, entry_score, "outside"),
        score=entry_score, approved=entry_zone_approved,
    )
    return Signal(
        ticker="ADAUSDT", timeframe="30m", direction=direction,
        entry_price=1.15, stop_loss=1.20, take_profit_1=1.05, take_profit_2=1.00,
        risk_reward=2.0, scores=scores, classification=SignalClassification.OURO,
        patterns=patterns, structure=structure, setup="test", context="test",
        approval_reasons=[], rejection_reasons=[],
        confidence=confidence_score, quality=quality_score,
        timestamp=datetime.now(), adx=25, rvol=1.5, regime=regime,
        structure_strength=0.5, entry_details=entry_details,
    )


class TestForensicArchitectureV4(unittest.TestCase):

    def setUp(self):
        self.results: List[dict] = []

    def log_sd(self, source: str, sd: "SignalDecision"):
        entry = {
            "source": source,
            "trace_id": sd.trace_id,
            "approved": sd.approved,
            "direction": sd.direction,
            "entry_score": round(sd.entry_score, 4),
            "consensus": round(sd.consensus, 4),
            "quality": round(sd.quality, 4),
            "confidence": round(sd.confidence, 4),
            "risk": round(sd.risk, 4),
            "entry_zone_valid": sd.entry_zone_valid,
            "entry_zone_ok": sd.entry_zone_ok,
            "entry_score_ok": sd.entry_score_ok,
            "consensus_ok": sd.consensus_ok,
            "quality_ok": sd.quality_ok,
            "confidence_ok": sd.confidence_ok,
            "risk_ok": sd.risk_ok,
            "trend_ok": sd.trend_ok,
            "structure_ok": sd.structure_ok,
            "market_ok": sd.market_ok,
            "institutional_ok": sd.institutional_ok,
            "reject_reason": sd.reject_reason,
        }
        self.results.append(entry)
        log.info("=== %s ===", source)
        for k, v in entry.items():
            log.info("  %-20s = %s", k, v)
        log.info("=" * 40)

    def test_v4_adausdt_entry_fail_consensus_fail(self):
        """ADAUSDT 30m SHORT | Entry Score 0.40 | Consensus 0.45
        Verifica se o fluxo V4.0 aprova ou rejeita coerentemente."""
        sig = _make_adausdt(
            entry_score=0.40, consensus_score=0.45,
            entry_zone_approved=False,
        )

        # === PASSO 1: DecisionEngine ===
        sd = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self.log_sd("1-DECISION_ENGINE", sd)

        # === PASSO 2: SelfAudit ===
        audit = SelfAuditEngine.audit(sd, sig)
        log.info("SELF-AUDIT passed=%s reason=%s", audit.passed, audit.block_reason)
        self.log_sd("2-SELF_AUDIT", sd)

        # === PASSO 3: SignalDecision.to_dict() (simula publisher) ===
        sd_dict = sd.to_dict()
        log.info("3-PUBLISHER sd.to_dict() keys=%s", list(sd_dict.keys()))

        # === PASSO 4: Diagnostic simulation ===
        diag_entry = {
            "status": "APPROVED" if sd.approved else "REJECTED",
            "direction": sd.direction,
            "trace_id": sd.trace_id,
            "primary_reason": sd.reject_reason,
            "entry_score": round(sd.entry_score * 100 if sd.entry_score < 1 else sd.entry_score, 1),
            "entry_zone_result": "PASS" if sd.entry_zone_valid else "FAIL",
            "consensus": round(sd.consensus, 4),
        }
        log.info("=== 4-DIAGNOSTIC_SIM ===")
        for k, v in diag_entry.items():
            log.info("  %-20s = %s", k, v)

        # === PASSO 5: Telegram simulation ===
        tg_msg = {
            "trace_id": sd_dict.get("trace_id"),
            "pair": sd_dict.get("pair"),
            "direction": sd_dict.get("direction"),
            "approved": sd_dict.get("approved"),
            "entry_score": sd_dict.get("entry_score"),
            "consensus": sd_dict.get("consensus"),
        }
        log.info("=== 5-TELEGRAM_SIM ===")
        for k, v in tg_msg.items():
            log.info("  %-20s = %s", k, v)

        # === VERIFICACAO: todos os campos DEVEM ser identicos ===
        log.info("=" * 56)
        log.info("VERIFICACAO DE CONSISTENCIA V4.0")
        log.info("=" * 56)

        errors = []
        # approved
        if sd.approved != sd_dict.get("approved"):
            errors.append(f"approved divergiu: SD={sd.approved} dict={sd_dict.get('approved')}")
        if sd.direction != sd_dict.get("direction"):
            errors.append(f"direction divergiu: SD={sd.direction} dict={sd_dict.get('direction')}")
        if sd.trace_id != tg_msg["trace_id"]:
            errors.append(f"trace_id divergiu: SD={sd.trace_id} tg={tg_msg['trace_id']}")

        # Verificar que campos _ok sao consistentes com approved
        if sd.approved:
            ok_fields = ["market_ok", "trend_ok", "structure_ok", "entry_zone_ok",
                         "entry_score_ok", "consensus_ok", "quality_ok",
                         "confidence_ok", "risk_ok", "institutional_ok"]
            for f in ok_fields:
                val = getattr(sd, f, None)
                if not val:
                    errors.append(f"BUG: approved=True mas {f}=False")
        else:
            # rejected must have at least one _ok = False
            ok_fields = ["market_ok", "trend_ok", "structure_ok", "entry_zone_ok",
                         "entry_score_ok", "consensus_ok", "quality_ok",
                         "confidence_ok", "risk_ok", "institutional_ok"]
            all_ok = all(getattr(sd, f, False) for f in ok_fields)
            if all_ok and sd.reject_reason:
                errors.append(f"BUG: approved=False mas todos ok=True")

        if errors:
            log.error("INCONSISTENCIAS ENCONTRADAS:")
            for e in errors:
                log.error("  [ERRO] %s", e)
            self.fail("\n".join(errors))
        else:
            log.info("[OK] SignalDecision V4.0 consistente em todos os modulos")

        # === VERIFICACAO DO CASO ESPECIFICO ===
        log.info("=" * 56)
        log.info("VEREDITO PARA ADAUSDT entry=0.40 cons=0.45")
        log.info("=" * 56)
        self.assertFalse(
            sd.approved,
            f"ADAUSDT entry=0.40 consensus=0.45 deve ser REJEITADO, "
            f"mas foi APROVADO (motivo: {sd.reject_reason})"
        )
        self.assertFalse(sd.entry_zone_ok, "entry_zone_ok deve ser False para entry_score=0.40")
        self.assertFalse(sd.entry_zone_valid, "entry_zone_valid deve ser False para entry_score=0.40")
        self.assertFalse(sd.consensus_ok, "consensus_ok deve ser False para consensus=0.45")
        self.assertIn("entry", sd.reject_reason.lower(),
                      "Primeiro filtro a falhar deve ser Entry Zone")
        log.info("[OK] ADAUSDT CORRETAMENTE REJEITADO — entry_score=0.40 < 0.45 gate falha primeiro")


if __name__ == "__main__":
    unittest.main()
