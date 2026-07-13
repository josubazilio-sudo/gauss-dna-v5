import logging
from typing import Any, List, Optional

from ENGINE.market.market_types import Candle, MarketContext
from ENGINE.scanner.scanner_patterns import scan_all_patterns, find_swing_points
from ENGINE.scanner.scanner_structure import analyze_structure
from ENGINE.scanner.scanner_types import Pattern, PatternType, MarketStructure, SignalDirection

from .base import BaseSkill
from .skill_opinion import SkillOpinion, SkillMetrics

log = logging.getLogger(__name__)


def _extract_candles(market_context: Any) -> Optional[List[Candle]]:
    if isinstance(market_context, MarketContext):
        for tf_ctx in market_context.timeframes.values():
            return getattr(tf_ctx, "candles", None) or getattr(tf_ctx, "_candles", None)
    return getattr(market_context, "candles", None)


def _count_by_direction(patterns: List[Pattern], d: SignalDirection) -> int:
    return sum(1 for p in patterns if p.direction == d)


def _avg_strength(patterns: List[Pattern]) -> float:
    if not patterns:
        return 0.0
    return sum(p.strength for p in patterns) / len(patterns)


def _max_confidence(patterns: List[Pattern]) -> float:
    if not patterns:
        return 0.0
    return max(p.confidence for p in patterns)


class SMCSkill(BaseSkill):
    def __init__(self, version: str = "1.0.0"):
        super().__init__(name="smc", version=version, category="structure")

    def analyze(self, market_context: Any, world_model: Any = None) -> SkillOpinion:
        candles = _extract_candles(market_context)
        if not candles or len(candles) < 10:
            return SkillOpinion(
                skill_name=self.name,
                confidence=0.0,
                risk=1.0,
                probability=0.0,
                evidence=["Dados insuficientes para analise SMC"],
                observations="MarketContext sem candles suficientes (minimo 10)",
                success=False,
            )

        patterns = scan_all_patterns(candles, "1h")
        swings = find_swing_points(candles)
        structure = analyze_structure(candles)

        evidence = []
        total_score = 0.0
        max_possible = 0.0

        bos_pat = [p for p in patterns if p.type == PatternType.BOS]
        choch_pat = [p for p in patterns if p.type == PatternType.CHOCH]
        ob_pat = [p for p in patterns if p.type == PatternType.ORDER_BLOCK]
        fvg_pat = [p for p in patterns if p.type == PatternType.FVG]
        sweep_pat = [p for p in patterns if p.type == PatternType.LIQUIDITY_SWEEP]

        if bos_pat:
            evidence.append(f"BOS confirmado ({len(bos_pat)}x, forca media {_avg_strength(bos_pat):.2f})")
            total_score += len(bos_pat) * 0.20
        max_possible += 0.40

        if choch_pat:
            evidence.append(f"CHoCH confirmado ({len(choch_pat)}x, forca media {_avg_strength(choch_pat):.2f})")
            total_score += len(choch_pat) * 0.25
        max_possible += 0.50

        if ob_pat:
            evidence.append(f"Order Block detectado ({len(ob_pat)}x, confianca max {_max_confidence(ob_pat):.2f})")
            total_score += len(ob_pat) * 0.15
        max_possible += 0.45

        if fvg_pat:
            evidence.append(f"FVG detectado ({len(fvg_pat)}x, forca media {_avg_strength(fvg_pat):.2f})")
            total_score += len(fvg_pat) * 0.10
        max_possible += 0.30

        if sweep_pat:
            evidence.append(f"Liquidity Sweep detectado ({len(sweep_pat)}x)")
            total_score += len(sweep_pat) * 0.15
        max_possible += 0.30

        structure_strength = structure.structure_strength if structure else 0.0
        evidence.append(f"Forca estrutural: {structure_strength:.2f}")
        total_score += structure_strength * 0.20
        max_possible += 0.20

        n_swings = len(swings)
        evidence.append(f"Swings identificados: {n_swings}")
        total_score += min(n_swings / 20, 1.0) * 0.05
        max_possible += 0.05

        if not bos_pat and not choch_pat and not ob_pat:
            evidence.append("Estrutura indefinida: sem BOS, CHoCH ou Order Block")
            evidence.append("Recomendacao: aguardar confirmacao estrutural")
            return SkillOpinion(
                skill_name=self.name,
                confidence=0.10,
                risk=0.70,
                probability=0.15,
                evidence=evidence,
                observations="Nenhum padrao SMC relevante detectado. Mercado sem estrutura clara para analise.",
                success=True,
            )

        if n_swings < 4:
            evidence.append("Poucos swings disponiveis para confirmacao estrutural")

        long_count = _count_by_direction(patterns, SignalDirection.LONG)
        short_count = _count_by_direction(patterns, SignalDirection.SHORT)
        total_patterns = len(patterns)

        if long_count > 0 and short_count > 0:
            evidence.append(f"Padroes conflitantes: {long_count} LONG vs {short_count} SHORT")
            conflict_penalty = min(long_count, short_count) / max(long_count, short_count) * 0.20
            total_score -= conflict_penalty

        evidence.append(f"Total de padroes SMC: {total_patterns}")

        overall = total_score / max(max_possible, 1.0)
        confidence = min(max(overall, 0.0), 0.95)
        risk = min(max(1.0 - (overall * 0.7 + structure_strength * 0.3), 0.05), 0.95)
        probability = min(confidence * (1.0 - risk * 0.3), 0.95)

        return SkillOpinion(
            skill_name=self.name,
            confidence=round(confidence, 2),
            risk=round(risk, 2),
            probability=round(probability, 2),
            evidence=evidence,
            observations=(
                f"Analise SMC concluida: {total_patterns} padroes detectados "
                f"({long_count} LONG / {short_count} SHORT), "
                f"forca estrutural {structure_strength:.2f}. "
                f"Estrutura {'consistente' if confidence > 0.5 else 'fraca'}."
            ),
            success=True,
        )
