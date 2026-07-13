"""
Probability Engine — Calcula probabilidade historica de vitoria.

Utiliza:
- Paper Trading
- Backtest
- Setup
- Timeframe
- Regime
- Liquidez
- Timing
- Flow
- Momentum
- Volatilidade
"""
import json
from ENGINE.common.paths import (
    TRADE_HISTORY_PATH, EVIDENCE_DIR, PAPER_TRADING_PATH,
    WEIGHTS_V7_PATH, LEARNING_DATA_PATH, METRICS_PATH
)
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from ENGINE.scanner.scanner_types import SignalClassification, SignalDirection
from ENGINE.decision.signal_decision import SignalDecision

log = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    signal_id: str
    symbol: str
    timeframe: str
    direction: str
    entry_price: float
    exit_price: float
    pnl: float
    r_multiple: float
    result: str  # win / loss / breakeven
    setup: str
    regime: str
    classification: str
    quality: float
    conviction: float
    flow: float
    timing: float
    entry_score: float
    liquidity: float
    risk_reward: float
    adx: float
    rvol: float
    timestamp: str


@dataclass
class ProbabilityResult:
    win_rate: float = 0.40
    total_samples: int = 0
    confidence: float = 0.0
    by_setup: Dict[str, float] = field(default_factory=dict)
    by_timeframe: Dict[str, float] = field(default_factory=dict)
    by_regime: Dict[str, float] = field(default_factory=dict)
    by_classification: Dict[str, float] = field(default_factory=dict)
    by_rr_range: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "win_rate": self.win_rate,
            "total_samples": self.total_samples,
            "confidence": self.confidence,
            "by_setup": self.by_setup,
            "by_timeframe": self.by_timeframe,
            "by_regime": self.by_regime,
            "by_classification": self.by_classification,
            "by_rr_range": self.by_rr_range,
        }


class ProbabilityEngine:
    """Calcula probabilidade historica de vitoria para um sinal."""

    def __init__(self, history_path: str = None):
        self._history_path = history_path or os.environ.get(
            "QUANTOS_HISTORY_PATH",
            str(TRADE_HISTORY_PATH),
        )
        self._trades: List[TradeRecord] = []
        self._load_history()

    def _load_history(self):
        if os.path.exists(self._history_path):
            try:
                with open(self._history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._trades = [TradeRecord(**t) for t in data.get("trades", [])]
                log.info("ProbabilityEngine: loaded %d trades from history", len(self._trades))
            except Exception as e:
                log.warning("ProbabilityEngine: failed to load history: %s", e)

    def _save_history(self):
        try:
            os.makedirs(os.path.dirname(self._history_path), exist_ok=True)
            with open(self._history_path, "w", encoding="utf-8") as f:
                json.dump({"trades": [t.__dict__ for t in self._trades]}, f, indent=2)
        except Exception as e:
            log.warning("ProbabilityEngine: failed to save history: %s", e)

    def record_trade(self, trade: TradeRecord):
        self._trades.append(trade)
        self._save_history()

    def estimate_probability(
        self,
        sd: SignalDecision,
        setup: str = "",
        regime: str = "",
    ) -> ProbabilityResult:
        result = ProbabilityResult()
        if not self._trades:
            result.win_rate = 0.40
            result.total_samples = 0
            result.confidence = 0.0
            return result

        total = len(self._trades)
        wins = sum(1 for t in self._trades if t.result == "win")
        losses = sum(1 for t in self._trades if t.result == "loss")
        if total > 0:
            result.win_rate = wins / total
            result.total_samples = total
            result.confidence = min(1.0, total / 100.0)

        by_setup: Dict[str, List[bool]] = {}
        by_tf: Dict[str, List[bool]] = {}
        by_regime: Dict[str, List[bool]] = {}
        by_cls: Dict[str, List[bool]] = {}
        by_rr: Dict[str, List[bool]] = {}

        for t in self._trades:
            is_win = t.result == "win"
            by_setup.setdefault(t.setup, []).append(is_win)
            by_tf.setdefault(t.timeframe, []).append(is_win)
            by_regime.setdefault(t.regime, []).append(is_win)
            by_cls.setdefault(t.classification, []).append(is_win)

            rr_key = "baixo" if t.risk_reward < 2.0 else "medio" if t.risk_reward < 3.0 else "alto"
            by_rr.setdefault(rr_key, []).append(is_win)

        result.by_setup = {k: sum(v) / len(v) for k, v in by_setup.items()}
        result.by_timeframe = {k: sum(v) / len(v) for k, v in by_tf.items()}
        result.by_regime = {k: sum(v) / len(v) for k, v in by_regime.items()}
        result.by_classification = {k: sum(v) / len(v) for k, v in by_cls.items()}
        result.by_rr_range = {k: sum(v) / len(v) for k, v in by_rr.items()}

        return result

    def adjusted_win_probability(
        self,
        sd: SignalDecision,
        setup: str = "",
        regime: str = "",
    ) -> float:
        """Calcula probabilidade ajustada combinando historico e scores atuais."""
        prob = self.estimate_probability(sd, setup, regime)

        if prob.total_samples == 0:
            base = 0.40
        else:
            base = prob.win_rate

        q = sd.quality
        conv = getattr(sd, 'quality_score', q)
        rr = sd.risk_reward

        boost = 0.0
        if q >= 0.80:
            boost += 0.08
        elif q >= 0.70:
            boost += 0.04

        if conv >= 0.80:
            boost += 0.06
        elif conv >= 0.65:
            boost += 0.03

        if rr >= 3.0:
            boost += 0.06
        elif rr >= 2.0:
            boost += 0.03

        if sd.entry_zone_ok:
            boost += 0.03

        adjusted = min(base + boost, 0.95)
        return round(adjusted, 4)
