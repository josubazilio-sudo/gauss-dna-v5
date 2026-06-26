"""Diagnóstico e Logging de Decisões."""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Diagnostics:
    def __init__(self):
        self.entries = []

    def record(self, symbol, decision, detail=None, score=None):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "decision": decision,
            "detail": str(detail) if detail else None,
            "score": score,
        }
        self.entries.append(entry)

        if decision in ("OURO", "PRATA", "BRONZE"):
            logger.info("[%s] %s | Score: %s% | Detalhe: %s", symbol, decision, score, detail)
        else:
            logger.debug("[%s] %s | Motivo: %s", symbol, decision, detail)

    def report(self):
        if not self.entries:
            return
        latest = self.entries[-20:]
        aprovados = [e for e in latest if e["decision"] in ("OURO", "PRATA", "BRONZE")]
        bloqueados = [e for e in latest if e["decision"] == "bloqueado"]
        recusados = [e for e in latest if e["decision"] == "recusado"]

        logger.info(
            "Diagnóstico (últimos %d): %d aprovados, %d bloqueados, %d recusados",
            len(latest), len(aprovados), len(bloqueados), len(recusados),
        )
