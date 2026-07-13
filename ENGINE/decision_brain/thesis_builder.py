import logging
from typing import Any, Dict, List, Optional

from ENGINE.scanner.scanner_types import (
    Signal, SignalDirection, PatternType, StructureType, ScannerScore,
)
from .decision_brain_types import (
    OperationalThesis, ThesisFactor, RegimeType,
)

log = logging.getLogger(__name__)


def _regime_label(regime: str) -> str:
    mapping = {
        "uptrend": "Tendencia de Alta",
        "downtrend": "Tendencia de Baixa",
        "ranging": "Mercado Lateral",
        "reversal": "Possivel Reversao",
    }
    return mapping.get(regime.lower(), regime)


def _regime_type(regime: str) -> RegimeType:
    r = regime.lower()
    if r in ("uptrend",):
        return RegimeType.TENDENCIA
    if r in ("downtrend",):
        return RegimeType.TENDENCIA
    if r in ("reversal",):
        return RegimeType.TRANSICAO
    return RegimeType.LATERAL


def _contexto_macro(signal: Signal) -> str:
    regime = signal.regime or "unknown"
    regime_label = _regime_label(regime)
    tf = signal.timeframe or "?"
    return (
        f"Ativo {signal.ticker} em TF {tf}. "
        f"Regime atual: {regime_label}. "
        f"Direcao do sinal: {signal.direction.value if hasattr(signal.direction, 'value') else signal.direction}. "
        f"Estrutura: {signal.structure.structure_type.value if signal.structure else 'N/D'}."
    )


def _multi_timeframe_text(signal: Signal) -> str:
    tf = signal.timeframe or "?"
    return (
        f"Sinal predominante em TF {tf}. "
        f"Consenso multi-TF: {signal.scores.consensus_score:.2f}." if signal.scores else f"Sinal em TF {tf}."
    )


def build_thesis(
    signal: Signal,
    scores: Optional[ScannerScore] = None,
    kalman_dir: str = "SIDE",
    kalman_conf: float = 0.0,
) -> OperationalThesis:
    sc = scores or signal.scores
    regime = signal.regime or "unknown"

    tendencia = ThesisFactor(
        nome="Tendencia",
        valor=sc.structural_score if sc else 0.0,
        justificativa=(
            f"Estrutura {signal.structure.structure_type.value if signal.structure else 'desconhecida'}, "
            f"forca estrutural {signal.structure_strength:.2f}"
        ),
        peso=0.25,
    )

    fluxo_institucional = ThesisFactor(
        nome="Fluxo Institucional",
        valor=sc.flow_score if sc else 0.0,
        justificativa=f"Score de fluxo: {sc.flow_score:.2f}" if sc else "Fluxo nao disponivel",
        peso=0.15,
    )

    estrutura = ThesisFactor(
        nome="Estrutura SMC",
        valor=sc.structural_score if sc else 0.0,
        justificativa=(
            f"BOS/CHOCH: {sum(1 for p in (signal.patterns or []) if p.type in (PatternType.BOS, PatternType.CHOCH))} "
            f"padroes. Order Blocks: {sum(1 for p in (signal.patterns or []) if p.type == PatternType.ORDER_BLOCK)}. "
            f"FVG: {sum(1 for p in (signal.patterns or []) if p.type == PatternType.FVG)}. "
            f"Liquidity Sweeps: {sum(1 for p in (signal.patterns or []) if p.type == PatternType.LIQUIDITY_SWEEP)}."
        ),
        peso=0.15,
    )

    liquidez = ThesisFactor(
        nome="Liquidez",
        valor=sc.liquidity_score if sc else 0.0,
        justificativa=f"RVOL: {signal.rvol:.2f}x. Score de liquidez: {sc.liquidity_score:.2f}" if sc else f"RVOL: {signal.rvol:.2f}x",
        peso=0.10,
    )

    momentum = ThesisFactor(
        nome="Momentum",
        valor=sc.momentum_score if sc else 0.0,
        justificativa=f"ADX: {signal.adx:.1f}. RSI: {getattr(sc, 'momentum_score', 0):.2f}",
        peso=0.10,
    )

    volatilidade = ThesisFactor(
        nome="Volatilidade",
        valor=max(0.0, 1.0 - min(signal.atr_value / (signal.entry_price * 0.02) if signal.entry_price > 0 else 0.0, 1.0)),
        justificativa=f"ATR: {signal.atr_value:.8f} ({signal.atr_value / signal.entry_price * 100:.2f}% do preco)" if signal.entry_price > 0 else f"ATR: {signal.atr_value:.8f}",
        peso=0.05,
    )

    timing = ThesisFactor(
        nome="Timing",
        valor=sc.timing_index if sc else 0.0,
        justificativa=f"Timing index: {sc.timing_index:.2f}. Kalman: {kalman_dir} (conf {kalman_conf:.2f})" if sc else f"Kalman: {kalman_dir}",
        peso=0.10,
    )

    risco = ThesisFactor(
        nome="Risco",
        valor=1.0 - (sc.risk_score if sc else 0.0),
        justificativa=f"Score de risco: {sc.risk_score:.2f}. RR: {signal.risk_reward:.2f}" if sc else f"RR: {signal.risk_reward:.2f}",
        peso=0.05,
    )

    expectativa_continuidade = ThesisFactor(
        nome="Expectativa de Continuidade",
        valor=sc.follow_through if sc else 0.0,
        justificativa=f"Follow Through: {sc.follow_through:.2f}. Conviccao: {sc.conviction_score:.2f}" if sc else "N/D",
        peso=0.05,
    )

    fatores = [
        tendencia, fluxo_institucional, estrutura, liquidez,
        momentum, volatilidade, timing, risco, expectativa_continuidade,
    ]
    score_total = sum(f.valor * f.peso for f in fatores) / sum(f.peso for f in fatores) if fatores else 0.0

    return OperationalThesis(
        contexto_macro=_contexto_macro(signal),
        regime=regime,
        tendencia=tendencia,
        fluxo_institucional=fluxo_institucional,
        estrutura=estrutura,
        liquidez=liquidez,
        momentum=momentum,
        volatilidade=volatilidade,
        timing=timing,
        risco=risco,
        multi_timeframe=_multi_timeframe_text(signal),
        expectativa_continuidade=expectativa_continuidade,
        score_total=round(score_total, 4),
    )
