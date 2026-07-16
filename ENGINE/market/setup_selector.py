import logging
from typing import Tuple, Optional
from dataclasses import dataclass

from .market_types import MarketRegime, SetupType, TrendDirection
from ..scanner.scanner_types import PatternType, MarketStructure, SignalDirection

log = logging.getLogger(__name__)


@dataclass
class SetupRecommendation:
    setup_type: SetupType
    strategy_description: str
    objective: str
    tp_multiplier: float
    max_leverage: int
    continuation_expected: str


REGIME_SETUP_MAP = {
    MarketRegime.STRONG_TREND_UP: {
        "allowed": {
            SetupType.TREND_PULLBACK,
            SetupType.TREND_FOLLOWING,
            SetupType.TREND_BREAKOUT,
        },
        "default": SetupType.TREND_PULLBACK,
    },
    MarketRegime.STRONG_TREND_DOWN: {
        "allowed": {
            SetupType.PULLBACK_SHORT,
            SetupType.TREND_FOLLOWING,
            SetupType.BREAKDOWN,
        },
        "default": SetupType.PULLBACK_SHORT,
    },
    MarketRegime.RANGING: {
        "allowed": {
            SetupType.RANGE_REVERSAL,
            SetupType.FADE,
            SetupType.MEAN_REVERSION,
        },
        "default": SetupType.RANGE_REVERSAL,
        "blocked": {SetupType.TREND_FOLLOWING},
    },
    MarketRegime.COMPRESSION: {
        "allowed": {
            SetupType.BREAKOUT,
        },
        "default": SetupType.BREAKOUT,
    },
    MarketRegime.EXHAUSTION: {
        "allowed": {
            SetupType.REVERSAL,
        },
        "default": SetupType.REVERSAL,
        "blocked": {SetupType.TREND_FOLLOWING, SetupType.TREND_PULLBACK, SetupType.PULLBACK_SHORT},
    },
}

REGIME_TP_MAP = {
    MarketRegime.STRONG_TREND_UP: 1.0,
    MarketRegime.STRONG_TREND_DOWN: 1.0,
    MarketRegime.RANGING: 0.5,
    MarketRegime.COMPRESSION: 0.0,
    MarketRegime.EXHAUSTION: 0.35,
}

REGIME_LEVERAGE_MAP = {
    MarketRegime.STRONG_TREND_UP: 25,
    MarketRegime.STRONG_TREND_DOWN: 25,
    MarketRegime.RANGING: 10,
    MarketRegime.COMPRESSION: 8,
    MarketRegime.EXHAUSTION: 5,
}

REGIME_STRATEGY_MAP = {
    MarketRegime.STRONG_TREND_UP: "Comprar retracoes na tendencia de alta",
    MarketRegime.STRONG_TREND_DOWN: "Vender retracoes na tendencia de baixa",
    MarketRegime.RANGING: "Venda na resistencia, compra no suporte da faixa",
    MarketRegime.COMPRESSION: "Aguardar rompimento para entrar na direcao",
    MarketRegime.EXHAUSTION: "Aguardar reversao confirmada, nao continuacao",
}

REGIME_OBJECTIVE_MAP = {
    MarketRegime.STRONG_TREND_UP: "Capturar continuacao da tendencia",
    MarketRegime.STRONG_TREND_DOWN: "Capturar continuacao da tendencia",
    MarketRegime.RANGING: "Movimento curto entre as bordas",
    MarketRegime.COMPRESSION: "Movimento apos expansao",
    MarketRegime.EXHAUSTION: "Reversao do movimento extremo",
}

REGIME_CONTINUATION_MAP = {
    MarketRegime.STRONG_TREND_UP: "Alta",
    MarketRegime.STRONG_TREND_DOWN: "Alta",
    MarketRegime.RANGING: "Moderada",
    MarketRegime.COMPRESSION: "Baixa",
    MarketRegime.EXHAUSTION: "Baixa",
}


def _detect_setup_from_patterns(
    patterns,
    direction,
    structure,
    regime: MarketRegime,
) -> Optional[SetupType]:
    if regime in (MarketRegime.STRONG_TREND_UP, MarketRegime.STRONG_TREND_DOWN):
        has_pullback = any(
            p.type in (PatternType.ORDER_BLOCK, PatternType.FVG)
            and p.direction == direction
            for p in patterns
        )
        has_breakout = any(
            p.type in (PatternType.BOS, PatternType.CHOCH)
            and p.direction == direction
            for p in patterns
        )
        if has_pullback:
            return SetupType.TREND_PULLBACK if direction == SignalDirection.LONG else SetupType.PULLBACK_SHORT
        if has_breakout:
            return SetupType.TREND_BREAKOUT if direction == SignalDirection.LONG else SetupType.BREAKDOWN
        return SetupType.TREND_FOLLOWING

    if regime == MarketRegime.RANGING:
        has_reversal = any(
            p.type in (PatternType.LIQUIDITY_SWEEP, PatternType.CHOCH)
            for p in patterns
        )
        if has_reversal:
            return SetupType.RANGE_REVERSAL
        return SetupType.FADE

    if regime == MarketRegime.COMPRESSION:
        has_breakout = any(
            p.type in (PatternType.BOS, PatternType.CHOCH)
            for p in patterns
        )
        if has_breakout:
            return SetupType.BREAKOUT
        return None

    if regime == MarketRegime.EXHAUSTION:
        has_reversal = any(
            p.type in (PatternType.LIQUIDITY_SWEEP, PatternType.CHOCH)
            and p.direction == direction
            for p in patterns
        )
        if has_reversal:
            return SetupType.REVERSAL
        return None

    return None


class SetupSelector:
    def select_best_setup(
        self,
        regime: MarketRegime,
        direction: SignalDirection,
        patterns: list,
        structure: Optional[MarketStructure] = None,
    ) -> Optional[SetupRecommendation]:
        setup_info = REGIME_SETUP_MAP.get(regime)
        if not setup_info:
            log.warning("SetupSelector: regime %s sem configuracao", regime)
            return None

        detected = _detect_setup_from_patterns(patterns, direction, structure, regime)
        if detected is None:
            detected = setup_info["default"]

        if detected in setup_info.get("blocked", set()):
            log.warning("SetupSelector: setup %s bloqueado para regime %s", detected, regime)
            return None

        return SetupRecommendation(
            setup_type=detected,
            strategy_description=REGIME_STRATEGY_MAP.get(regime, ""),
            objective=REGIME_OBJECTIVE_MAP.get(regime, ""),
            tp_multiplier=REGIME_TP_MAP.get(regime, 0.5),
            max_leverage=REGIME_LEVERAGE_MAP.get(regime, 10),
            continuation_expected=REGIME_CONTINUATION_MAP.get(regime, "Moderada"),
        )

    def is_setup_compatible(self, setup: SetupType, regime: MarketRegime) -> bool:
        setup_info = REGIME_SETUP_MAP.get(regime)
        if not setup_info:
            return False
        if setup in setup_info.get("blocked", set()):
            return False
        if setup not in setup_info["allowed"]:
            return False
        return True

    def get_tp_multiplier(self, regime: MarketRegime) -> float:
        return REGIME_TP_MAP.get(regime, 0.5)

    def get_max_leverage(self, regime: MarketRegime) -> int:
        return REGIME_LEVERAGE_MAP.get(regime, 10)
