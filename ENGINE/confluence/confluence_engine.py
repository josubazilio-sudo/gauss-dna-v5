import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..scanner.scanner_types import (
    SignalDirection, Pattern, PatternType, MarketStructure,
    StructureType, ScannerScore,
)

from .confluence_config import (
    CONFLUENCE_FILTERS, CONFLUENCE_TOTAL,
    QUALITY_TIERS, CONFLUENCE_LATERAL_FILTERS,
)

log = logging.getLogger(__name__)


@dataclass
class ConfluenceBreakdown:
    total_score: float
    normalized_score: float
    filters_passed: int
    filters_total: int
    details: Dict[str, float]
    tier: str
    tier_label: str
    lateral_market_score: float
    lateral_reasons: List[str]



class ConfluenceEngine:
    def compute(
        self,
        patterns: List[Pattern],
        structure: MarketStructure,
        direction: SignalDirection,
        adx: float = 0.0,
        rvol: float = 0.0,
        atr_percent: float = 0.0,
        regime: str = "unknown",
        scores: Optional[ScannerScore] = None,
    ) -> ConfluenceBreakdown:
        details: Dict[str, float] = {}
        passed_count = 0

        for filter_key, cfg in CONFLUENCE_FILTERS.items():
            points, _ = self._evaluate_filter(
                filter_key, patterns, structure, direction,
                adx, rvol, atr_percent, regime, scores,
            )
            if points > 0:
                passed_count += 1
            details[filter_key] = points

        total = sum(details.values())
        normalized = round(min(total / CONFLUENCE_TOTAL, 1.0) * 100, 1)

        lateral_score, lateral_reasons = self._check_lateral_market(
            patterns, structure, adx, atr_percent,
        )

        tier, tier_label = self._classify(normalized)

        return ConfluenceBreakdown(
            total_score=total,
            normalized_score=normalized,
            filters_passed=passed_count,
            filters_total=len(CONFLUENCE_FILTERS),
            details=details,
            tier=tier,
            tier_label=tier_label,
            lateral_market_score=lateral_score,
            lateral_reasons=lateral_reasons,
        )


    def _evaluate_filter(
        self, filter_key: str,
        patterns: List[Pattern], structure: MarketStructure,
        direction: SignalDirection,
        adx: float, rvol: float, atr_percent: float,
        regime: str, scores: Optional[ScannerScore],
    ) -> Tuple[float, str]:
        weight = CONFLUENCE_FILTERS[filter_key]["weight"]

        if filter_key == "trend":
            if structure.structure_type == StructureType.UPTREND and direction == SignalDirection.LONG:
                return weight, f"UPTREND alinhado com LONG"
            if structure.structure_type == StructureType.DOWNTREND and direction == SignalDirection.SHORT:
                return weight, f"DOWNTREND alinhado com SHORT"
            if structure.structure_type in (StructureType.UPTREND, StructureType.DOWNTREND):
                return round(weight * 0.5, 1), f"Contra-tendência ({structure.structure_type.value})"
            return 0, "Tendência neutra ou desalinhada"

        if filter_key == "choch":
            choch = [p for p in patterns if p.type == PatternType.CHOCH and p.direction == direction]
            if choch:
                return weight, f"CHoCH {direction.value}: {len(choch)} ocorrência(s)"
            return 0, "Sem CHoCH"

        if filter_key == "order_block":
            obs = [p for p in patterns if p.type == PatternType.ORDER_BLOCK and p.direction == direction]
            if obs:
                return weight, f"Order Block {direction.value}: {len(obs)} bloco(s)"
            return 0, "Sem Order Block"

        if filter_key == "liquidity_sweep":
            sweeps = [p for p in patterns if p.type == PatternType.LIQUIDITY_SWEEP]
            if sweeps:
                return weight, f"Liquidity Sweep: {len(sweeps)} ocorrência(s)"
            return 0, "Sem Liquidity Sweep"

        if filter_key == "bos":
            boss = [p for p in patterns if p.type == PatternType.BOS and p.direction == direction]
            if boss:
                return weight, f"BOS {direction.value}: {len(boss)} ocorrência(s)"
            return 0, "Sem BOS"

        if filter_key == "fvg":
            fvgs = [p for p in patterns if p.type == PatternType.FVG]
            if fvgs:
                return weight, f"FVG: {len(fvgs)} gap(s)"
            return 0, "Sem FVG"

        if filter_key == "volume":
            if scores and scores.momentum_score:
                if rvol >= 1.0:
                    return weight, f"RVOL={rvol:.2f} (acima da média)"
                return round(weight * 0.5, 1), f"RVOL={rvol:.2f} (moderado)"
            return 0, "Sem dados de volume"

        if filter_key == "adx":
            if adx >= 40:
                return weight, f"ADX={adx:.1f} (tendência forte)"
            if adx >= 25:
                return round(weight * 0.8, 1), f"ADX={adx:.1f} (tendência moderada)"
            return round(weight * 0.3, 1), f"ADX={adx:.1f} (tendência fraca)"

        if filter_key == "momentum":
            if scores and scores.momentum_score:
                ms = scores.momentum_score
                if ms >= 0.6:
                    return weight, f"Momentum={ms:.2f}"
                return round(weight * ms, 1), f"Momentum={ms:.2f}"
            return 0, "Sem momentum"

        if filter_key == "volatility":
            if atr_percent > 0:
                if 0.003 <= atr_percent <= 0.02:
                    return weight, f"ATR%={atr_percent:.4f} (volatilidade ideal)"
                if atr_percent < 0.003:
                    return round(weight * 0.5, 1), f"ATR%={atr_percent:.4f} (volatilidade baixa)"
                return round(weight * 0.3, 1), f"ATR%={atr_percent:.4f} (volatilidade alta)"
            return 0, "Sem ATR"

        return 0, "Filtro desconhecido"

    def _check_lateral_market(
        self, patterns: List[Pattern], structure: MarketStructure,
        adx: float, atr_percent: float,
    ) -> Tuple[float, List[str]]:
        reasons = []
        score = 0.0

        has_bos = any(p.type == PatternType.BOS for p in patterns)
        has_choch = any(p.type == PatternType.CHOCH for p in patterns)
        structure_weak = structure.structure_strength < 0.30

        if adx < 25:
            score += 0.2
            reasons.append(f"ADX baixo ({adx:.1f} < 25)")
        if atr_percent < 0.003:
            score += 0.2
            reasons.append(f"ATR baixo ({atr_percent:.4f} < 0.003)")
        if structure_weak:
            score += 0.2
            reasons.append(f"Estrutura fraca ({structure.structure_strength:.2f} < 0.30)")
        if not has_bos and not has_choch:
            score += 0.2
            reasons.append("Sem BOS ou CHoCH")
        if structure.structure_type == StructureType.RANGING:
            score += 0.2
            reasons.append("Mercado lateral (RANGING)")

        return min(score, 1.0), reasons


    @staticmethod
    def _classify(normalized_score: float) -> Tuple[str, str]:
        for tier_name, tier_cfg in QUALITY_TIERS.items():
            if normalized_score >= tier_cfg["min_score"]:
                return tier_name, tier_cfg["label"]
        return "REJEITADO", "❌ REJEITADO"

    @staticmethod
    def normalized_score_to_quality(normalized_score: float) -> float:
        return round(normalized_score / 100.0, 4)
