import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .scanner_types import (
    ScannerScore, SignalClassification, Pattern,
    MarketStructure, PatternType, StructureType,
)
from .scanner_config import (
    HARD_MIN_PATTERNS, HARD_MIN_RVOL, HARD_MAX_SPREAD,
    HARD_MIN_ADX, HARD_MIN_STRUCTURE_STRENGTH,
    HARD_MAX_ATR_PCT, HARD_MIN_ATR_PCT,
    QUALITY_GATE_MIN_SCORE, QUALITY_GATE_RISK_MAX, QUALITY_GATE_CONFIDENCE_MIN,
    RANK_MIN_QUALITY, RANK_MIN_CONFIDENCE, RANK_MIN_CONSENSUS,
    RANK_MIN_ENTRY, RANK_MIN_CONVICTION,
    QUALITY_TIERS,
)
from ENGINE.common.score_normalizer import scale_1_to_100

log = logging.getLogger(__name__)


@dataclass
class Stage1Result:
    passed: bool
    reasons: List[str] = field(default_factory=list)

    def __bool__(self):
        return self.passed


@dataclass
class Stage2Result:
    classification: SignalClassification
    reasons: List[str] = field(default_factory=list)
    score_breakdown: str = ""


@dataclass
class QualityGateResult:
    approved: bool
    stage1: Stage1Result
    stage2: Optional[Stage2Result] = None
    final_classification: Optional[SignalClassification] = None
    summary: str = ""


def stage1_hard_filters(
    patterns: List[Pattern],
    structure: MarketStructure,
    rvol: float,
    adx: float,
    spread: float,
    atr_pct: float,
    entry_zone_approved: bool,
    direction: Optional[str] = None,
) -> Stage1Result:
    """STAGE 1 — Hard Filters.

    Eliminatory. Any single failure rejects the signal immediately
    with a clear reason. No scoring — binary pass/fail.
    """
    reasons = []

    if not patterns:
        reasons.append("Sem padroes institucionais detectados")
    elif len(patterns) < HARD_MIN_PATTERNS:
        reasons.append(f"Apenas {len(patterns)} padrao(oes) — minimo {HARD_MIN_PATTERNS}")

    if rvol < HARD_MIN_RVOL:
        reasons.append(f"RVOL {rvol:.2f}x abaixo do minimo {HARD_MIN_RVOL}x")

    if spread > HARD_MAX_SPREAD:
        reasons.append(f"Spread {spread:.4f} acima do maximo {HARD_MAX_SPREAD}")

    if adx < HARD_MIN_ADX:
        reasons.append(f"ADX {adx:.1f} abaixo do minimo {HARD_MIN_ADX}")

    if structure.structure_strength < HARD_MIN_STRUCTURE_STRENGTH:
        reasons.append(
            f"Forca estrutural {structure.structure_strength:.2f} abaixo do minimo "
            f"{HARD_MIN_STRUCTURE_STRENGTH}"
        )

    if atr_pct > HARD_MAX_ATR_PCT:
        reasons.append(f"ATR {atr_pct*100:.2f}% acima do maximo {HARD_MAX_ATR_PCT*100:.2f}%")

    if atr_pct < HARD_MIN_ATR_PCT:
        reasons.append(f"ATR {atr_pct*100:.4f}% abaixo do minimo {HARD_MIN_ATR_PCT*100:.4f}%")

    if not entry_zone_approved:
        reasons.append("Zona de entrada nao aprovada")

    return Stage1Result(passed=len(reasons) == 0, reasons=reasons)


def stage2_ranking(
    scores: ScannerScore,
) -> Stage2Result:
    """STAGE 2 — Ranking.

    Classifies approved signals into tiers based on combined score profile.
    Non-eliminatory — determines quality level, not pass/fail.

    V19.0: usa os mesmos ranges fixos de scanner_scoring.classify_signal().
    """
    reasons = []

    from .scanner_scoring import classify_signal

    tier = classify_signal(scores)

    min_checks = [
        ("quality", scores.quality_score, RANK_MIN_QUALITY),
        ("confidence", scores.confidence_score, RANK_MIN_CONFIDENCE),
        ("entry", scores.entry_score, RANK_MIN_ENTRY),
        ("conviction", scores.conviction_score, RANK_MIN_CONVICTION),
        ("consensus", scores.consensus_score, RANK_MIN_CONSENSUS),
    ]
    for name, value, threshold in min_checks:
        if value < threshold:
            reasons.append(f"{name} {value:.2f} abaixo do ideal {threshold}")

    breakdown_parts = [
        f"Quality:{scores.quality_score:.2f}",
        f"Confidence:{scores.confidence_score:.2f}",
        f"Conviction:{scores.conviction_score:.2f}",
        f"Entry:{scores.entry_score:.2f}",
        f"Consensus:{scores.consensus_score:.2f}",
        f"Tier:{tier.value}",
    ]
    score_breakdown = " | ".join(breakdown_parts)

    return Stage2Result(
        classification=tier,
        reasons=reasons,
        score_breakdown=score_breakdown,
    )


def apply_quality_gate(
    patterns: List[Pattern],
    structure: MarketStructure,
    scores: ScannerScore,
    rvol: float,
    adx: float,
    spread: float,
    atr_pct: float,
    entry_zone_approved: bool,
    direction: Optional[str] = None,
) -> QualityGateResult:
    """Apply two-stage quality gate.

    Stage 1: Hard filters — binary pass/fail with explicit reasons.
    Stage 2: Ranking — classification into Ouro/Prata/Bronze/Reprovado.

    Returns a QualityGateResult with clear approved/rejected status.
    """
    s1 = stage1_hard_filters(
        patterns=patterns,
        structure=structure,
        rvol=rvol,
        adx=adx,
        spread=spread,
        atr_pct=atr_pct,
        entry_zone_approved=entry_zone_approved,
        direction=direction,
    )

    if not s1.passed:
        summary = "REPROVADO (Stage 1 — Hard Filters)"
        return QualityGateResult(
            approved=False,
            stage1=s1,
            stage2=None,
            final_classification=SignalClassification.REPROVADO,
            summary=summary,
        )

    s2 = stage2_ranking(scores)

    if s2.classification == SignalClassification.REPROVADO:
        summary = "REPROVADO (Stage 2 — Ranking insuficiente)"
        return QualityGateResult(
            approved=False,
            stage1=s1,
            stage2=s2,
            final_classification=SignalClassification.REPROVADO,
            summary=summary,
        )

    summary = f"APROVADO — {s2.classification.value} | {s2.score_breakdown}"
    return QualityGateResult(
        approved=True,
        stage1=s1,
        stage2=s2,
        final_classification=s2.classification,
        summary=summary,
    )


def format_gate_report(result: QualityGateResult) -> str:
    lines = []
    lines.append("=== QUALITY GATE (TWO-STAGE) ===")
    lines.append(f"Resultado: {result.summary}")
    lines.append("")

    lines.append("--- Stage 1: Hard Filters ---")
    if result.stage1.reasons:
        for r in result.stage1.reasons:
            lines.append(f"  [REPROVADO] {r}")
    else:
        lines.append("  Todos os filtros obrigatorios aprovados")

    if result.stage2:
        lines.append("")
        lines.append("--- Stage 2: Ranking ---")
        lines.append(f"  Classificacao: {result.stage2.classification.value}")
        lines.append(f"  Breakdown: {result.stage2.score_breakdown}")
        if result.stage2.reasons:
            for r in result.stage2.reasons:
                lines.append(f"  [OBS] {r}")

    lines.append("================================")
    return "\n".join(lines)
