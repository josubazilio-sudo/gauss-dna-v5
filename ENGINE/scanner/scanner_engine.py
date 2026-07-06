import logging
import time
import concurrent.futures
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ENGINE.market.market_types import Candle, MarketContext
from ENGINE.market.market_trend import compute_adx
from ENGINE.market.market_momentum import compute_rsi, compute_rvol

from .scanner_types import (
    SignalDirection, SignalClassification, ScannerScore,
    Pattern, MarketStructure, Signal, ScanReport,
)
from .scanner_config import DEFAULT_TIMEFRAMES, SCORE_THRESHOLD_PRATA, QUALITY_GATE_RISK_MAX
from .scanner_patterns import scan_all_patterns
from .scanner_structure import analyze_structure
from .scanner_scoring import compute_all_scanner_scores, classify_signal, check_quality_gate
from .scanner_signal import build_signal
from .scanner_ranker import pipeline as rank_pipeline

log = logging.getLogger(__name__)


class ScannerEngine:
    def __init__(self, timeframes: Optional[List[str]] = None):
        self._timeframes = timeframes or DEFAULT_TIMEFRAMES
        self._last_scan: Optional[ScanReport] = None

    def scan(
        self,
        pair: str,
        candles: Dict[str, List[Candle]],
        market_ctx: MarketContext,
        funding_rate: float = 0.0,
        spread: float = 0.0,
    ) -> ScanReport:
        if not candles:
            raise ValueError("At least one timeframe with candles is required")

        start = time.time()
        errors: List[str] = []
        all_signals: List[Signal] = []
        total_patterns = 0

        tf_candles = self._resolve_timeframes(candles)
        main_candles = tf_candles.get("1h", tf_candles.get("15m", next(iter(tf_candles.values()))))

        for tf, tf_candles_list in tf_candles.items():
            try:
                if len(tf_candles_list) < 20:
                    continue

                patterns = scan_all_patterns(tf_candles_list, tf)
                structure = analyze_structure(tf_candles_list)

                total_patterns += len(patterns)

                if not patterns:
                    continue

                rsi = compute_rsi(tf_candles_list)
                rvol = compute_rvol(tf_candles_list)

                scores = compute_all_scanner_scores(
                    structure=structure,
                    patterns=patterns,
                    market_score=market_ctx.market_score,
                    trend_score=market_ctx.trend_score,
                    rsi=rsi,
                    rvol=rvol,
                    atr_percent=market_ctx.indicators.atr_percent,
                    liquidity_score=market_ctx.liquidity_score,
                    spread=spread,
                    mkt_trend=market_ctx.trend,
                    mkt_regime_confidence=market_ctx.regime_confidence,
                )

                classification = classify_signal(scores)
                passed_gate, rejection_reasons = check_quality_gate(scores)

                dir_pref = SignalDirection.LONG if scores.structural_score > 0.5 else SignalDirection.SHORT
                direction = _dominant_direction(patterns, dir_pref)

                current_price = tf_candles_list[-1].close
                signal = build_signal(
                    ticker=pair,
                    timeframe=tf,
                    direction=direction,
                    patterns=patterns,
                    structure=structure,
                    scores=scores,
                    classification=classification,
                    current_price=current_price,
                    atr=market_ctx.indicators.atr,
                    approval_reasons=[] if passed_gate else None,
                    rejection_reasons=rejection_reasons if not passed_gate else None,
                )
                all_signals.append(signal)

            except Exception as e:
                errors.append(f"TF {tf}: {e}")
                log.warning(f"Scan error on {pair} TF {tf}: {e}")

        final_signals = rank_pipeline(all_signals)
        elapsed = (time.time() - start) * 1000

        report = ScanReport(
            pair=pair,
            timestamp=datetime.now(timezone.utc),
            timeframes_analyzed=len(tf_candles),
            total_patterns_found=total_patterns,
            signals=final_signals,
            errors=errors,
            duration_ms=round(elapsed, 2),
        )
        self._last_scan = report
        return report

    def last_scan(self) -> Optional[ScanReport]:
        return self._last_scan

    def scan_multi(
        self,
        pairs_candles: Dict[str, Dict[str, List[Candle]]],
        market_contexts: Dict[str, MarketContext],
        funding_map: Optional[Dict[str, float]] = None,
        spread_map: Optional[Dict[str, float]] = None,
    ) -> Dict[str, ScanReport]:
        results = {}
        with concurrent.futures.ProcessPoolExecutor() as executor:
            future_to_pair = {
                executor.submit(
                    self.scan,
                    pair,
                    tf_candles,
                    market_contexts[pair],
                    (funding_map or {}).get(pair, 0.0),
                    (spread_map or {}).get(pair, 0.0)
                ): pair
                for pair, tf_candles in pairs_candles.items()
                if pair in market_contexts
            }
            for future in concurrent.futures.as_completed(future_to_pair):
                pair = future_to_pair[future]
                try:
                    results[pair] = future.result()
                except Exception as e:
                    log.error(f"Scan failed for {pair}: {e}")
        return results

    def _resolve_timeframes(self, candles: Dict[str, List[Candle]]) -> Dict[str, List[Candle]]:
        result = {}
        for tf in self._timeframes:
            if tf in candles and len(candles[tf]) >= 20:
                result[tf] = candles[tf]
        if not result:
            for tf, c in candles.items():
                if len(c) >= 20:
                    result[tf] = c
                    break
            if not result:
                first_key = next(iter(candles))
                result[first_key] = candles[first_key]
        return result


def _dominant_direction(patterns: List[Pattern], fallback: SignalDirection) -> SignalDirection:
    longs = sum(1 for p in patterns if p.direction == SignalDirection.LONG)
    shorts = sum(1 for p in patterns if p.direction == SignalDirection.SHORT)
    if longs > shorts:
        return SignalDirection.LONG
    if shorts > longs:
        return SignalDirection.SHORT
    return fallback
