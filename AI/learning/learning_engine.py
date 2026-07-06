import logging
from AI.analysis.strategy_analyzer import StrategyAnalyzer
from CORE.memory.memory_engine import MemoryEngine

log = logging.getLogger(__name__)

class LearningEngine:
    def __init__(self, memory: MemoryEngine):
        self._memory = memory
        self._analyzer = StrategyAnalyzer(memory)

    def learn(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        log.info(f"LearningEngine: Analisando performance de {strategy_name}")
        metrics = self._analyzer.analyze_strategy(strategy_name)
        
        if metrics and metrics.profit_factor < 2.5:
            log.info("LearningEngine: Detectado PF < 2.5. Propondo otimização de risco...")
            return {
                "action": "optimize_risk",
                "current_pf": metrics.profit_factor,
                "suggested_rr": 2.5
            }
        return None
