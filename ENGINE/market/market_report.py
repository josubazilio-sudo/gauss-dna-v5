import logging
from typing import List

from .market_types import MarketContext, MarketRegime, TrendDirection

log = logging.getLogger(__name__)


def generate_report(ctx: MarketContext) -> str:
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append(f"MARKET INTELLIGENCE REPORT — {ctx.pair}")
    lines.append(f"Timestamp: {ctx.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Price: {ctx.price:.4f}")
    lines.append("=" * 60)

    lines.append(f"\n📊 REGIME: {ctx.regime.value.upper()} (confidence: {ctx.regime_confidence:.2f})")
    lines.append(f"   Trend: {ctx.trend.value.upper()} (strength: {ctx.trend_strength:.2f})")

    lines.append(f"\n📈 TECHNICAL INDICATORS:")
    lines.append(f"   ADX: {ctx.indicators.adx:.1f} | RSI: {ctx.indicators.rsi:.1f} | RVOL: {ctx.indicators.rvol:.2f}")
    lines.append(f"   ATR: {ctx.indicators.atr:.4f} ({ctx.indicators.atr_percent*100:.2f}%)")
    lines.append(f"   BB Width: {ctx.indicators.bb_width:.4f} | BB Position: {ctx.indicators.bb_position:.2f}")
    lines.append(f"   Volume: {ctx.indicators.volume:.0f} | Avg Vol: {ctx.indicators.avg_volume:.0f}")

    lines.append(f"\n🎯 SCORES:")
    _add_score_line(lines, "Market Score", ctx.market_score)
    _add_score_line(lines, "Trend Score", ctx.trend_score)
    _add_score_line(lines, "Momentum Score", ctx.momentum_score)
    _add_score_line(lines, "Volatility Score", ctx.volatility_score)
    _add_score_line(lines, "Liquidity Score", ctx.liquidity_score)
    _add_score_line(lines, "Risk Score", ctx.risk_score)
    _add_score_line(lines, "Confidence Score", ctx.confidence_score)
    _add_score_line(lines, "Institutional Score", ctx.institutional_score)

    lines.append(f"\n💧 LIQUIDITY & FUNDING:")
    lines.append(f"   Spread: {ctx.spread:.4f}")
    lines.append(f"   Funding Rate: {ctx.funding_rate:.6f}")
    lines.append(f"   BTC Correlation: {ctx.btc_correlation:.2f} | ETH: {ctx.eth_correlation:.2f}")
    if ctx.btc_dominance:
        lines.append(f"   BTC Dominance: {ctx.btc_dominance:.2f}%")
    if ctx.open_interest is not None:
        lines.append(f"   Open Interest: {ctx.open_interest:.0f}")

    if ctx.timeframes:
        lines.append(f"\n⏰ MULTI-TIMEFRAME ({len(ctx.timeframes)} timeframes):")
        for tf_name, tf_ctx in sorted(ctx.timeframes.items()):
            lines.append(
                f"   {tf_name}: {tf_ctx.trend.value.upper()} "
                f"(strength: {tf_ctx.trend_strength:.2f}) "
                f"| {tf_ctx.regime.value.upper()} "
                f"(conf: {tf_ctx.regime_confidence:.2f})"
            )

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def generate_summary(ctx: MarketContext) -> str:
    return (
        f"[{ctx.pair}] {ctx.regime.value.upper()} | "
        f"Score: {ctx.market_score:.2f} | "
        f"Trend: {ctx.trend.value.upper()} ({ctx.trend_strength:.2f}) | "
        f"RSI: {ctx.indicators.rsi:.0f} | ADX: {ctx.indicators.adx:.0f} | "
        f"RVOL: {ctx.indicators.rvol:.1f}"
    )


def _add_score_line(lines: List[str], label: str, value: float) -> None:
    bar = "█" * int(value * 20) + "░" * (20 - int(value * 20))
    lines.append(f"   {label:20s}: {value:.3f} {bar}")
