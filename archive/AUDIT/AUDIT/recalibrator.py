import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ENGINE.decision_brain.decision_brain import DecisionBrain

log = logging.getLogger(__name__)

RECALIB_DIR = Path(__file__).parent.parent / "MEMORY" / "recalibration"


class Recalibrator:
    def __init__(self, brain: DecisionBrain, min_trades: int = 100):
        self._brain = brain
        self._min_trades = min_trades
        self._cycle = 0
        RECALIB_DIR.mkdir(parents=True, exist_ok=True)

    def analyze_and_adjust(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(trades) < self._min_trades:
            return []

        self._cycle += 1
        ajustes = []

        for dim, key_fn in [
            ("setup", lambda t: t.get("setup", "")),
            ("regime", lambda t: t.get("regime", "")),
            ("asset", lambda t: t.get("pair", "")),
            ("timeframe", lambda t: t.get("timeframe", "")),
        ]:
            ajustes.extend(self._check_dimension(trades, dim, key_fn))

        if ajustes:
            self._apply_adjustments(ajustes)

        self._save_cycle(trades, ajustes)
        return ajustes

    def _check_dimension(self, trades, dim: str, key_fn):
        groups = defaultdict(list)
        for t in trades:
            groups[key_fn(t)].append(t)
        suggestions = []

        for label, ts in groups.items():
            if len(ts) < 5:
                continue
            wins = sum(1 for t in ts if t.get("result") == "win")
            wr = wins / len(ts)
            overall_wins = sum(1 for t in trades if t.get("result") == "win")
            overall_wr = overall_wins / len(trades) if trades else 0
            degradation = overall_wr - wr

            if degradation > 0.15 and overall_wr > 0:
                suggestions.append({
                    "dimensao": dim,
                    "label": label,
                    "trades": len(ts),
                    "win_rate": round(wr, 4),
                    "overall_win_rate": round(overall_wr, 4),
                    "degradacao": round(degradation, 4),
                    "acao": f"Reduzir peso para {label} em {dim}",
                })
        return suggestions

    def _apply_adjustments(self, ajustes):
        if not ajustes:
            return
        degradation = max(a.get("degradacao", 0) for a in ajustes)
        reduction = min(degradation * 0.5, 0.20)
        padrao = self._brain.PESOS_PADRAO
        novos_pesos = {
            "tese_score": max(0.30, padrao["tese_score"] - reduction),
            "contra_tese_score": min(0.60, padrao["contra_tese_score"] + reduction),
        }
        self._brain.update_weights(novos_pesos, f"recalibracao_ciclo_{self._cycle}")

    def _save_cycle(self, trades, ajustes):
        record = {
            "cycle": self._cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_trades": len(trades),
            "ajustes": ajustes,
            "pesos_resultantes": self._brain.get_weights(),
        }
        path = RECALIB_DIR / f"recalibracao_ciclo_{self._cycle}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        log.info("Recalibration cycle %d saved: %s", self._cycle, path)
