import math
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

from ENGINE.scanner.scanner_types import (
    SignalDirection, Signal, EntryDetails, PatternType, Pattern,
    MarketStructure, StructureType,
)
from ENGINE.scanner.scanner_config import (
    RR_BASE_SL_MULTIPLIER, RR_BASE_TP1_MULTIPLIER, RR_BASE_TP2_MULTIPLIER,
    RR_MIN_RR, RR_IDEAL_RR,
)

log = logging.getLogger(__name__)


def _price_precision(price: float) -> int:
    if price <= 0:
        return 8
    exp = int(math.floor(math.log10(abs(price))))
    # Para preços muito pequenos (altcoins), usar mais casas decimais
    # Para preços grandes (BTC), usar menos
    return max(4, -exp + 6)


@dataclass
class RiskResult:
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward: float
    rr_approved: bool
    reason: str = ""


def true_atr(
    highs: list,
    lows: list,
    closes: list,
    period: int = 14,
) -> float:
    """Calcula ATR verdadeiro usando True Range classico."""
    if len(closes) < period + 1 or len(highs) < period + 1 or len(lows) < period + 1:
        return 0.0
    tr_values = []
    for i in range(-period, 0):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr_values.append(max(hl, hc, lc))
    return sum(tr_values) / len(tr_values)


def calculate_entry_from_zone(
    entry_details: Optional[EntryDetails],
    current_price: float,
    direction: SignalDirection,
) -> float:
    """Define o preco de entrada priorizando Entry Zone.

    Prioridade:
    1. Melhor Order Block valido (ideal_price)
    2. Melhor FVG valido (ideal_price)
    3. Preco atual (fallback)
    """
    if entry_details and entry_details.approved:
        zone = getattr(entry_details, 'entry_zone', None) or getattr(entry_details, 'zone', None)
        if zone and getattr(zone, 'status', 'none') != 'none' and getattr(zone, 'ideal_price', 0) > 0:
            return zone.ideal_price
    return current_price


def calculate_stop_loss(
    entry: float,
    direction: SignalDirection,
    atr: float,
    structure: MarketStructure,
    patterns: list,
    highs: Optional[list] = None,
    lows: Optional[list] = None,
    closes: Optional[list] = None,
) -> float:
    """Calcula Stop Loss usando ATR verdadeiro, estrutura e Order Blocks.

    Prioridade:
    1. ATR verdadeiro * multiplicador base
    2. Estrutura (swing low/high)
    3. Order Block extremo
    """
    atr_val = atr
    if highs and lows and closes:
        true_atr_val = true_atr(highs, lows, closes)
        if true_atr_val > 0:
            atr_val = true_atr_val

    if atr_val <= 0:
        raise ValueError(
            f"Cannot calculate stop_loss: ATR={atr_val:.8f} for entry={entry:.8f} dir={direction}. "
            "Insufficient market data or all candles flat."
        )

    atr_dist = atr_val * RR_BASE_SL_MULTIPLIER

    structure = structure or MarketStructure(
        structure_type=StructureType.RANGING,
        swing_highs=[], swing_lows=[],
    )

    swing_sl = None
    if direction == SignalDirection.LONG:
        if structure.swing_lows:
            swing_sl = structure.swing_lows[-1].price
    else:
        if structure.swing_highs:
            swing_sl = structure.swing_highs[-1].price

    ob_sl = None
    for p in patterns:
        if p.type == PatternType.ORDER_BLOCK and p.direction == direction:
            meta = p.metadata or {}
            lower = meta.get('lower', 0)
            upper = meta.get('upper', 0)
            if direction == SignalDirection.LONG:
                ob_sl = lower if lower > 0 else (p.price - atr_dist * 0.5)
            else:
                ob_sl = upper if upper > 0 else (p.price + atr_dist * 0.5)
            break

    if direction == SignalDirection.LONG:
        atr_sl = entry - atr_dist
        sl = atr_sl
        if swing_sl is not None:
            sl = max(sl, swing_sl)
        if ob_sl is not None:
            sl = max(sl, ob_sl)
    else:
        atr_sl = entry + atr_dist
        sl = atr_sl
        if swing_sl is not None:
            sl = min(sl, swing_sl)
        if ob_sl is not None:
            sl = min(sl, ob_sl)

    sl_pct = abs(entry - sl) / entry if entry > 0 else 0.05
    max_sl_pct = min(atr / entry * 3.0 if entry > 0 else 0.05, 0.05)
    if sl_pct > max_sl_pct:
        if direction == SignalDirection.LONG:
            sl = entry * (1.0 - max_sl_pct)
        else:
            sl = entry * (1.0 + max_sl_pct)

    prec = _price_precision(sl)
    return round(sl, prec)


def calculate_take_profits(
    entry: float,
    stop_loss: float,
    direction: SignalDirection,
    atr: float,
    scores=None,
    closes: list = None,
    highs: list = None,
    lows: list = None,
) -> Tuple[float, float]:
    """Calcula TP1 e TP2 usando TP Adaptativo V19.0 se houver dados OHLC."""
    if closes and highs and lows and len(closes) > 30:
        try:
            from ENGINE.risk.tp_adaptativo import calculate_adaptive_tp
            dir_str = "LONG" if direction in (SignalDirection.LONG, "LONG", "BUY") else "SHORT"
            tp_result = calculate_adaptive_tp(
                entry=entry, stop_loss=stop_loss, direction=dir_str,
                atr=atr, closes=closes, highs=highs, lows=lows,
                trend_score=getattr(scores, 'trend_score', 0.5) if scores else 0.5,
                momentum=getattr(scores, 'momentum', 0.5) if scores else 0.5,
                adx=getattr(scores, 'adx', 25.0) if scores else 25.0,
                volume_ratio=getattr(scores, 'volume_ratio', 1.0) if scores else 1.0,
                trend_strength=getattr(scores, 'trend_strength', 0.5) if scores else 0.5,
                volatility_ratio=getattr(scores, 'volatility_ratio', 1.0) if scores else 1.0,
            )
            return tp_result.tp1, tp_result.tp2
        except Exception as e:
            log.warning("TPAdaptativo failed, falling back to fixed TP: %s", e)

    risk = abs(entry - stop_loss) if stop_loss != 0 else atr * RR_BASE_SL_MULTIPLIER
    tp1_mult = RR_BASE_TP1_MULTIPLIER
    tp2_mult = RR_BASE_TP2_MULTIPLIER
    if direction == SignalDirection.LONG:
        tp1 = entry + risk * tp1_mult
        tp2 = entry + risk * tp2_mult
    else:
        tp1 = entry - risk * tp1_mult
        tp2 = entry - risk * tp2_mult
    prec = _price_precision(entry)
    return round(tp1, prec), round(tp2, prec)


def calculate_risk_reward(
    entry: float,
    stop_loss: float,
    take_profit: float,
    direction: SignalDirection,
) -> float:
    if direction == SignalDirection.LONG:
        risk = entry - stop_loss
        reward = take_profit - entry
    else:
        risk = stop_loss - entry
        reward = entry - take_profit

    if risk <= 0:
        return 0.0
    return round(reward / risk, 2)


def compute_risk(
    entry: float,
    stop_loss: float,
    direction: SignalDirection,
) -> float:
    risk = abs(entry - stop_loss) / entry if entry > 0 else 0
    prec = _price_precision(entry) if entry > 0 else 8
    return round(risk, prec)


def apply(
    signal: Signal,
    direction: SignalDirection,
    atr: float,
    structure: MarketStructure,
    patterns: list,
    highs: Optional[list] = None,
    lows: Optional[list] = None,
    closes: Optional[list] = None,
) -> RiskResult:
    """Aplica o Risk Manager ao sinal apos aprovacao do Decision Engine.

    1. Determina entry price pela Entry Zone
    2. Calcula Stop Loss
    3. Calcula Take Profits
    4. Valida Risk/Reward minimo
    """
    entry_before = signal.entry_price
    entry = calculate_entry_from_zone(
        signal.entry_details, signal.entry_price, direction,
    )

    sl = calculate_stop_loss(
        entry, direction, atr, structure, patterns,
        highs=highs, lows=lows, closes=closes,
    )

    tp1, tp2 = calculate_take_profits(
        entry, sl, direction, atr,
        scores=signal.scores,
        closes=closes, highs=highs, lows=lows,
    )

    rr = calculate_risk_reward(entry, sl, tp1, direction)

    prec = max(2, _price_precision(entry))
    log.info(
        "RISK| sym=%s dir=%s entry_before=%.*f entry=%.*f sl=%.*f tp1=%.*f tp2=%.*f "
        "rr=%.2f atr=%.*f swing=%s ob=%s",
        signal.ticker, direction,
        prec, entry_before, prec, entry, prec, sl, prec, tp1, prec, tp2,
        rr, prec, atr,
        structure.structure_type if structure else 'none',
        'yes' if any(p.type == PatternType.ORDER_BLOCK for p in patterns) else 'no',
    )

    rr_approved = rr >= RR_MIN_RR
    reason = ""
    if not rr_approved:
        reason = f"RR {rr:.2f} abaixo do minimo {RR_MIN_RR}"
        log.warning("RiskManager: RR {:.2f} < {:.2f} para {}".format(rr, RR_MIN_RR, signal.ticker))

    if sl <= 0:
        raise ValueError(
            f"Stop loss calculado como {sl:.{prec}f} para {signal.ticker} "
            f"entry={entry:.{prec}f} direction={direction}. "
            f"ATR={atr:.{prec}f} invalido ou price precision {prec} insuficiente."
        )

    return RiskResult(
        entry_price=entry,
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=tp2,
        risk_reward=rr,
        rr_approved=rr_approved,
        reason=reason,
    )
