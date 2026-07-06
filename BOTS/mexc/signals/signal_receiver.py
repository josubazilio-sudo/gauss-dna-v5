import logging
from typing import Callable, Dict, List, Optional

from ..bot_config import BotConfig
from ..bot_types import OrderSide, SignalApproval
from ..exchange.connector import ExchangeConnector

log = logging.getLogger(__name__)


class SignalData:
    def __init__(self, pair: str, direction: str, entry_price: float, stop_loss: float,
                 take_profit_1: float, take_profit_2: float, timeframe: str, setup: str,
                 regime: str, confidence: float, quality: float, score: float,
                 classification: str, patterns: List[str], signal_id: str = ""):
        self.pair = pair
        self.direction = direction
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit_1 = take_profit_1
        self.take_profit_2 = take_profit_2
        self.timeframe = timeframe
        self.setup = setup
        self.regime = regime
        self.confidence = confidence
        self.quality = quality
        self.score = score
        self.classification = classification
        self.patterns = patterns
        self.signal_id = signal_id

    @property
    def order_side(self) -> OrderSide:
        return OrderSide.BUY if self.direction.lower() == "long" else OrderSide.SELL


class SignalReceiver:
    def __init__(self, config: BotConfig):
        self._config = config
        self._callbacks: List[Callable] = []
        self._pending_signals: List[SignalData] = []

    @property
    def pending_count(self) -> int:
        return len(self._pending_signals)

    def register_callback(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def receive_signal(self, data: dict) -> Optional[SignalData]:
        try:
            signal = SignalData(
                pair=data.get("ticker", ""),
                direction=data.get("direction", ""),
                entry_price=float(data.get("entry_price", 0)),
                stop_loss=float(data.get("stop_loss", 0)),
                take_profit_1=float(data.get("take_profit_1", 0)),
                take_profit_2=float(data.get("take_profit_2", 0)),
                timeframe=data.get("timeframe", ""),
                setup=data.get("setup", ""),
                regime=data.get("regime", ""),
                confidence=float(data.get("confidence", 0)),
                quality=float(data.get("quality", 0)),
                score=float(data.get("score", 0)),
                classification=data.get("classification", ""),
                patterns=data.get("patterns", []),
                signal_id=data.get("signal_id", ""),
            )
            self._pending_signals.append(signal)
            for cb in self._callbacks:
                try:
                    cb(signal)
                except Exception:
                    log.exception("SignalReceiver: callback failed")
            log.info("SignalReceiver: received signal %s %s %s", signal.pair, signal.direction, signal.timeframe)
            return signal
        except Exception as e:
            log.error("SignalReceiver: invalid signal data: %s", e)
            return None

    def pop_pending(self) -> List[SignalData]:
        signals = list(self._pending_signals)
        self._pending_signals.clear()
        return signals

    def clear(self) -> None:
        self._pending_signals.clear()
