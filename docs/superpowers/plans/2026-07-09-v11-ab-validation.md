# V11 A/B Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a professional A/B validation proving that V11 Decision Brain takes superior decisions to V7, with automatic metrics, audit, and recalibration.

**Architecture:** A new `AUDIT/ab_validation.py` orchestrator that forks scanner signals into V7 and V11 pipelines, simulates trades independently for each, computes metrics via existing `statistics_engine`, compares via `comparator`, and generates a comparison report. Auto-recalibration module adjusts DecisionBrain weights every 100 trades based on empirical performance.

**Tech Stack:** Python 3.10+, existing scanner/decision engines, file-based JSON storage, no external databases.

**Architecture frozen:** No changes to scanner, indicators, strategy, or decision logic. Only new validation modules + minimal additions to `decision_brain.py` (weights API) and `institutional_audit.py` (thesis fields).

---

### Task 1: Modify `institutional_audit.py` — Add Decision Brain audit fields

**Files:**
- Modify: `AUDIT/institutional_audit.py` (headers + record_decision_brain method)

- [ ] **Step 1: Extend HEADERS with thesis/counter-thesis fields**

Add to the HEADERS list:
```python
"thesis_summary", "counter_thesis_summary", "decision_state",
"probabilidade", "conviccao", "risco", "justificativa_final",
"tese_score", "contra_score", "engine_version",
```

- [ ] **Step 2: Add `record_decision_brain()` method**

```python
def record_decision_brain(
    self,
    pair: str,
    timeframe: str,
    direction: str,
    entry_price: float,
    brain_record: "DecisionBrainRecord",
) -> None:
    import json
    tese = brain_record.tese
    ct = brain_record.contra_tese

    thesis_lines = []
    thesis_lines.append(f"score={tese.score_total:.2f}")
    thesis_lines.append(f"regime={tese.regime}")
    thesis_lines.append(f"contexto={tese.contexto_macro}")
    thesis_lines.append(f"tendencia={tese.tendencia.valor:.2f}")
    thesis_lines.append(f"fluxo={tese.fluxo_institucional.valor:.2f}")
    thesis_lines.append(f"estrutura={tese.estrutura.valor:.2f}")

    ct_lines = []
    ct_lines.append(f"score_contra={ct.score_contra:.2f}")
    for f in ct.fatores:
        if f.ativo:
            ct_lines.append(f"{f.nome}(peso={f.peso:.2f}): {f.justificativa}")

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pair": pair,
        "timeframe": timeframe,
        "direction": direction,
        "entry_price": entry_price,
        "thesis_summary": " | ".join(thesis_lines),
        "counter_thesis_summary": " | ".join(ct_lines),
        "decision_state": brain_record.estado.value,
        "probabilidade": brain_record.judgment.probabilidade if brain_record.judgment else 0.0,
        "conviccao": brain_record.judgment.conviccao if brain_record.judgment else 0.0,
        "risco": brain_record.judgment.risco if brain_record.judgment else 0.0,
        "justificativa_final": brain_record.justificativa_final,
        "tese_score": tese.score_total,
        "contra_score": ct.score_contra,
        "engine_version": brain_record.engine_version,
    }
    self._records.append(record)
```

- [ ] **Step 3: Run existing tests to confirm no breakage**

Run: `python -m pytest TESTS/test_backtest.py -x -q 2>&1 | tail -5`
Expected: no failures related to audit module

---

### Task 2: Create `AUDIT/baseline.py` — Baseline snapshot and comparison

**Files:**
- Create: `AUDIT/baseline.py`

- [ ] **Step 1: Create the file with save/load/compare functions**

```python
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

BASELINE_DIR = Path(__file__).parent.parent / "MEMORY" / "baseline"


def save_baseline(result, version: str = "V7", path: Optional[Path] = None) -> Path:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    dest = path or (BASELINE_DIR / f"baseline_{version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    data = {
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "metrics": {
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "win_rate": round(result.win_rate, 4),
            "profit_factor": round(result.profit_factor, 4),
            "expectancy": round(result.expectancy, 6),
            "max_drawdown": round(result.max_drawdown, 4),
            "sharpe_ratio": round(result.sharpe_ratio, 4),
            "sortino_ratio": round(result.sortino_ratio, 4),
            "calmar_ratio": round(result.calmar_ratio, 4),
            "avg_rr": round(result.avg_rr, 4),
            "net_pnl": round(result.net_pnl, 4),
            "gross_profit": round(result.gross_profit, 4),
            "gross_loss": round(result.gross_loss, 4),
            "avg_trade_duration_h": round(result.avg_trade_duration_h, 4),
        },
        "by_setup": {k: {"trades": v["trades"], "wins": v["wins"], "win_rate": round(v["win_rate"], 4)} for k, v in result.by_setup.items()},
        "by_regime": {k: {"trades": v["trades"], "wins": v["wins"], "win_rate": round(v["win_rate"], 4)} for k, v in result.by_regime.items()},
        "by_timeframe": {k: {"trades": v["trades"], "wins": v["wins"], "win_rate": round(v["win_rate"], 4)} for k, v in result.by_timeframe.items()},
        "by_asset": {k: {"trades": v["trades"], "wins": v["wins"], "win_rate": round(v["win_rate"], 4), "profit_factor": round(v.get("profit_factor", 0), 4)} for k, v in result.by_asset.items()},
    }

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    log.info("Baseline saved: %s", dest)
    return dest


def load_baseline(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        log.warning("Baseline not found: %s", path)
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_against_baseline(result, baseline: Dict[str, Any]) -> Dict[str, Any]:
    base = baseline.get("metrics", {})
    current = {
        "total_trades": result.total_trades,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "expectancy": result.expectancy,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "avg_rr": result.avg_rr,
        "net_pnl": result.net_pnl,
    }
    deltas = {}
    for key in current:
        b = base.get(key)
        c = current[key]
        if b is not None and b != 0:
            deltas[key] = {
                "baseline": b,
                "current": c,
                "diff": round(c - b, 4),
                "diff_pct": round((c - b) / abs(b) * 100, 2),
            }
        elif b is not None:
            deltas[key] = {"baseline": b, "current": c, "diff": round(c - b, 4), "diff_pct": None}
    return deltas


def list_baselines() -> list:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(BASELINE_DIR.glob("baseline_*.json"))
```

- [ ] **Step 2: Create `MEMORY/baseline/` directory and verify import works**

Run: `python -c "from AUDIT.baseline import save_baseline, load_baseline, compare_against_baseline; print('OK')"`
Expected: `OK`

---

### Task 3: Add `update_weights()` to DecisionBrain

**Files:**
- Modify: `ENGINE/decision_brain/decision_brain.py`

- [ ] **Step 1: Extract default weights to class constant**

Add at top of class (before `__init__`):
```python
PESOS_PADRAO = {
    "tese_score": 0.60,
    "contra_tese_score": 0.40,
    "conviccao_min": 0.50,
    "probabilidade_base": 0.50,
}
```

Change `__init__` to use the constant and make weights configurable:
```python
def __init__(self, pesos_iniciais: Optional[Dict[str, float]] = None):
    self._historico: List[DecisionBrainRecord] = []
    self._version = "11.0.0"
    self._pesos = dict(pesos_iniciais or self.PESOS_PADRAO)
    self._ajustes: List[Dict[str, Any]] = []
```

- [ ] **Step 2: Add `update_weights()` method**

```python
def update_weights(self, novos_pesos: Dict[str, float], motivo: str = "recalibracao_automatica") -> bool:
    peso_min = 0.30
    peso_max = 1.50
    ajustados = {}
    for chave, valor in novos_pesos.items():
        if chave not in self.PESOS_PADRAO:
            log.warning("DecisionBrain: peso desconhecido '%s' ignorado", chave)
            continue
        original = self._pesos.get(chave, self.PESOS_PADRAO[chave])
        delta_max = original * 0.20
        novo = max(original - delta_max, min(original + delta_max, valor))
        novo = max(peso_min, min(peso_max, novo))
        if abs(novo - original) > 0.001:
            ajustados[chave] = {"de": round(original, 4), "para": round(novo, 4)}
            self._pesos[chave] = novo

    if ajustados:
        registro = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "motivo": motivo,
            "ajustes": ajustados,
            "pesos_resultantes": dict(self._pesos),
        }
        self._ajustes.append(registro)
        log.info("DecisionBrain: pesos ajustados: %s", ajustados)
        return True
    return False
```

- [ ] **Step 3: Add `get_weights()` and `get_ajustes()` methods**

```python
def get_weights(self) -> Dict[str, float]:
    return dict(self._pesos)

def get_ajustes(self) -> List[Dict[str, Any]]:
    return list(self._ajustes)
```

- [ ] **Step 4: Forward weights to judgment module**

In `evaluate()` method, pass `self._pesos` to `make_judgment()`. But looking at `judgment.py`, the weights are in a module-level constant `PESOS_JULGAMENTO`. Instead of refactoring the judgment module, we'll keep the judgment weights separate from the recalibration for now. The recalibration will adjust `self._pesos` which controls the high-level decision tuning.

Actually, let's keep it simple: `update_weights` adjusts the DecisionBrain's internal tuning parameters, which will be used in `evaluate()` to influence the judgment call. Modify `evaluate()` to pass `self._pesos`:

In `evaluate()`, change:
```python
judgment = make_judgment(tese, contra_tese, signal)
```
to:
```python
judgment = make_judgment(tese, contra_tese, signal, pesos_override=self._pesos)
```

And modify `judgment.py` to accept an optional parameter:
```python
def make_judgment(tese, contra_tese, signal, pesos_override=None):
    pesos = {**PESOS_JULGAMENTO, **(pesos_override or {})}
    # use pesos[...] instead of PESOS_JULGAMENTO[...]
```

- [ ] **Step 5: Verify module loads correctly**

Run: `python -c "from ENGINE.decision_brain.decision_brain import DecisionBrain; b = DecisionBrain(); b.update_weights({'tese_score': 0.7}, 'test'); print('OK')"`
Expected: `OK`

---

### Task 4: Create `AUDIT/ab_validation.py` — Main A/B Runner

**Files:**
- Create: `AUDIT/ab_validation.py`

This is the core module. It orchestrates: data loading → scanner → fork V7/V11 → simulate → metrics → compare → audit.

- [ ] **Step 1: Create ABTradeRecord dataclass**

```python
@dataclass
class ABTradeRecord:
    pair: str
    timeframe: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    entry_time: datetime
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    result: str = ""
    profit_loss_pct: float = 0.0
    mae_pct: float = 0.0
    mfe_pct: float = 0.0
    score: float = 0.0
    quality: float = 0.0
    classification: str = ""
    regime: str = ""
    rr: float = 0.0
    duration_h: float = 0.0
    setup: str = ""
    engine_version: str = ""
    # V11-specific
    decision_state: str = ""
    probabilidade: float = 0.0
    conviccao: float = 0.0
    risco: float = 0.0
    tese_score: float = 0.0
    contra_score: float = 0.0
    justificativa: str = ""
    signal_id: str = ""
```

- [ ] **Step 2: Create `_simulate_trade()` helper**

Copy from `BacktestAudit._simulate_trade()` — same logic, operates on `ABTradeRecord`.

```python
def _simulate_trade(trade: ABTradeRecord, forward_window: List[Candle]) -> Tuple[str, float, float]:
    direction = trade.direction
    entry = trade.entry_price
    sl = trade.stop_loss
    tp1 = trade.take_profit_1
    tp2 = trade.take_profit_2
    mae = 0.0
    mfe = 0.0
    for candle in forward_window:
        high, low = candle.high, candle.low
        if direction == "long":
            mae = max(mae, (entry - low) / entry)
            mfe = max(mfe, (high - entry) / entry)
            if low <= sl: return "loss", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
            if high >= tp2: return "win", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
        else:
            mae = max(mae, (high - entry) / entry)
            mfe = max(mfe, (entry - low) / entry)
            if high >= sl: return "loss", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
            if low <= tp2: return "win", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
    return "loss", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
```

- [ ] **Step 3: Create `_compute_metrics()` helper**

Same logic as `BacktestAudit._compute_metrics()` — fills an `ABResult` dataclass with win_rate, profit_factor, expectancy, max_drawdown, sharpe, sortino, calmar, avg_rr, net_pnl, etc.

Define `ABResult`:
```python
@dataclass
class ABResult:
    engine_version: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    avg_rr: float = 0.0
    net_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    avg_trade_duration_h: float = 0.0
    trades: List[ABTradeRecord] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    by_setup: Dict = field(default_factory=dict)
    by_regime: Dict = field(default_factory=dict)
    by_timeframe: Dict = field(default_factory=dict)
    by_asset: Dict = field(default_factory=dict)
    by_classification: Dict = field(default_factory=dict)
```

- [ ] **Step 4: Create main `ABValidation` class**

```python
import logging
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from ENGINE.market.market_types import Candle
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.scanner.scanner_types import Signal, SignalClassification
from ENGINE.decision.decision_engine import DecisionEngine
from ENGINE.decision_brain.decision_brain import DecisionBrain
from ENGINE.decision_brain.decision_brain_types import DecisionState
from AUDIT.data_loader import BinanceDataLoader
from AUDIT.institutional_audit import InstitutionalAudit

# Reuse constants from backtest_audit
BACKTEST_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
BACKTEST_TIMEFRAMES = ["15m", "1h", "4h"]
BACKTEST_MONTHS = 24
BASE_PRICES = {
    "BTCUSDT": 65000.0, "ETHUSDT": 3500.0, "SOLUSDT": 145.0,
    "BNBUSDT": 580.0, "XRPUSDT": 0.55,
}
VOLATILITIES = {
    "BTCUSDT": 0.015, "ETHUSDT": 0.018, "SOLUSDT": 0.025,
    "BNBUSDT": 0.020, "XRPUSDT": 0.030,
}

log = logging.getLogger(__name__)
```

The `run()` method:
```python
class ABValidation:
    def __init__(self, use_real_data: bool = True):
        self._scanner = ScannerEngine()
        self._v7 = DecisionEngine()
        self._v11 = DecisionBrain()
        self._audit = InstitutionalAudit()
        self._use_real_data = use_real_data
        self._data_loader = BinanceDataLoader() if use_real_data else None

    def run(
        self,
        assets: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        months: int = BACKTEST_MONTHS,
    ) -> Tuple[ABResult, ABResult, Dict[str, Any], InstitutionalAudit]:
        """
        Returns: (result_v7, result_v11, comparison, audit)
        """
        targets = assets or BACKTEST_ASSETS
        tfs = timeframes or BACKTEST_TIMEFRAMES
        result_v7 = ABResult(engine_version="V7")
        result_v11 = ABResult(engine_version="V11")

        candle_cache = self._load_data(targets, tfs, months)
        equity_v7 = 10000.0
        equity_v11 = 10000.0
        peak_v7 = 10000.0
        peak_v11 = 10000.0
        trades_v7: List[ABTradeRecord] = []
        trades_v11: List[ABTradeRecord] = []
        equity_curve_v7 = [equity_v7]
        equity_curve_v11 = [equity_v11]

        for pair in targets:
            for tf in tfs:
                all_candles = candle_cache.get(pair, {}).get(tf, [])
                if len(all_candles) < 200:
                    continue
                step = max(1, len(all_candles) // 100)
                for scan_i in range(0, len(all_candles) - 200, step):
                    window_end = scan_i + 200
                    window = all_candles[scan_i:window_end]
                    if len(window) < 100:
                        continue
                    try:
                        ctx = _make_market_context(pair, window)
                        candles_dict = {tf: window}
                        report = self._scanner.scan(pair, candles_dict, ctx)
                    except Exception as e:
                        log.debug("Scan error %s %s: %s", pair, tf, e)
                        continue

                    for sig in report.signals:
                        fwd_start = window_end
                        fwd_end = min(fwd_start + 96, len(all_candles))
                        forward_window = all_candles[fwd_start:fwd_end]
                        if len(forward_window) < 5:
                            continue

                        # === V7 PATH ===
                        v7_trade = self._process_v7(sig, forward_window, pair, tf)
                        if v7_trade:
                            trades_v7.append(v7_trade)
                            pnl = v7_trade.profit_loss_pct
                            equity_v7 += equity_v7 * pnl * 0.02
                            if equity_v7 > peak_v7:
                                peak_v7 = equity_v7
                            equity_curve_v7.append(equity_v7)

                        # === V11 PATH ===
                        v11_trade = self._process_v11(sig, forward_window, pair, tf)
                        if v11_trade:
                            trades_v11.append(v11_trade)
                            pnl = v11_trade.profit_loss_pct
                            equity_v11 += equity_v11 * pnl * 0.02
                            if equity_v11 > peak_v11:
                                peak_v11 = equity_v11
                            equity_curve_v11.append(equity_v11)

        self._fill_result(result_v7, trades_v7, equity_curve_v7)
        self._fill_result(result_v11, trades_v11, equity_curve_v11)
        comparison = self._compare(result_v7, result_v11)

        return result_v7, result_v11, comparison, self._audit
```

- [ ] **Step 5: Implement `_process_v7()`**

```python
def _process_v7(
    self, sig: Signal, forward_window: List[Candle], pair: str, tf: str
) -> Optional[ABTradeRecord]:
    try:
        main_candles = forward_window
        highs = [c.high for c in main_candles]
        lows = [c.low for c in main_candles]
        closes = [c.close for c in main_candles]
        entry_details = sig.entry_details if hasattr(sig, 'entry_details') else None

        sd = self._v7.evaluate_signal(
            sig,
            entry_details=entry_details,
            highs=highs, lows=lows, closes=closes,
        )
        if not sd.approved:
            return None
        trade = ABTradeRecord(
            pair=pair, timeframe=tf,
            direction=sd.direction,
            entry_price=sd.entry_price,
            stop_loss=sd.stop_loss,
            take_profit_1=sd.take_profit_1,
            take_profit_2=sd.take_profit_2,
            entry_time=sig.timestamp,
            score=sd.entry_score,
            quality=sd.quality,
            classification=sig.classification.value if sig.classification else "",
            regime=sig.regime,
            rr=sd.risk_reward,
            setup=sig.setup,
            engine_version="V7",
            signal_id=sd.signal_id or sd.trace_id,
        )
        sim_result, mae, mfe = _simulate_trade(trade, forward_window)
        trade.result = sim_result
        trade.profit_loss_pct = _calc_pnl(trade)
        trade.mae_pct = mae
        trade.mfe_pct = mfe
        trade.duration_h = 96 * _tf_hours(tf)
        return trade
    except Exception as e:
        log.debug("V7 error %s %s: %s", pair, tf, e)
        return None
```

- [ ] **Step 6: Implement `_process_v11()`**

```python
def _process_v11(
    self, sig: Signal, forward_window: List[Candle], pair: str, tf: str
) -> Optional[ABTradeRecord]:
    try:
        main_candles = forward_window
        ind = _make_market_context(pair, forward_window).indicators
        closes = [c.close for c in main_candles]

        brain_rec = self._v11.evaluate(
            signal=sig,
            candles=main_candles,
            rsi=ind.rsi,
            adx=ind.adx,
            atr_percent=ind.atr_percent,
            rvol=ind.rvol,
            vwap_distance=abs(sig.structure.vwap_distance) if sig.structure else 0.0,
        )

        if brain_rec.estado != DecisionState.EXECUTAR:
            # Record rejected reasons in audit too
            self._audit.record_decision_brain(pair, tf, sig.direction.value, sig.entry_price, brain_rec)
            return None

        trade = ABTradeRecord(
            pair=pair, timeframe=tf,
            direction=sig.direction.value,
            entry_price=sig.entry_price,
            stop_loss=sig.stop_loss,
            take_profit_1=sig.take_profit_1,
            take_profit_2=sig.take_profit_2,
            entry_time=sig.timestamp,
            score=sig.scores.quality_score if sig.scores else 0.0,
            quality=sig.quality,
            classification=sig.classification.value if sig.classification else "",
            regime=sig.regime,
            rr=sig.risk_reward,
            setup=sig.setup,
            engine_version="V11",
            decision_state=brain_rec.estado.value,
            probabilidade=brain_rec.judgment.probabilidade if brain_rec.judgment else 0,
            conviccao=brain_rec.judgment.conviccao if brain_rec.judgment else 0,
            risco=brain_rec.judgment.risco if brain_rec.judgment else 0,
            tese_score=brain_rec.tese.score_total,
            contra_score=brain_rec.contra_tese.score_contra,
            justificativa=brain_rec.justificativa_final,
            signal_id=sig.signal_id or "",
        )
        sim_result, mae, mfe = _simulate_trade(trade, forward_window)
        trade.result = sim_result
        trade.profit_loss_pct = _calc_pnl(trade)
        trade.mae_pct = mae
        trade.mfe_pct = mfe
        trade.duration_h = 96 * _tf_hours(tf)

        # Audit: record full thesis/counter-thesis for this trade
        self._audit.record_decision_brain(pair, tf, sig.direction.value, sig.entry_price, brain_rec)

        return trade
    except Exception as e:
        log.debug("V11 error %s %s: %s", pair, tf, e)
        return None
```

- [ ] **Step 7: Implement `_fill_result()` with metrics computation**

Reuse the same logic from `BacktestAudit._compute_metrics()` and decomposition methods:

```python
def _fill_result(self, result: ABResult, trades: List[ABTradeRecord], equity_curve: List[float]):
    if not trades:
        return
    result.total_trades = len(trades)
    result.trades = trades
    result.equity_curve = equity_curve

    winners = [t for t in trades if t.result == "win"]
    losers = [t for t in trades if t.result == "loss"]
    result.winning_trades = len(winners)
    result.losing_trades = len(losers)
    result.win_rate = len(winners) / len(trades) if trades else 0

    gross_profit = sum(abs(t.profit_loss_pct) * 10000 * 0.02 for t in winners)
    gross_loss = sum(abs(t.profit_loss_pct) * 10000 * 0.02 for t in losers)
    result.gross_profit = gross_profit
    result.gross_loss = gross_loss
    result.net_pnl = gross_profit - gross_loss
    result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0
    result.avg_rr = sum(t.rr for t in trades) / len(trades)
    result.avg_trade_duration_h = sum(t.duration_h for t in trades) / len(trades)

    avg_win = gross_profit / len(winners) if winners else 0
    avg_loss = gross_loss / len(losers) if losers else 0
    result.expectancy = (result.win_rate * avg_win - (1 - result.win_rate) * avg_loss) / 10000 if avg_loss > 0 else 0

    returns = []
    for i in range(1, len(equity_curve)):
        if equity_curve[i-1] > 0:
            returns.append((equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1])
    if len(returns) > 1:
        avg_ret = sum(returns) / len(returns)
        std_ret = (sum((r - avg_ret)**2 for r in returns) / len(returns)) ** 0.5
        result.sharpe_ratio = avg_ret / std_ret * (252 ** 0.5) if std_ret > 0 else 0
        neg = [r for r in returns if r < 0]
        if neg:
            neg_std = (sum(r**2 for r in neg) / len(neg)) ** 0.5
            result.sortino_ratio = avg_ret / neg_std * (252 ** 0.5) if neg_std > 0 else 0

    peak = max(equity_curve) if equity_curve else 10000
    trough = peak
    max_dd = 0.0
    for e in equity_curve:
        if e > peak: peak = e; trough = peak
        if e < trough: trough = e; dd = (peak - trough) / peak; max_dd = max(max_dd, dd)
    result.max_drawdown = max_dd
    if result.max_drawdown > 0 and result.sharpe_ratio != 0:
        result.calmar_ratio = result.sharpe_ratio / result.max_drawdown if result.max_drawdown > 0 else 0

    # Decompositions
    self._compute_by_dimension(result, trades, "setup", lambda t: t.setup)
    self._compute_by_dimension(result, trades, "regime", lambda t: t.regime)
    self._compute_by_dimension(result, trades, "timeframe", lambda t: t.timeframe)
    self._compute_by_dimension(result, trades, "asset", lambda t: t.pair)
    self._compute_by_dimension(result, trades, "classification", lambda t: t.classification)

def _compute_by_dimension(self, result: ABResult, trades, dim: str, key_fn):
    groups = defaultdict(list)
    for t in trades:
        groups[key_fn(t)].append(t)
    target = getattr(result, f"by_{dim}")
    for k, ts in groups.items():
        wins = sum(1 for t in ts if t.result == "win")
        total = len(ts)
        target[k] = {
            "trades": total, "wins": wins,
            "win_rate": wins / total if total > 0 else 0,
        }
```

- [ ] **Step 8: Implement `_compare()`**

```python
def _compare(self, a: ABResult, b: ABResult) -> Dict[str, Any]:
    def safe(a_val, b_val):
        return round(a_val - b_val, 4)

    def pct(a_val, b_val):
        if b_val and b_val != 0:
            return round((a_val - b_val) / abs(b_val) * 100, 2)
        return None

    comparison = {}
    metrics = ["win_rate", "profit_factor", "expectancy", "max_drawdown",
               "sharpe_ratio", "sortino_ratio", "avg_rr", "net_pnl",
               "total_trades", "winning_trades", "avg_trade_duration_h"]

    for m in metrics:
        av = getattr(a, m, 0)
        bv = getattr(b, m, 0)
        comparison[m] = {
            "V7": av, "V11": bv,
            "diff": safe(bv, av),
            "diff_pct": pct(bv if m != "max_drawdown" else bv, av if m != "max_drawdown" else av),
        }

    # Favor smaller drawdown — flip sign
    if "max_drawdown" in comparison:
        comparison["max_drawdown"]["V11_better"] = b.max_drawdown <= a.max_drawdown

    return comparison
```

- [ ] **Step 9: Include helper functions from backtest_audit**

Copy `_make_market_context`, `_compute_atr`, `_ema`, `_tf_hours`, `_tf_minutes`, `_generate_historical` from `backtest_audit.py` (same logic, reused).

Add `_load_data()` that wraps the Binance download or synthetic generation:
```python
def _load_data(self, targets, tfs, months):
    if self._use_real_data and self._data_loader:
        log.info("Downloading %d months of real data...", months)
        return self._data_loader.download_all(targets, tfs, months)
    candle_cache = {}
    for pair in targets:
        candle_cache[pair] = {}
        base = BASE_PRICES.get(pair, 100.0)
        vol = VOLATILITIES.get(pair, 0.02)
        for tf in tfs:
            candle_cache[pair][tf] = self._generate_historical(base, vol, months, tf)
    return candle_cache
```

- [ ] **Step 10: Verify import and basic structure**

Run: `python -c "from AUDIT.ab_validation import ABValidation, ABResult, ABTradeRecord; print('OK')"`
Expected: `OK`

---

### Task 5: Create `AUDIT/recalibrator.py` — Automatic recalibration every 100 trades

**Files:**
- Create: `AUDIT/recalibrator.py`

- [ ] **Step 1: Create `Recalibrator` class**

```python
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

    def analyze_and_adjust(self, trades_v11: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(trades_v11) < self._min_trades:
            return []

        self._cycle += 1
        ajustes = []

        ajustes.extend(self._check_dimension(trades_v11, "setup", lambda t: t.get("setup", "")))
        ajustes.extend(self._check_dimension(trades_v11, "regime", lambda t: t.get("regime", "")))
        ajustes.extend(self._check_dimension(trades_v11, "asset", lambda t: t.get("pair", "")))
        ajustes.extend(self._check_dimension(trades_v11, "timeframe", lambda t: t.get("timeframe", "")))

        if ajustes:
            self._apply_adjustments(ajustes)

        self._save_cycle(trades_v11, ajustes)
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
        novos_pesos = {
            "tese_score": max(0.30, self._brain.PESOS_PADRAO["tese_score"] - reduction),
            "contra_tese_score": min(0.60, self._brain.PESOS_PADRAO["contra_tese_score"] + reduction),
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
```

- [ ] **Step 2: Verify module loads**

Run: `python -c "from AUDIT.recalibrator import Recalibrator; print('OK')"`
Expected: `OK`

---

### Task 6: Create `AUDIT/run_ab.py` — CLI entry point for A/B validation

**Files:**
- Create: `AUDIT/run_ab.py`

This is the main entry point that runs everything end-to-end.

- [ ] **Step 1: Create CLI script**

```python
#!/usr/bin/env python3
"""
QuantOS V11.1 — Validacao A/B Institutional
V7 (producao) vs V11 (Decision Brain)

Uso:
    python AUDIT/run_ab.py [--synthetic] [--real] [--assets BTCUSDT,ETHUSDT] [--tfs 1h,4h]
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from AUDIT.ab_validation import ABValidation, ABResult
from AUDIT.baseline import save_baseline, compare_against_baseline, list_baselines
from AUDIT.recalibrator import Recalibrator
from ENGINE.decision_brain.decision_brain import DecisionBrain


def main():
    use_real = "--real" in sys.argv
    args = sys.argv[1:]

    print("=" * 68)
    print("  QUANTOS V11.1 — VALIDAÇÃO A/B INSTITUCIONAL")
    print("  V7 (producao) vs V11 (Decision Brain)")
    print(f"  Fonte: {'REAIS (Binance)' if use_real else 'SINTETICOS'}")
    print("=" * 68)

    # 1. Run A/B
    print("\n[1/5] Executando A/B Validation...")
    ab = ABValidation(use_real_data=use_real)
    result_v7, result_v11, comparison, audit = ab.run()

    print(f"  V7:  {result_v7.total_trades} trades | WR={result_v7.win_rate:.1%} | PF={result_v7.profit_factor:.2f}")
    print(f"  V11: {result_v11.total_trades} trades | WR={result_v11.win_rate:.1%} | PF={result_v11.profit_factor:.2f}")

    # 2. Save baseline (V7 always)
    print("\n[2/5] Salvando baseline V7...")
    baseline_path = save_baseline(result_v7, version="V7")

    # 3. Compare
    print("\n[3/5] Comparando V7 vs V11...")
    for metric, vals in sorted(comparison.items()):
        if isinstance(vals, dict) and "diff" in vals:
            arrow = "▲" if vals.get("V11_better", vals.get("diff", 0) > 0) else "▼"
            print(f"  {metric:<20s} V7={vals['V7']:<12} V11={vals['V11']:<12} {arrow} {vals.get('diff', 0):+.4f}")

    # 4. Recalibrate if enough trades
    print("\n[4/5] Verificando recalibracao...")
    brain = ab._v11
    recal = Recalibrator(brain, min_trades=100)
    trade_dicts = [t.__dict__ for t in result_v11.trades]
    ajustes = recal.analyze_and_adjust(trade_dicts)
    if ajustes:
        print(f"  Ajustes aplicados: {len(ajustes)}")
        for a in ajustes:
            print(f"    ! {a['dimensao']}:{a['label']} WR={a['win_rate']:.1%} degrad={a['degradacao']:.1%}")
    else:
        print(f"  Nenhum ajuste necessario ({len(result_v11.trades)} trades V11)")

    # 5. Generate summary
    print("\n[5/5] Resumo da Validacao...")
    print(f"  Baseline V7: {baseline_path}")
    print(f"  Audit V11: {audit._dir / 'audit_log.json'}")
    audit.flush()

    print("\n" + "=" * 68)
    print("  CRITÉRIOS DE APROVAÇÃO V11:")

    criteria = [
        ("PF V11 >= V7", result_v11.profit_factor, result_v7.profit_factor,
         result_v11.profit_factor >= result_v7.profit_factor),
        ("Expectancy V11 >= V7", result_v11.expectancy, result_v7.expectancy,
         result_v11.expectancy >= result_v7.expectancy),
        ("Drawdown V11 <= V7", result_v7.max_drawdown, result_v11.max_drawdown,
         result_v11.max_drawdown <= result_v7.max_drawdown),
        ("WR V11 >= V7", result_v11.win_rate, result_v7.win_rate,
         result_v11.win_rate >= result_v7.win_rate),
    ]
    passed = sum(1 for _, _, _, ok in criteria if ok)
    for name, v11val, v7val, ok in criteria:
        status = "PASSOU" if ok else "FALHOU"
        print(f"  [{status}] {name}: V7={v7val:.4f} V11={v11val:.4f}")

    print(f"\n  {passed}/{len(criteria)} criterios atendidos")
    if passed == len(criteria):
        print("  V11 APROVADO PARA SUBSTITUIR V7")
    else:
        print("  V11 MANTIDO EM PAPER TRADING — nova calibracao necessaria")
    print("=" * 68)

    return comparison


if __name__ == "__main__":
    main()
```

---

### Task 7: Run tests and verify no regressions

**Files:**
- (none — verification only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest TESTS/ -x -q 2>&1 | tail -10`
Expected: same result as before (no new failures)

- [ ] **Step 2: Run synthetic A/B validation end-to-end**

Run: `python AUDIT/run_ab.py --synthetic 2>&1 | tail -30`
Expected: completes successfully, shows V7 vs V11 comparison

- [ ] **Step 3: Verify audit log was created**

Run: `ls -la AUDIT/data/audit_log.json`
Expected: file exists with V11 thesis/counter-thesis records

---

### Task 8: Generate evidence and report

- [ ] **Step 1: Generate diff of all changes**

Run: `git diff --stat` (or manual file listing if no git)
Expected: list of all files created/modified

- [ ] **Step 2: Show example of V7 vs V11 decision for same signal**

Read from audit log and print one example where both engines had different decisions.

- [ ] **Step 3: Generate final implementation report**

Write report to `MEMORY/audit/ab_report_final.txt`
