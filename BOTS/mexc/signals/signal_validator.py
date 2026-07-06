import logging
from typing import List, Tuple

from ..bot_config import BotConfig
from ..bot_types import SignalApproval
from .signal_receiver import SignalData

log = logging.getLogger(__name__)


class SignalValidator:
    def __init__(self, config: BotConfig):
        self._config = config

    def validate(self, signal: SignalData, current_market_price: float, market_ctx: Any) -> Tuple[SignalApproval, List[str]]:
        reasons: List[str] = []
        
        # 1. Filtro de Distância (Hard Filter 1%)
        distance = abs(signal.entry_price - current_market_price) / current_market_price
        if distance > 0.01:
            reasons.append(f"Distância da entrada {distance:.2%} > 1.0% (REJEITADO)")
        
        # 2. Filtro de Resistência/Suporte Institucional (Novo v3.0)
        if signal.direction.lower() == "long":
            if market_ctx.indicators.ema200 > signal.entry_price and market_ctx.indicators.ema200 < signal.take_profit_1:
                reasons.append("Resistência EMA200 detectada antes do TP1")
        elif signal.direction.lower() == "short":
            if market_ctx.indicators.ema200 < signal.entry_price and market_ctx.indicators.ema200 > signal.take_profit_1:
                reasons.append("Suporte EMA200 detectado antes do TP1")

        # 3. Validação de Score Institucional v3.0
        if signal.confidence < 0.85 or signal.quality < 0.85:
            reasons.append("Confidence/Quality abaixo do gate institucional 85%")

        if not signal.direction:
            reasons.append("Empty direction")
        if signal.entry_price <= 0:
            reasons.append("Invalid entry price")
        if signal.stop_loss <= 0:
            reasons.append("Invalid stop loss")
        if signal.take_profit_1 <= 0:
            reasons.append("Invalid take profit 1")
        if signal.take_profit_2 <= 0:
            reasons.append("Invalid take profit 2")
        if signal.confidence < self._config.min_confidence:
            reasons.append(f"Confidence {signal.confidence:.2f} < min {self._config.min_confidence}")
        if signal.quality < self._config.min_quality:
            reasons.append(f"Quality {signal.quality:.2f} < min {self._config.min_quality}")
        rr = self._calculate_rr(signal)
        if rr < self._config.min_risk_reward:
            reasons.append(f"Risk/Reward {rr:.2f} < min {self._config.min_risk_reward}")
        if not self._check_classification(signal):
            reasons.append(f"Classification {signal.classification} below required {self._config.required_classification}")
        if signal.pair not in self._config.pairs:
            reasons.append(f"Pair {signal.pair} not in configured pairs")

        if reasons:
            log.info("SignalValidator: rejected %s %s: %s", signal.pair, signal.direction, "; ".join(reasons))
            return SignalApproval.REJECTED, reasons

        log.info("SignalValidator: approved %s %s", signal.pair, signal.direction)
        return SignalApproval.APPROVED, ["All validations passed"]

    def _calculate_rr(self, signal: SignalData) -> float:
        if signal.direction.lower() == "long":
            potential = signal.take_profit_1 - signal.entry_price
            risk = signal.entry_price - signal.stop_loss
        else:
            potential = signal.entry_price - signal.take_profit_1
            risk = signal.stop_loss - signal.entry_price
        if risk <= 0:
            return 0.0
        return potential / risk

    def _check_classification(self, signal: SignalData) -> bool:
        rank = {"ouro_supremo": 5, "ouro": 4, "prata": 3, "bronze": 2, "reprovado": 1}
        required_rank = rank.get(self._config.required_classification.lower().replace(" ", "_"), 0)
        signal_rank = rank.get(signal.classification.lower().replace(" ", "_"), 0)
        return signal_rank >= required_rank
