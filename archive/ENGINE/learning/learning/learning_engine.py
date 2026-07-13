"""
Learning Engine — Sistema de aprendizado continuo.

Apos cada operacao registra:
- Setup, resultado, R obtido, drawdown, tempo, regime, timeframe
- Classificacao, score, conviccao, flow, timing, entry score

Apos centenas de operacoes, recalibra automaticamente os pesos
dos componentes que mais contribuem para o lucro.
"""
import json
from ENGINE.common.paths import (
    TRADE_HISTORY_PATH, EVIDENCE_DIR, PAPER_TRADING_PATH,
    WEIGHTS_V7_PATH, LEARNING_DATA_PATH, METRICS_PATH
)
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from copy import deepcopy

log = logging.getLogger(__name__)


@dataclass
class TradeOutcome:
    signal_id: str
    symbol: str
    timeframe: str
    direction: str
    entry_price: float
    exit_price: float
    pnl: float
    r_multiple: float
    result: str
    drawdown: float
    duration_hours: float
    regime: str
    classification: str
    quality_score: float
    conviction_score: float
    flow_score: float
    timing_index: float
    entry_score: float
    institutional_score: float
    structural_score: float
    liquidity_score: float
    risk_score: float
    confidence_score: float
    consensus_score: float
    risk_reward: float
    setup: str
    timestamp: str


@dataclass
class ComponentPerformance:
    name: str
    weight: float
    win_rate: float = 0.0
    avg_profit: float = 0.0
    correlation: float = 0.0
    sample_count: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "weight": self.weight,
            "win_rate": self.win_rate,
            "avg_profit": self.avg_profit,
            "correlation": self.correlation,
            "sample_count": self.sample_count,
        }


class LearningEngine:
    """Aprendizado continuo baseado em resultados de trades."""

    def __init__(self, history_path: str = None):
        self._history_path = history_path or os.environ.get(
            "QUANTOS_LEARNING_PATH",
            str(LEARNING_DATA_PATH),
        )
        self._outcomes: List[TradeOutcome] = []
        self._component_performance: Dict[str, ComponentPerformance] = {}
        self._min_trades_for_update = 50
        self._weight_adjustment_rate = 0.05
        self._load()

    def _load(self):
        if os.path.exists(self._history_path):
            try:
                with open(self._history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._outcomes = [TradeOutcome(**t) for t in data.get("outcomes", [])]
                cp_data = data.get("component_performance", {})
                self._component_performance = {
                    k: ComponentPerformance(**v) for k, v in cp_data.items()
                }
                log.info("LearningEngine: loaded %d outcomes, %d components",
                         len(self._outcomes), len(self._component_performance))
            except Exception as e:
                log.warning("LearningEngine: failed to load: %s", e)

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._history_path), exist_ok=True)
            data = {
                "outcomes": [o.__dict__ for o in self._outcomes],
                "component_performance": {
                    k: v.to_dict() for k, v in self._component_performance.items()
                },
            }
            with open(self._history_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.warning("LearningEngine: failed to save: %s", e)

    def record_outcome(self, outcome: TradeOutcome):
        self._outcomes.append(outcome)
        self._save()

        if len(self._outcomes) >= self._min_trades_for_update:
            self._recalibrate()

    def _recalibrate(self):
        """Recalibra pesos dos componentes com base em correlacao com lucro."""
        log.info("LearningEngine: recalibrating with %d outcomes", len(self._outcomes))

        components = {
            "institutional_score": [],
            "structural_score": [],
            "market_score": [],
            "momentum_score": [],
            "liquidity_score": [],
            "risk_score": [],
            "confidence_score": [],
            "quality_score": [],
            "conviction_score": [],
            "flow_score": [],
            "timing_index": [],
            "entry_score": [],
            "consensus_score": [],
        }

        profitable = []
        for o in self._outcomes:
            profitable.append(1 if o.pnl > 0 else 0)
            for key in components:
                val = getattr(o, key, 0.0)
                components[key].append(val)

        n = len(profitable)
        if n < self._min_trades_for_update:
            return

        for key, values in components.items():
            if len(values) != n:
                continue

            corr = self._correlation(values, profitable)
            wr = sum(1 for i, v in enumerate(values) if profitable[i] == 1 and v > sum(values)/len(values))
            wr_total = sum(1 for i in range(n) if profitable[i] == 1)
            win_rate_above_avg = wr / max(wr_total, 1)

            avg_profit = sum(
                self._outcomes[i].pnl for i in range(n)
                if values[i] > sum(values) / len(values)
            ) / max(n, 1)

            current_weight = self._component_performance.get(key, ComponentPerformance(
                name=key, weight=self._default_weight(key),
            ))

            if abs(corr) < 0.05:
                new_weight = max(0.01, current_weight.weight - self._weight_adjustment_rate)
            elif corr > 0:
                new_weight = min(0.30, current_weight.weight + self._weight_adjustment_rate * abs(corr))
            else:
                new_weight = max(0.01, current_weight.weight - self._weight_adjustment_rate * abs(corr))

            self._component_performance[key] = ComponentPerformance(
                name=key,
                weight=round(new_weight, 4),
                win_rate=round(win_rate_above_avg, 4),
                avg_profit=round(avg_profit, 4),
                correlation=round(corr, 4),
                sample_count=n,
            )

        total_weight = sum(cp.weight for cp in self._component_performance.values())
        if total_weight > 0:
            for cp in self._component_performance.values():
                cp.weight = round(cp.weight / total_weight, 4)

        self._save()
        log.info("LearningEngine: recalibration complete. %d components updated.",
                 len(self._component_performance))

    def _default_weight(self, key: str) -> float:
        defaults = {
            "institutional_score": 0.15, "structural_score": 0.10,
            "market_score": 0.08, "momentum_score": 0.08,
            "liquidity_score": 0.08, "risk_score": 0.05,
            "confidence_score": 0.08, "quality_score": 0.15,
            "conviction_score": 0.08, "flow_score": 0.12,
            "timing_index": 0.10, "entry_score": 0.08,
            "consensus_score": 0.08,
        }
        return defaults.get(key, 0.05)

    def _correlation(self, xs: List[float], ys: List[int]) -> float:
        n = len(xs)
        if n < 3:
            return 0.0
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        cov = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
        var_x = sum((x - mean_x) ** 2 for x in xs)
        var_y = sum((y - mean_y) ** 2 for y in ys)
        if var_x == 0 or var_y == 0:
            return 0.0
        return cov / ((var_x * var_y) ** 0.5)

    def get_adjusted_weights(self) -> Dict[str, float]:
        if not self._component_performance:
            return {}
        return {k: v.weight for k, v in self._component_performance.items()}

    def get_performance_summary(self) -> Dict[str, Any]:
        return {
            name: cp.to_dict()
            for name, cp in self._component_performance.items()
        }
