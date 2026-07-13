import logging
from typing import Any, List, Optional

from ENGINE.market.market_types import MarketContext, TechnicalIndicators

from .base import BaseSkill
from .skill_opinion import SkillOpinion

log = logging.getLogger(__name__)


def _get_indicators(market_context: Any) -> Optional[TechnicalIndicators]:
    if isinstance(market_context, MarketContext):
        return market_context.indicators
    return getattr(market_context, "indicators", None)


def _get_score(market_context: Any, name: str, default: float = 0.0) -> float:
    return getattr(market_context, name, default)


class VolumeSkill(BaseSkill):
    def __init__(self, version: str = "1.0.0"):
        super().__init__(name="volume", version=version, category="flow")

    def analyze(self, market_context: Any, world_model: Any = None) -> SkillOpinion:
        indicators = _get_indicators(market_context)
        if indicators is None:
            return SkillOpinion(
                skill_name=self.name,
                confidence=0.0,
                risk=1.0,
                probability=0.0,
                evidence=["Sem dados de indicadores para analise de volume"],
                observations="MarketContext sem indicadores tecnicos",
                success=False,
            )

        evidence = []
        total_score = 0.0
        max_possible = 0.0

        rvol = getattr(indicators, "rvol", 0.0)
        volume = getattr(indicators, "volume", 0.0)
        avg_volume = getattr(indicators, "avg_volume", 0.0)

        if rvol >= 2.0:
            evidence.append(f"RVOL {rvol:.2f}x — Volume extremamente acima da media")
            total_score += 0.30
        elif rvol >= 1.5:
            evidence.append(f"RVOL {rvol:.2f}x — Volume muito acima da media")
            total_score += 0.25
        elif rvol >= 1.0:
            evidence.append(f"RVOL {rvol:.2f}x — Volume acima da media")
            total_score += 0.15
        elif rvol >= 0.7:
            evidence.append(f"RVOL {rvol:.2f}x — Volume moderado")
            total_score += 0.05
        else:
            evidence.append(f"RVOL {rvol:.2f}x — Volume abaixo da media")
        max_possible += 0.30

        if volume > 0 and avg_volume > 0:
            vol_ratio = volume / avg_volume
            if vol_ratio >= 3.0:
                evidence.append(f"Volume anomalo: {vol_ratio:.1f}x a media historica")
                total_score += 0.15
            elif vol_ratio >= 2.0:
                evidence.append(f"Volume elevado: {vol_ratio:.1f}x a media historica")
                total_score += 0.10
            elif vol_ratio < 0.5:
                evidence.append(f"Volume reduzido: {vol_ratio:.1f}x a media historica")
                total_score += 0.0
            max_possible += 0.15

        flow_score = _get_score(market_context, "institutional_score", 0.0)
        if flow_score >= 0.80:
            evidence.append(f"Fluxo institucional forte: {flow_score:.2f}")
            total_score += 0.20
        elif flow_score >= 0.60:
            evidence.append(f"Fluxo institucional moderado: {flow_score:.2f}")
            total_score += 0.10
        elif flow_score >= 0.40:
            evidence.append(f"Fluxo institucional neutro: {flow_score:.2f}")
            total_score += 0.0
        elif flow_score > 0.0:
            evidence.append(f"Fluxo institucional fraco: {flow_score:.2f}")
        max_possible += 0.20

        market_score = _get_score(market_context, "market_score", 0.0)
        trend_score = _get_score(market_context, "trend_score", 0.0)
        momentum_score = _get_score(market_context, "momentum_score", 0.0)
        liquidity_score = _get_score(market_context, "liquidity_score", 0.0)

        adx = getattr(indicators, "adx", 0.0)
        if adx >= 30:
            evidence.append(f"ADX {adx:.1f} — Tendencia forte")
            total_score += 0.10
        elif adx >= 25:
            evidence.append(f"ADX {adx:.1f} — Tendencia moderada")
            total_score += 0.05
        elif adx >= 20:
            evidence.append(f"ADX {adx:.1f} — Tendencia fraca")
            total_score += 0.0
        else:
            evidence.append(f"ADX {adx:.1f} — Tendencia indefinida")
        max_possible += 0.10

        if momentum_score >= 0.70:
            evidence.append(f"Momentum score: {momentum_score:.2f}")
            total_score += 0.05
        max_possible += 0.05

        if liquidity_score >= 0.70:
            evidence.append(f"Liquidez score: {liquidity_score:.2f}")
        elif liquidity_score <= 0.30:
            evidence.append(f"Liquidez baixa: {liquidity_score:.2f}")

        funding = getattr(market_context, "funding_rate", None)
        if funding is not None:
            if funding > 0.01:
                evidence.append(f"Funding positivo: {funding:.4f}")
            elif funding < -0.01:
                evidence.append(f"Funding negativo: {funding:.4f}")

        spread = getattr(market_context, "spread", None)
        if spread is not None and spread > 0:
            if spread <= 0.0005:
                evidence.append(f"Spread baixo: {spread:.4f}")
            elif spread > 0.005:
                evidence.append(f"Spread elevado: {spread:.4f}")

        if not evidence:
            evidence.append("Nenhum dado de volume ou fluxo disponivel")

        overall = total_score / max(max_possible, 1.0)
        confidence = min(max(overall, 0.0), 0.95)
        risk = min(max(1.0 - (overall * 0.6 + (liquidity_score if liquidity_score > 0 else 0.5) * 0.4), 0.05), 0.95)
        probability = min(confidence * (1.0 - risk * 0.25), 0.95)

        return SkillOpinion(
            skill_name=self.name,
            confidence=round(confidence, 2),
            risk=round(risk, 2),
            probability=round(probability, 2),
            evidence=evidence,
            observations=(
                f"Analise de volume concluida: RVOL {rvol:.2f}x, "
                f"fluxo {flow_score:.2f}, "
                f"momentum {momentum_score:.2f}. "
                f"Volume {'elevado' if rvol >= 1.0 else 'moderado' if rvol >= 0.7 else 'baixo'}."
            ),
            success=True,
        )
