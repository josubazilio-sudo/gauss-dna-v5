import logging
from typing import List

from .scanner_types import Signal, ScanReport, SignalClassification

log = logging.getLogger(__name__)


def generate_report(report: ScanReport) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append(f"SCAN REPORT — {report.pair}")
    lines.append(f"Timestamp: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Timeframes: {report.timeframes_analyzed} | Patterns: {report.total_patterns_found}")
    lines.append(f"Duration: {report.duration_ms:.1f}ms")
    lines.append("=" * 70)

    if report.errors:
        lines.append(f"\n⚠ ERRORS ({len(report.errors)}):")
        for e in report.errors:
            lines.append(f"  - {e}")

    passed = [s for s in report.signals if s.classification != SignalClassification.REPROVADO]
    rejected = [s for s in report.signals if s.classification == SignalClassification.REPROVADO]

    if passed:
        lines.append(f"\n✅ SIGNALS ({len(passed)}):")
        for s in passed:
            lines.append(_format_signal(s))
    if rejected:
        lines.append(f"\n❌ REJECTED ({len(rejected)}):")
        for s in rejected:
            lines.append(_format_signal(s))

    if not report.signals:
        lines.append("\nNo signals found in this cycle.")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def _format_signal(s: Signal) -> str:
    cls_icon = {
        SignalClassification.OURO_SUPREMO: "🏆",
        SignalClassification.OURO: "🥇",
        SignalClassification.PRATA: "🥈",
        SignalClassification.BRONZE: "🥉",
        SignalClassification.REPROVADO: "❌",
    }.get(s.classification, "📊")
    return (
        f"\n  {cls_icon} [{s.classification.value.upper()}] {s.ticker} {s.timeframe} {s.direction.value.upper()}"
        f"\n     Entry: {s.entry_price:.4f} | SL: {s.stop_loss:.4f} | TP1: {s.take_profit_1:.4f} | TP2: {s.take_profit_2:.4f}"
        f"\n     RR: {s.risk_reward:.2f} | Quality: {s.quality:.2f} | Confidence: {s.confidence:.2f}"
        f"\n     Patterns: {', '.join(p.type.value for p in s.patterns[:3])}"
        f"\n     Setup: {s.setup[:120]}"
        f"\n     Context: {s.context[:120]}"
    )
