import logging
from typing import Dict, Any, Optional
from ..ai_types import EvolutionProposal
from ENGINE.backtest.backtest_engine import BacktestEngine
from ENGINE.backtest.backtest_types import BacktestConfig

log = logging.getLogger(__name__)

class EvolutionEngine:
    def __init__(self, backtest_engine: BacktestEngine):
        self._bt = backtest_engine

    def optimize(self, strategy_name: str, config: BacktestConfig) -> Optional[BacktestConfig]:
        log.info(f"EvolutionEngine: Otimizando estratégia {strategy_name}")
        # Simplificação: Otimiza o parâmetro de risco baseado na sugestão
        new_config = config
        new_config.atr_tp2_multiplier += 0.5
        
        # Validação via BacktestEngine
        result = self._bt.run_simulation(new_config)
        
        if result.profit_factor >= 2.5:
            log.info("EvolutionEngine: Otimização validada com sucesso.")
            return new_config
        else:
            log.warning("EvolutionEngine: Otimização não validada. Mantendo baseline.")
            return None
