import logging
import os
import time
import concurrent.futures
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ENGINE.market.market_types import Candle, MarketContext
from ENGINE.market.market_trend import compute_adx
from ENGINE.market.market_momentum import compute_rsi, compute_rvol, compute_avg_volume
from ENGINE.consensus.consensus_engine import ConsensusEngine
from ENGINE.confluence.confluence_engine import ConfluenceEngine
from ENGINE.indicators.kalman import (
    kalman_direction,
    kalman_confidence,
    kalman_trend_state,
    kalman_tendency,
)

from .scanner_types import (
    SignalDirection, SignalClassification, MarketStructure,
    PatternType, Pattern, Signal, ScanReport,
)
from .scanner_config import (
    DEFAULT_TIMEFRAMES, CONSENSUS_MINIMUM_SCORE,
    HARD_MIN_RVOL, HARD_MIN_STRUCTURE_STRENGTH,
)
from .scanner_patterns import scan_all_patterns
from .scanner_structure import analyze_structure
from .scanner_scoring import (
    compute_all_scanner_scores, compute_quality_score, classify_signal,
    score_institutional, rescale_to_ceiling,
)
from .scanner_signal import build_signal, verify_direction_alignment, generate_approval_reasons
from .entry_zone import calculate_entry_zone
from .scanner_ranker import pipeline as rank_pipeline
from .flex_scoring import (
    compute_exaustao, compute_flow_data_from_candles, compute_flow_score,
    compute_timing_index, compute_follow_through,
    compute_conviction_score,
)


log = logging.getLogger(__name__)


class ScannerEngine:
    def __init__(self, timeframes: Optional[List[str]] = None):
        self._timeframes = timeframes or DEFAULT_TIMEFRAMES
        self._last_scan: Optional[ScanReport] = None
        self._consensus = ConsensusEngine()
        self._confluence = ConfluenceEngine()

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

                pattern_dir = SignalDirection.LONG
                dir_counts = {SignalDirection.LONG: 0, SignalDirection.SHORT: 0}
                for p in patterns:
                    if p.direction in dir_counts:
                        dir_counts[p.direction] += 1
                if dir_counts[SignalDirection.SHORT] > dir_counts[SignalDirection.LONG]:
                    pattern_dir = SignalDirection.SHORT

                confluence = self._confluence.compute(
                    patterns=patterns,
                    structure=structure,
                    direction=pattern_dir,
                    adx=market_ctx.indicators.adx,
                    rvol=rvol,
                    atr_percent=market_ctx.indicators.atr_percent,
                    regime=market_ctx.regime.value if hasattr(market_ctx.regime, 'value') else str(market_ctx.regime),
                    scores=scores,
                )

                if confluence.lateral_market_score > 0.8:
                    log.info("ScannerEngine: %s %s — lateral market excessivo, skipping", pair, tf)
                    continue

                dir_pref = SignalDirection.LONG if confluence.normalized_score >= 50 else SignalDirection.SHORT
                direction = _resolve_direction(patterns, dir_pref, structure)

                direction_confirmed, alignment_warnings = verify_direction_alignment(direction, structure, patterns)

                current_price = tf_candles_list[-1].close
                volume = tf_candles_list[-1].volume if hasattr(tf_candles_list[-1], 'volume') else 0.0

                entry_details = calculate_entry_zone(
                    patterns, current_price, market_ctx.indicators.atr,
                    candles=tf_candles_list, direction=direction,
                )

                zone_attr = getattr(entry_details, 'entry_zone', None) or getattr(entry_details, 'zone', None)
                entry_zone_val = zone_attr.status if zone_attr else ""

                smc_data = {
                    "BOS": any(p.type == PatternType.BOS and p.direction == direction for p in patterns),
                    "CHOCH": any(p.type == PatternType.CHOCH and p.direction == direction for p in patterns),
                    "LIQUIDITY_SWEEP": any(p.type == PatternType.LIQUIDITY_SWEEP and p.direction == direction for p in patterns),
                    "ORDER_BLOCK": any(p.type == PatternType.ORDER_BLOCK and p.direction == direction for p in patterns),
                    "FVG": any(p.type == PatternType.FVG and p.direction == direction for p in patterns),
                }

                avg_volume = compute_avg_volume(tf_candles_list)

                opposite_direction = (
                    SignalDirection.SHORT if direction == SignalDirection.LONG else SignalDirection.LONG
                )
                has_adverse_pattern = any(
                    p.type in (PatternType.LIQUIDITY_SWEEP, PatternType.ORDER_BLOCK, PatternType.FVG)
                    and p.direction == opposite_direction
                    for p in patterns
                )
                traps_clear = not has_adverse_pattern
                volume_above_avg = avg_volume > 0 and volume >= avg_volume
                rvol_confirmed = rvol >= HARD_MIN_RVOL
                structure_valid = structure.structure_strength >= HARD_MIN_STRUCTURE_STRENGTH
                false_breakout_clear = direction_confirmed

                closes_series = [c.close for c in tf_candles_list]
                flow_data = compute_flow_data_from_candles(
                    patterns=patterns, rvol=rvol, volume=volume, avg_volume=avg_volume,
                    direction=direction, closes=closes_series,
                    highs=[c.high for c in tf_candles_list],
                    lows=[c.low for c in tf_candles_list],
                    adx=market_ctx.indicators.adx,
                )
                flow_score = compute_flow_score(flow_data, direction)
                kalman_dir = kalman_direction(closes_series)
                kalman_conf = kalman_confidence(closes_series)
                kalman_state = kalman_trend_state(closes_series)
                kalman_tend = kalman_tendency(closes_series)

                if kalman_dir == "ERRO":
                    log.warning("ScannerEngine: %s %s — Kalman ERRO, skipping signal", pair, tf)
                    continue
                timing_idx = compute_timing_index(
                    patterns, structure, rvol,
                    flow_data.get("volume_crescente", False),
                    kalman_dir=kalman_dir,
                    kalman_confidence=kalman_conf,
                    current_price=current_price,
                    ema21=market_ctx.indicators.ema_21,
                    rsi=rsi,
                )
                exaustao = compute_exaustao(
                    rsi=rsi,
                    adx=market_ctx.indicators.adx,
                    atr_percent=market_ctx.indicators.atr_percent,
                    rvol=rvol,
                    kalman_tendency=kalman_tend,
                    closes=closes_series,
                    highs=[c.high for c in tf_candles_list],
                    lows=[c.low for c in tf_candles_list],
                    volumes=[c.volume for c in tf_candles_list],
                    direction=direction,
                    current_price=current_price,
                )
                ft_score, ft_explicacao = compute_follow_through(tf_candles_list, direction, smc_data)
                conv_score, conv_factors, conv_explicacao = compute_conviction_score(
                    flow_score=flow_score,
                    follow_through_score=ft_score,
                    timing_index=timing_idx,
                    adx=market_ctx.indicators.adx,
                    rvol=rvol,
                    volume_crescente=flow_data.get("volume_crescente", False),
                    patterns=patterns,
                    structure=structure,
                    kalman_dir=kalman_dir,
                    kalman_confidence=kalman_conf,
                    kalman_trend_state=kalman_state,
                    kalman_tendency=kalman_tend,
                    atr_pct=market_ctx.indicators.atr_percent,
                    rsi=rsi,
                    direction=direction,
                )
                scores.conviction_score = rescale_to_ceiling(conv_score, "conviction_score")
                scores.flow_score = rescale_to_ceiling(flow_score, "flow_score")
                scores.follow_through = ft_score
                scores.timing_index = timing_idx

                # institutional_score foi calculado em compute_all_scanner_scores()
                # com flow_score=0.0 (default, ainda nao computado naquele ponto) —
                # recalcula agora que flow/structural/risk (ja reescalados) estao
                # disponiveis, senao institutional_score fica permanentemente sem
                # a contribuicao de flow.
                scores.institutional_score = score_institutional(
                    scores.structural_score, scores.market_score, scores.momentum_score,
                    scores.liquidity_score, scores.risk_score, scores.confidence_score,
                    scores.flow_score,
                )
                scores.quality_score = compute_quality_score(scores)

                # Classificacao provisoria (consensus_score multi-TF ainda nao calculado
                # nesta altura — sera recalculada apos o consenso, mais abaixo).
                classification = classify_signal(scores)
                approval_reasons = generate_approval_reasons(patterns, structure, scores, direction, rvol)
                approval_reasons.extend(aw for aw in alignment_warnings if aw not in approval_reasons)

                ob_dist = 0.0
                fvg_dist = 0.0
                for p in patterns:
                    if p.type == PatternType.ORDER_BLOCK and ob_dist == 0.0:
                        ob_dist = abs(current_price - p.price)
                    elif p.type == PatternType.FVG and fvg_dist == 0.0:
                        fvg_dist = abs(current_price - p.price)

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
                    approval_reasons=approval_reasons,
                    rejection_reasons=None,
                    rvol=rvol,
                    adx=market_ctx.indicators.adx,
                    regime=market_ctx.regime.value if hasattr(market_ctx.regime, 'value') else str(market_ctx.regime),
                    volume=volume,
                    entry_score=entry_details.score,
                    consensus_score=0.0,
                    entry_zone=entry_zone_val,
                    order_block_distance=round(ob_dist, 2),
                    fvg_distance=round(fvg_dist, 2),
                    validity="",
                    entry_details=entry_details,
                    kalman_direction=kalman_dir,
                    kalman_confidence=kalman_conf,
                    kalman_trend_state=kalman_state,
                    kalman_tendency=kalman_tend,
                    classification_label=classification.value if hasattr(classification, 'value') else str(classification),
                    structure_valid=structure_valid,
                    false_breakout_clear=false_breakout_clear,
                    traps_clear=traps_clear,
                    volume_above_avg=volume_above_avg,
                    rvol_confirmed=rvol_confirmed,
                )

                if exaustao.bloquear:
                    log.info(
                        "ScannerEngine: %s %s — exaustao bloqueando sinal (score=%.0f: %s)",
                        pair, tf, exaustao.score, ", ".join(exaustao.reasons),
                    )
                    signal.classification = SignalClassification.REPROVADO
                    signal.classification_label = SignalClassification.REPROVADO.value
                    signal.rejection_reasons.append(
                        f"Exaustao detectada (score={exaustao.score:.0f}): {', '.join(exaustao.reasons)}"
                    )

                all_signals.append(signal)

            except Exception as e:
                errors.append(f"TF {tf}: {e}")
                import traceback
                log.error(f"Scan error on {pair} TF {tf}: {e}\n{traceback.format_exc()}")

        if all_signals:
            directions: Dict[str, SignalDirection] = {}
            tf_scores: Dict[str, float] = {}
            tf_confidence: Dict[str, float] = {}
            primary_entry_score = all_signals[0].scores.entry_score
            primary_quality = all_signals[0].scores.quality_score
            for s in all_signals:
                directions[s.timeframe] = s.direction
                tf_scores[s.timeframe] = s.scores.quality_score
                tf_confidence[s.timeframe] = s.scores.confidence_score

            consensus = self._consensus.compute(
                directions, tf_scores, tf_confidence,
                entry_score=primary_entry_score, quality_score=primary_quality,
            )

            consensus_ok = consensus.meets_minimum(CONSENSUS_MINIMUM_SCORE)
            if not consensus_ok:
                log.info(
                    "ScannerEngine: %s — consensus %.2f < %.2f (TFs=%d), rejecting all signals",
                    pair, consensus.consensus_score, CONSENSUS_MINIMUM_SCORE, len(all_signals),
                )

            for s in all_signals:
                # Consensus so e conhecido apos avaliar todos os timeframes — a
                # classificacao provisoria (feita antes, com consensus_score=0)
                # precisa ser recalculada agora que o valor real esta disponivel.
                s.scores.consensus_score = consensus.consensus_score
                if not consensus_ok:
                    s.approval_reasons = []
                    s.rejection_reasons.append(
                        f"Consenso multi-TF insuficiente ({consensus.consensus_score:.2f} < {CONSENSUS_MINIMUM_SCORE})"
                    )
                    s.classification = SignalClassification.REPROVADO
                    s.classification_label = SignalClassification.REPROVADO.value
                elif not s.rejection_reasons:
                    s.classification = classify_signal(s.scores)
                    s.classification_label = s.classification.value if hasattr(s.classification, 'value') else str(s.classification)

                consensus_str = (
                    f"Consenso: {consensus.consensus_score:.2f} | "
                    f"Direcao: {consensus.final_direction.value} | "
                    f"Classificacao: {consensus.classification}"
                )
                if consensus.dissenting_timeframes:
                    dissenting = ", ".join(consensus.dissenting_timeframes)
                    consensus_str += f" | Divergentes: {dissenting}"
                s.explanation = consensus_str

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
        executor_class = concurrent.futures.ThreadPoolExecutor
        if os.name != "nt":
            executor_class = concurrent.futures.ProcessPoolExecutor
        with executor_class() as executor:
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


def _resolve_direction(
    patterns: List[Pattern], fallback: SignalDirection,
    structure: Optional[MarketStructure] = None,
) -> SignalDirection:
    from .scanner_signal import _resolve_direction as _rd
    return _rd(patterns, fallback, structure)
