import logging
from typing import Dict, List, Optional
from ..ai_types import StrategyMetric
from CORE.memory.memory_engine import MemoryEngine

log = logging.getLogger(__name__)

class StrategyAnalyzer:
    def __init__(self, memory: MemoryEngine):
        self._memory = memory

    def analyze_strategy(self, strategy_name: str) -> Optional[StrategyMetric]:
        # Busca resultados históricos no MEMORY
        records = self._memory.get_backtest_records(strategy_name)
        if not records:
            return None
        
        # Agrega métricas consolidadas
        total_profit = sum(r.net_profit for r in records)
        total_trades = sum(r.total_trades for r in records)
        if total_trades == 0: return None
        
        return StrategyMetric(
            win_rate=sum(r.winning_trades for r in records) / total_trades,
            profit_factor=sum(r.gross_profit for r in records) / max(sum(r.gross_loss for r in records), 1),
            max_drawdown=max(r.max_drawdown_pct for r in records),
            expectancy=sum(r.expectancy for r in records) / len(records),
            sharpe_ratio=sum(r.sharpe_ratio for r in records) / len(records),
            trades_count=total_trades
        )
