import logging
from typing import List, Optional

from ENGINE.scanner.scanner_types import (
    Signal, SignalDirection, PatternType, ScannerScore,
)
from .decision_brain_types import CounterThesis, CounterThesisFactor

log = logging.getLogger(__name__)


def build_counter_thesis(
    signal: Signal,
    scores: Optional[ScannerScore] = None,
    kalman_dir: str = "SIDE",
    rsi: float = 50.0,
    adx: float = 0.0,
    atr_percent: float = 0.0,
    rvol: float = 0.0,
    vwap_distance: float = 0.0,
) -> CounterThesis:
    sc = scores or signal.scores
    ct = CounterThesis()

    rsi_extremo = (rsi > 75 and signal.direction == SignalDirection.LONG) or \
                  (rsi < 25 and signal.direction == SignalDirection.SHORT)
    ct.adicionar(
        nome="RSI Extremo",
        ativo=rsi_extremo,
        peso=0.20,
        justificativa=f"RSI {rsi:.1f} {'acima de 75' if rsi > 75 else 'abaixo de 25'} — possivel exaustao" if rsi_extremo else f"RSI {rsi:.1f} dentro da faixa normal",
    )

    exaustao_volume = rvol > 2.5 and adx > 40
    ct.adicionar(
        nome="Exaustao (Volume Climax)",
        ativo=exaustao_volume,
        peso=0.15,
        justificativa=f"RVOL {rvol:.2f}x com ADX {adx:.1f} — possivel climax de volume" if exaustao_volume else f"Volume dentro da normalidade",
    )

    kalman_lateral = kalman_dir in ("SIDE", "ERRO")
    ct.adicionar(
        nome="Kalman Lateral ou Erro",
        ativo=kalman_lateral,
        peso=0.15,
        justificativa=f"Kalman: {kalman_dir} — sem tendencia clara ou erro no filtro" if kalman_lateral else f"Kalman: {kalman_dir} — tendencia presente",
    )

    ft_baixo = (sc.follow_through if sc else 0.0) < 0.35
    ct.adicionar(
        nome="Follow Through Baixo",
        ativo=ft_baixo,
        peso=0.10,
        justificativa=f"Follow Through: {sc.follow_through:.2f} abaixo de 0.35" if ft_baixo else f"Follow Through: {sc.follow_through:.2f} adequado",
    )

    confluencia_insuficiente = (sc.quality_score if sc else 0.0) < 0.65
    ct.adicionar(
        nome="Confluencia Insuficiente",
        ativo=confluencia_insuficiente,
        peso=0.10,
        justificativa=f"Quality: {sc.quality_score:.2f} abaixo de 0.65" if confluencia_insuficiente else f"Quality: {sc.quality_score:.2f} adequada",
    )

    risco_elevado = (sc.risk_score if sc else 0.0) > 0.40
    ct.adicionar(
        nome="Risco Elevado",
        ativo=risco_elevado,
        peso=0.10,
        justificativa=f"Risk Score: {sc.risk_score:.2f} acima de 0.40" if risco_elevado else f"Risk Score: {sc.risk_score:.2f} aceitavel",
    )

    vwap_distante = abs(vwap_distance) > 0.03
    ct.adicionar(
        nome="Distancia Excessiva da VWAP",
        ativo=vwap_distante,
        peso=0.10,
        justificativa=f"Distancia VWAP: {vwap_distance*100:.2f}% acima de 3%" if vwap_distante else f"Distancia VWAP: {vwap_distance*100:.2f}% aceitavel",
    )

    sem_confirmacao = not any(p.type in (PatternType.BOS, PatternType.CHOCH) for p in (signal.patterns or []))
    ct.adicionar(
        nome="Sem Confirmacao Estrutural",
        ativo=sem_confirmacao,
        peso=0.10,
        justificativa="Nenhum BOS ou CHOCH detectado" if sem_confirmacao else "BOS/CHOCH presentes",
    )

    ct.calcular_score()
    return ct
