import logging
from typing import Dict
from ..ai_types import EvolutionProposal

log = logging.getLogger(__name__)

class DecisionValidator:
    def __init__(self, current_baseline: Dict[str, float]):
        self._baseline = current_baseline

    def is_safe(self, proposal: EvolutionProposal) -> bool:
        # Quality Gate: Drawdown não pode aumentar
        if proposal.metrics_delta.get("drawdown_increase", 0) > 0:
            log.error("DecisionValidator: REJEITADO! Aumento de Drawdown detectado.")
            return False
            
        # Quality Gate: Profit Factor não pode diminuir
        if proposal.metrics_delta.get("profit_factor_decrease", 0) > 0:
            log.error("DecisionValidator: REJEITADO! Queda no Profit Factor detectada.")
            return False
            
        return True
