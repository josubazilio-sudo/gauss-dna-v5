import hashlib
import logging
from typing import Any, Dict, List, Optional

from ENGINE.scanner.scanner_types import Signal, PatternType, EntryDetails, SignalDirection
from ENGINE.scanner.scanner_config import (
    ENTRY_ZONE_SCORE_MIN, CONSENSUS_MINIMUM_SCORE,
    QUALITY_GATE_MIN_SCORE, HARD_MIN_ADX, HARD_MIN_RVOL,
    HARD_MIN_STRUCTURE_STRENGTH, RR_MIN_RR,
    CONFIDENCE_GATE_MIN_SCORE, CONFIDENCE_QUALITY_MAX_DIFF, LATERAL_REGIMES,
    VOTE_WEIGHTS, VOTE_MIN_CONCORDANCE_PCT,
)
from ENGINE.risk.risk_manager import apply as apply_risk
from .signal_decision import SignalDecision

log = logging.getLogger(__name__)

DecisionResult = SignalDecision


def _log_result(trace_id: str, pair: str, direction: str, dr: SignalDecision):
    log.info(
        "TRACE[%s] %s %s | rvol=%s adx=%s struct=%s entry_zone=%s "
        "entry_score=%s quality=%s consensus=%s rr=%s | %s",
        trace_id, pair, direction,
        dr.rvol_ok, dr.adx_ok, dr.structure_ok, dr.entry_zone_ok,
        dr.entry_score_ok, dr.quality_ok, dr.consensus_ok, dr.rr_ok,
        dr.reject_reason,
    )


class DecisionEngine:

    @staticmethod
    def evaluate_signal(
        signal: Signal,
        entry_details: Optional[EntryDetails] = None,
        highs: Optional[List[float]] = None,
        lows: Optional[List[float]] = None,
        closes: Optional[List[float]] = None,
    ) -> SignalDecision:
        """Decision Engine simplificado — 8 hard gates essenciais.

        Fluxo: Hard Gates → Risk Manager (1x) → RR Gate → APROVADO.
        """
        sd = SignalDecision.from_signal(signal)
        scores = signal.scores

        quality = sd.quality

        # GATE 1: Dados de mercado válidos
        if not bool(signal.ticker) or signal.entry_price <= 0:
            sd.approved = False; sd.reject_reason = "Sem dados de mercado"
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # GATE 2: RVOL >= threshold
        if signal.rvol < HARD_MIN_RVOL:
            sd.approved = False; sd.reject_reason = f"RVOL {signal.rvol:.2f} < {HARD_MIN_RVOL}"
            sd.rvol_ok = False
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd
        sd.rvol_ok = True

        # GATE 3: ADX >= 25
        if signal.adx < HARD_MIN_ADX:
            sd.approved = False; sd.reject_reason = f"ADX {signal.adx:.1f} < {HARD_MIN_ADX}"
            sd.adx_ok = False
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd
        sd.adx_ok = True

        # GATE 4: BOS ou CHOCH confirmado
        has_bos = any(p.type == PatternType.BOS for p in signal.patterns)
        has_choch = any(p.type == PatternType.CHOCH for p in signal.patterns)
        if not (has_bos or has_choch):
            sd.approved = False; sd.reject_reason = "Sem BOS ou CHoCH confirmado"
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # GATE 5: Estrutura forte o suficiente
        if signal.structure_strength < HARD_MIN_STRUCTURE_STRENGTH:
            sd.approved = False
            sd.reject_reason = f"Forca estrutural {signal.structure_strength:.2f} < {HARD_MIN_STRUCTURE_STRENGTH}"
            sd.structure_ok = False
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd
        sd.structure_ok = True

        # GATE 6: Entry Zone
        entry_score = sd.entry_score
        entry_ok = entry_score >= ENTRY_ZONE_SCORE_MIN
        if entry_details is not None:
            entry_ok = entry_details.approved
        sd.entry_zone_ok = entry_ok
        sd.entry_zone_valid = entry_ok
        sd.entry_score_ok = entry_score >= ENTRY_ZONE_SCORE_MIN
        if not entry_ok:
            sd.approved = False
            sd.reject_reason = f"Entry Zone FAIL (score {entry_score:.2f} < {ENTRY_ZONE_SCORE_MIN})"
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # GATE 7: Quality >= threshold
        quality_ok = quality >= QUALITY_GATE_MIN_SCORE
        sd.quality_ok = quality_ok
        if not quality_ok:
            sd.approved = False; sd.reject_reason = f"Quality {quality:.2f} < {QUALITY_GATE_MIN_SCORE}"
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # Consensus (não eliminatório, usado no score final)
        consensus = sd.consensus
        cons_ok = consensus >= CONSENSUS_MINIMUM_SCORE
        sd.consensus_ok = cons_ok
        if not cons_ok:
            sd.approved = False; sd.reject_reason = f"Consensus {consensus:.2f} < {CONSENSUS_MINIMUM_SCORE}"
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # GATE 9: Confidence >= threshold (RFC_RECALIBRACAO_SINAIS_INSTITUCIONAL.md)
        confidence = sd.confidence
        confidence_ok = confidence >= CONFIDENCE_GATE_MIN_SCORE
        sd.confidence_ok = confidence_ok
        if not confidence_ok:
            sd.approved = False; sd.reject_reason = f"Confidence {confidence:.2f} < {CONFIDENCE_GATE_MIN_SCORE}"
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # GATE 10: Confianca nao pode se descolar da Qualidade alem do limite —
        # as duas medem coisas diferentes por design, mas uma diferenca grande
        # indica descalibracao entre as duas formulas, nao um setup real melhor.
        conf_qual_diff = confidence - quality
        if abs(conf_qual_diff) > CONFIDENCE_QUALITY_MAX_DIFF:
            sd.approved = False
            sd.reject_reason = (
                f"Descalibracao Confianca-Qualidade: {conf_qual_diff:.2f} "
                f"(limite {CONFIDENCE_QUALITY_MAX_DIFF})"
            )
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # GATE 11: Mercado lateral exige excecao estruturada (rompimento +
        # volume + estrutura + consenso), nao aprova por padrao.
        if signal.regime in LATERAL_REGIMES:
            rompimento_confirmado = has_bos or has_choch
            excecao_valida = (
                rompimento_confirmado
                and signal.volume_above_avg
                and signal.structure_valid
                and cons_ok
            )
            if not excecao_valida:
                sd.approved = False
                sd.reject_reason = (
                    "Mercado lateral sem excecao (rompimento+volume+estrutura+consenso) confirmada"
                )
                _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # GATE TREND (V18.6): Hard Gate de Tendencia — MA50/MA200
        # LONG: Price > MA50, Price > MA200, MA50 > MA200
        # SHORT: Price < MA50, Price < MA200, MA50 < MA200
        _entry_price = signal.entry_price
        _ma50 = signal.ema50
        _ma200 = signal.ema200
        _signal_dir_local = sd.direction.lower() if hasattr(sd.direction, 'lower') else str(sd.direction).lower()
        _is_long_tg = _signal_dir_local in ("long", "buy")
        _is_short_tg = _signal_dir_local in ("short", "sell")
        _trend_gate_fail = False
        if _is_long_tg and _ma50 > 0 and _ma200 > 0:
            if not (_entry_price > _ma50 and _entry_price > _ma200 and _ma50 > _ma200):
                sd.trend_gate_ok = False
                sd.approved = False
                sd.reject_reason = (
                    f"REJECT_LONG_ABOVE_TREND "
                    f"(entry={_entry_price:.4f} ma50={_ma50:.4f} ma200={_ma200:.4f})"
                )
                _trend_gate_fail = True
        elif _is_short_tg and _ma50 > 0 and _ma200 > 0:
            if not (_entry_price < _ma50 and _entry_price < _ma200 and _ma50 < _ma200):
                sd.trend_gate_ok = False
                sd.approved = False
                sd.reject_reason = (
                    f"REJECT_SHORT_AGAINST_TREND "
                    f"(entry={_entry_price:.4f} ma50={_ma50:.4f} ma200={_ma200:.4f})"
                )
                _trend_gate_fail = True
        if _ma50 > 0 and _ma200 > 0:
            sd.trend_gate_ok = sd.trend_gate_ok is not False
        if _trend_gate_fail:
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd)
            return sd

        # GATE 12 (V18.3): Regras do Kalman
        # LONG: UP ou NEUTRO permitidos. DOWN = rejeitar.
        # SHORT: DOWN ou NEUTRO permitidos. UP = rejeitar.
        kalman_raw = (signal.kalman_direction or "").upper()
        kalman_up = "UP" in kalman_raw or "ALT" in kalman_raw
        kalman_down = "DOWN" in kalman_raw or "BAIX" in kalman_raw
        kalman_neutral = not kalman_up and not kalman_down
        signal_dir = sd.direction.lower() if hasattr(sd.direction, 'lower') else str(sd.direction).lower()
        is_long = signal_dir in ("long", "buy")
        is_short = signal_dir in ("short", "sell")

        kalman_conflito = (is_long and kalman_down) or (is_short and kalman_up)
        if kalman_conflito:
            sd.approved = False
            sd.reject_reason = (
                f"Kalman {signal.kalman_direction} incompativel com {sd.direction.upper()} "
                f"(LONG permite UP/NEUTRO, SHORT permite DOWN/NEUTRO)"
            )
            sd.kalman_ok = False
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd
        sd.kalman_ok = True

        # GATE 13 (V18.3): Consistency Gate — todos os modulos devem concordar
        # com a direcao. Qualquer conflito grave = rejeitar.
        regime_lower = (signal.regime or "").lower()
        regime_dir = "up" if "up" in regime_lower else ("down" if "down" in regime_lower else "neutral")

        trend_aligned = (
            (is_long and regime_dir == "up") or
            (is_short and regime_dir == "down") or
            regime_dir == "neutral"
        )
        flow_ok = getattr(signal.scores, 'flow_score', 0) >= 0.3 if signal.scores else False
        liquidity_ok = getattr(signal.scores, 'liquidity_score', 0) >= 0.6 if signal.scores else False
        momentum_ok = getattr(signal.scores, 'momentum_score', 0) >= 0.5 if signal.scores else False

        consistency_checks = {
            "kalman": not kalman_conflito,
            "regime": trend_aligned,
            "flow": flow_ok,
            "liquidity": liquidity_ok,
            "momentum": momentum_ok,
            "structure": signal.structure_strength >= HARD_MIN_STRUCTURE_STRENGTH,
            "consensus": cons_ok,
        }

        if not trend_aligned:
            sd.approved = False
            sd.reject_reason = f"Consistency: Regime {signal.regime} conflita com direcao {sd.direction.upper()}"
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # GATE 14 (V18.4): Votacao Institucional Ponderada
        # Cada modulo vota com peso, exige 70% do peso total.
        vote_items = {
            "Kalman": not kalman_conflito,
            "Regime": trend_aligned,
            "Fluxo": flow_ok,
            "Liquidez": liquidity_ok,
            "Momentum": momentum_ok,
            "Consenso": cons_ok,
            "Qualidade": quality >= QUALITY_GATE_MIN_SCORE,
            "Confianca": confidence >= CONFIDENCE_GATE_MIN_SCORE,
            "Estrutura": signal.structure_strength >= HARD_MIN_STRUCTURE_STRENGTH,
            "Padrao": has_bos or has_choch,
        }
        vote_key_map = {
            "Kalman": "kalman", "Regime": "regime", "Fluxo": "fluxo",
            "Liquidez": "liquidez", "Momentum": "momentum", "Consenso": "consenso",
            "Qualidade": "qualidade", "Confianca": "confianca",
            "Estrutura": "estrutura", "Padrao": "padrao",
        }
        yes_weight = sum(
            VOTE_WEIGHTS[vote_key_map[lbl]]
            for lbl, v in vote_items.items() if v
        )
        total_vote_weight = sum(VOTE_WEIGHTS.values())
        concordance_pct = (yes_weight / total_vote_weight * 100) if total_vote_weight > 0 else 0

        if concordance_pct < VOTE_MIN_CONCORDANCE_PCT:
            sd.approved = False
            contra = [lbl for lbl, v in vote_items.items() if not v]
            sd.reject_reason = (
                f"Votacao Ponderada: {yes_weight:.0f}/{total_vote_weight} "
                f"({concordance_pct:.0f}%) < {VOTE_MIN_CONCORDANCE_PCT}%. "
                f"Contra: {', '.join(contra[:5])}"
            )
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # GATE 15 (V18.3): Nao permitir LONG contra tendencia baixa ou
        # SHORT contra tendencia alta sem confirmacao estrutural de reversao.
        trend_down = regime_dir == "down"
        trend_up = regime_dir == "up"
        contra_tendencia = (is_long and trend_down) or (not is_long and trend_up)
        if contra_tendencia:
            has_choch = any(p.type == PatternType.CHOCH for p in signal.patterns)
            has_bos = any(p.type == PatternType.BOS for p in signal.patterns)
            reversao_confirmada = has_choch and has_bos and signal.volume_above_avg and cons_ok
            if not reversao_confirmada:
                dir_label = "LONG" if is_long else "SHORT"
                trend_label = "baixa" if trend_down else "alta"
                sd.approved = False
                sd.reject_reason = (
                    f"{dir_label} contra tendencia {trend_label} sem reversao confirmada "
                    f"(CHoCH+BOS+volume+consenso)"
                )
                _log_result(sd.trace_id, sd.symbol, sd.direction, sd); return sd

        # APROVADO (Hard Gates) → Risk Manager (chamado UMA vez)
        direction = SignalDecision._to_direction(sd.direction)
        sig_structure = getattr(signal, 'structure', None)
        if sig_structure is None:
            from ENGINE.scanner.scanner_types import MarketStructure, StructureType
            sig_structure = MarketStructure(
                structure_type=StructureType.RANGING,
                swing_highs=[], swing_lows=[],
            )

        risk_result = apply_risk(
            signal=signal,
            direction=direction,
            atr=signal.atr_value,
            structure=sig_structure,
            patterns=signal.patterns,
            highs=highs, lows=lows, closes=closes,
        )

        sd.entry_price = risk_result.entry_price
        sd.stop_loss = risk_result.stop_loss
        sd.take_profit_1 = risk_result.take_profit_1
        sd.take_profit_2 = risk_result.take_profit_2
        sd.risk_reward = risk_result.risk_reward
        sd.rr_ok = risk_result.rr_approved

        # GATE 8: RR >= 2.0
        if not risk_result.rr_approved:
            sd.approved = False
            sd.reject_reason = risk_result.reason
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd)
            return sd

        # Validações finais de preço
        if sd.stop_loss <= 0 or sd.entry_price <= 0 or sd.take_profit_1 <= 0:
            sd.approved = False
            sd.reject_reason = "Precos invalidos apos Risk Manager"
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd)
            return sd

        # GATE 16 (V18.4): Final Validation Hard Gate — bloqueante
        # Nenhuma inconsistencia critica pode chegar ao Telegram.
        sd.coherence = {
            "direction": sd.direction,
            "kalman": signal.kalman_direction,
            "trend": signal.regime,
        }
        fv_errors = []

        if kalman_conflito:
            fv_errors.append(f"FV: Kalman {signal.kalman_direction} vs {sd.direction.upper()}")

        # Verificacoes que dependem de dados pos-decision (feitas em main.py
        # para classification/expectancy — aqui so o que temos no momento)
        if is_long and trend_down and not (has_choch and has_bos and signal.volume_above_avg and cons_ok):
            fv_errors.append(f"FV: LONG contra tendencia sem reversao")
        if is_short and trend_up and not (has_choch and has_bos and signal.volume_above_avg and cons_ok):
            fv_errors.append(f"FV: SHORT contra tendencia sem reversao")

        if fv_errors:
            sd.approved = False
            sd.reject_reason = "; ".join(fv_errors)
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd)
            return sd

        # APROVADO FINAL
        sd.approved = True
        sd.reject_reason = "APROVADO — Todos os filtros essenciais"
        _log_result(sd.trace_id, sd.symbol, sd.direction, sd)
        return sd

    @staticmethod
    def detect_mtf_conflict(decisions: List[SignalDecision]) -> dict:
        """V19.1: detecta conflito multi-timeframe entre sinais do mesmo par.

        Retorna dict {timeframe: bool} indicando se cada timeframe esta em
        conflito com pelo menos um outro timeframe do par.
        Conflito = direcao oposta (ex.: 1H LONG vs 4h SHORT).
        """
        directions = {}
        for d in decisions:
            dir_norm = d.direction.lower()
            if dir_norm in ("long", "buy"):
                directions[d.timeframe] = "LONG"
            elif dir_norm in ("short", "sell"):
                directions[d.timeframe] = "SHORT"

        if len(directions) < 2:
            return {d.timeframe: False for d in decisions}

        conflicts = {}
        for d in decisions:
            tf = d.timeframe
            my_dir = directions.get(tf, "")
            has_conflict = any(
                other_dir != my_dir
                for other_tf, other_dir in directions.items()
                if other_tf != tf
            ) if my_dir else False
            conflicts[tf] = has_conflict

        return conflicts
