import logging
from typing import Any, List, Tuple

from ..bot_config import BotConfig
from ..bot_types import SignalApproval
from .signal_receiver import SignalData

log = logging.getLogger(__name__)


class SignalValidator:
    def __init__(self, config: BotConfig):
        self._config = config

    def validate(self, signal: SignalData, current_market_price: float,
                 market_ctx: Any) -> Tuple[SignalApproval, List[str]]:
        reasons: List[str] = []

        # ============================================================
        # 1 — VALIDAÇÃO DO PREÇO (v4.0: >0.50% recalcular, >1% cancelar)
        # ============================================================
        distance = abs(signal.entry_price - current_market_price) / current_market_price
        if distance > self._config.max_entry_distance_cancel:
            reasons.append(
                f"[REGRA ZERO] Distância {distance:.2%} > {self._config.max_entry_distance_cancel:.0%} — CANCELADO"
            )
        elif distance > self._config.max_entry_distance_recalc:
            reasons.append(
                f"[REGRA ZERO] Distância {distance:.2%} > {self._config.max_entry_distance_recalc:.2%} — RECALCULAR"
            )

        # ============================================================
        # 2 — VALIDAÇÃO DA ENTRADA (tipo permitido)
        # ============================================================
        if signal.entry_type and signal.entry_type not in SignalData.VALID_ENTRY_TYPES:
            reasons.append(f"[ENTRADA] Tipo '{signal.entry_type}' não permitido")

        # ============================================================
        # 3 — FILTRO DE FALSO ROMPIMENTO
        # ============================================================
        if not signal.false_breakout_clear:
            reasons.append("[FALSO ROMPIMENTO] Não confirmado — fechamento, volume ou estrutura falharam")
        if not signal.rvol_confirmed:
            reasons.append("[RVOL] Volume relativo não confirmado")
        if not signal.no_absorption:
            reasons.append("[ABSORÇÃO] Absorção institucional detectada")
        if not signal.no_rejection:
            reasons.append("[REJEIÇÃO] Rejeição forte detectada (pavio excessivo)")
        if not signal.volume_above_avg:
            reasons.append("[VOLUME] Volume abaixo da média")

        # ============================================================
        # 4 — FILTRO DE ARMADILHAS
        # ============================================================
        if not signal.traps_clear:
            reasons.append("[ARMADILHA] Stop Hunt / Sweep / OB contrário / FVG contrário detectado")

        # ============================================================
        # 5 — VALIDAÇÃO DO STOP (atrás da estrutura)
        # ============================================================
        if signal.atr > 0:
            if signal.direction.lower() == "long":
                stop_distance = signal.entry_price - signal.stop_loss
                if stop_distance < signal.atr * 0.3:
                    reasons.append(f"[STOP] Stop dentro do ruído ({stop_distance:.2f} < {signal.atr * 0.3:.2f} ATR*0.3)")
            else:
                stop_distance = signal.stop_loss - signal.entry_price
                if stop_distance < signal.atr * 0.3:
                    reasons.append(f"[STOP] Stop dentro do ruído ({stop_distance:.2f} < {signal.atr * 0.3:.2f} ATR*0.3)")

        # ============================================================
        # 6 — VALIDAÇÃO DOS ALVOS
        # ============================================================
        if signal.direction.lower() == "long":
            if market_ctx and hasattr(market_ctx, "indicators"):
                if market_ctx.indicators.ema200 > signal.entry_price and market_ctx.indicators.ema200 < signal.take_profit_1:
                    reasons.append("[TP] Resistência EMA200 antes do TP1")
            if signal.atr > 0:
                tp1_distance = signal.take_profit_1 - signal.entry_price
                expected_bars = tp1_distance / signal.atr
                if expected_bars > 48:
                    reasons.append(f"[TP] TP1 exigiria ~{expected_bars:.0f} candles — irrealista para {signal.timeframe}")
        else:
            if market_ctx and hasattr(market_ctx, "indicators"):
                if market_ctx.indicators.ema200 < signal.entry_price and market_ctx.indicators.ema200 > signal.take_profit_1:
                    reasons.append("[TP] Suporte EMA200 antes do TP1")
            if signal.atr > 0:
                tp1_distance = signal.entry_price - signal.take_profit_1
                expected_bars = tp1_distance / signal.atr
                if expected_bars > 48:
                    reasons.append(f"[TP] TP1 exigiria ~{expected_bars:.0f} candles — irrealista para {signal.timeframe}")

        # ============================================================
        # 7 — RISK REWARD
        # ============================================================
        rr_tp1 = self._calculate_rr(signal, signal.take_profit_1)
        rr_tp2 = self._calculate_rr(signal, signal.take_profit_2) if signal.take_profit_2 > 0 else 0.0
        if rr_tp1 < self._config.min_risk_reward:
            reasons.append(f"[RR] RR TP1 {rr_tp1:.2f} < mínimo {self._config.min_risk_reward}:1")

        # ============================================================
        # 8 — QUALIDADE DO SINAL (v4.0 gates)
        # ============================================================
        if signal.confidence < self._config.min_confidence:
            reasons.append(f"[CONFIANÇA] {signal.confidence:.0%} < {self._config.min_confidence:.0%}")
        if signal.quality < self._config.min_quality:
            reasons.append(f"[QUALIDADE] {signal.quality:.0%} < {self._config.min_quality:.0%}")
        if signal.score < self._config.min_institutional_score:
            reasons.append(f"[SCORE INST] {signal.score:.1f} < {self._config.min_institutional_score:.0f}")
        if signal.structural_score < self._config.min_structural_score:
            reasons.append(f"[SCORE ESTRUT] {signal.structural_score:.1f} < {self._config.min_structural_score:.0f}")
        if not signal.structure_valid:
            reasons.append("[ESTRUTURA] Estrutura de mercado inválida")
        if not signal.volume_above_avg:
            reasons.append("[VOLUME] Volume abaixo da média")

        # ============================================================
        # Validações gerais (campos obrigatórios)
        # ============================================================
        if not signal.direction:
            reasons.append("Empty direction")
        if signal.entry_price <= 0:
            reasons.append("Invalid entry price")
        if signal.stop_loss <= 0:
            reasons.append("Invalid stop loss")
        if signal.take_profit_1 <= 0:
            reasons.append("Invalid take profit 1")
        if signal.confidence < self._config.min_confidence:
            reasons.append(f"Confidence {signal.confidence:.2f} < min {self._config.min_confidence}")
        if signal.pair not in self._config.pairs:
            reasons.append(f"Pair {signal.pair} not in configured pairs")

        # ============================================================
        # DECISÃO FINAL
        # ============================================================
        if reasons:
            log.info(
                "SignalValidator v4.0: REJEITADO %s %s (%d razões): %s",
                signal.pair, signal.direction, len(reasons), "; ".join(reasons),
            )
            return SignalApproval.REJECTED, reasons

        log.info(
            "SignalValidator v4.0: APROVADO %s %s | RR TP1=%.2f TP2=%.2f | Dist=%.2f%%",
            signal.pair, signal.direction, rr_tp1, rr_tp2, distance * 100,
        )
        return SignalApproval.APPROVED, [
            "✓ Baseline v4.0 — Todos os 16 checks passaram",
            f"✓ Dist={distance:.2%} RR TP1={rr_tp1:.2f} TP2={rr_tp2:.2f}",
            f"✓ Conf={signal.confidence:.0%} Qual={signal.quality:.0%}",
            f"✓ ScoreInst={signal.score:.0f} ScoreEstrut={signal.structural_score:.0f}",
        ]

    def _calculate_rr(self, signal: SignalData, target: float) -> float:
        if signal.direction.lower() == "long":
            potential = target - signal.entry_price
            risk = signal.entry_price - signal.stop_loss
        else:
            potential = signal.entry_price - target
            risk = signal.stop_loss - signal.entry_price
        if risk <= 0:
            return 0.0
        return potential / risk
