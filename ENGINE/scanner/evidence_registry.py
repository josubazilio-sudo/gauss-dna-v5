import json
from ENGINE.common.paths import (
    TRADE_HISTORY_PATH, EVIDENCE_DIR, PAPER_TRADING_PATH,
    WEIGHTS_V7_PATH, LEARNING_DATA_PATH, METRICS_PATH
)
import logging
import os
from datetime import datetime
from typing import Dict, Any

log = logging.getLogger(__name__)

log.warning("V6 scanner/evidence_registry.py importado — DEPRECATED. Usar ENGINE/risk/ e ENGINE/decision/ (V7)")

class EvidenceRegistry:
    def __init__(self, directory: str = str(EVIDENCE_DIR)):
        self.directory = directory
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
            
    def register_decision(self, decision: Any, candidate: Any):
        """Registra a decisão do motor V6 e todos os dados de contexto."""
        trace_id = decision.trace_id
        file_path = os.path.join(self.directory, f"{trace_id}.json")
        
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "decision": decision.__dict__ if hasattr(decision, '__dict__') else decision,
            "candidate": candidate.__dict__ if hasattr(candidate, '__dict__') else candidate,
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=4, default=str)
        
        log.info(f"Evidence registered: {trace_id}")
