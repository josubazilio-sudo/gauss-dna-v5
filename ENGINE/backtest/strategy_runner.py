import logging
from typing import List, Dict, Optional, Callable

from .backtest_types import Trade, TradeDirection, BacktestConfig

log = logging.getLogger(__name__)


class StrategyRunner:
    def __init__(self, config: BacktestConfig):
        self._config = config

    def run(self, signal: Dict, candle_data: List[Dict]) -> List[Trade]:
        trades: List[Trade] = []
        return trades


def select_setup(signal_dict: Dict) -> Optional[str]:
    patterns = signal_dict.get("patterns", [])
    if patterns:
        return ";".join(p.type.value for p in patterns[:3])
    return signal_dict.get("setup", "unknown")
