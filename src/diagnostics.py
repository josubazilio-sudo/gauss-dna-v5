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

    def summary(self, top_n=5):
        if not self.entries:
            return None
        aprovados = [e for e in self.entries if e["decision"] in ("OURO", "PRATA", "BRONZE")]
        bloqueados = [e for e in self.entries if e["decision"] == "bloqueado"]
        recusados = [e for e in self.entries if e["decision"] == "recusado"]
        ordenados = sorted(
            [e for e in self.entries if e.get("score")],
            key=lambda x: x["score"] or 0, reverse=True,
        )
        top = ordenados[:top_n]
        top_linhas = "\n".join(
            f"  {i+1}. {e['symbol']} - {e['decision']} ({e['score']}/100)"
            for i, e in enumerate(top)
        ) if top else "  Nenhum sinal gerado"
        return (
            f"GAUSS DNA V5 - Diagnóstico do ciclo\n"
            f"Total analisados: {len(self.entries)}\n"
            f"✅ Aprovados: {len(aprovados)}\n"
            f"🔒 Bloqueados: {len(bloqueados)}\n"
            f"❌ Recusados: {len(recusados)}\n\n"
            f"Top {top_n}:\n{top_linhas}"
        )
