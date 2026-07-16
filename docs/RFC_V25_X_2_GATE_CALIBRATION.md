# RFC V25.X.2 — Gate Calibration Engine

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement statistical gate calibration module that collects per-gate metrics, computes descriptive statistics, runs threshold simulations, diagnoses market conditions, and generates evidence-based recommendations — without auto-tuning any threshold.

**Architecture:** A new `GateCalibrationEngine` in `ENGINE/analytics/gate_calibration_engine.py` hooks into the existing signal pipeline (via `rejection_analytics.record_signal()` call sites). It accumulates per-gate observations across all signals (approved + rejected), then at cycle end computes statistics + simulations + diagnosis + recommendations. A standalone report is generated and optionally sent to Telegram. Threshold changes require explicit human approval.

**Tech Stack:** Python 3.10+, dataclasses, collections, numpy-style statistics (native), logging, json.

---

## File Changes Map

| File | Action | Purpose |
|------|--------|---------|
| `ENGINE/analytics/gate_calibration_engine.py` | **Create** | Main calibration engine |
| `ENGINE/scanner/scanner_config.py` | Modify | Add calibration config constants |
| `main.py` | Modify | Hook calibration into scan pipeline |
| `ENGINE/diagnostic/fast_diagnostic.py` | Modify | Include calibration summary |
| `TESTS/test_rfc_v25_x2_calibration.py` | **Create** | Unit tests |

---

### Task 1: Create GateCalibrationEngine — Data Collection

**Files:**
- Create: `ENGINE/analytics/gate_calibration_engine.py`

Core structure:

```python
@dataclass
class GateObservation:
    timestamp: str
    symbol: str
    timeframe: str
    direction: str
    result: str  # APPROVED or REJECTED
    gate: str    # gate name (or "" for approved)
    value: float
    threshold: float
    rejected: bool

@dataclass
class GateStats:
    total: int = 0
    approved: int = 0
    rejected: int = 0
    rejection_rate: float = 0.0
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    p10: float = 0.0
    p25: float = 0.0
    p50: float = 0.0
    p75: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    threshold: float = 0.0
```

Key design:
- `record_gate_observation(gate, symbol, timeframe, direction, value, threshold, rejected, result)` — accumulates per-gate data points
- `record_signal_all_gates(signal, sd)` — records ALL gate values for ONE signal (approved AND rejected)
- `end_cycle(min_samples=500)` — computes full analysis
- `_compute_stats(values)` — mean, median, std, min, max, P10-95
- `_simulate_thresholds(gate, stats)` — ±5%, ±10% impact
- `_diagnose_market(stats_by_gate)` — market regime identification
- `_generate_recommendations(stats_by_gate, simulations, diagnosis)` — evidence-based
- `get_calibration_report()` — formatted report text

---

### Task 2: Data Collection Point — record_signal_all_gates()

```python
def record_signal_all_gates(self, signal, sd):
    """Records ALL gate values for a signal."""
    gates = {
        "RVOL": signal.rvol if hasattr(signal, 'rvol') else 0,
        "ADX": signal.adx if hasattr(signal, 'adx') else 0,
        "Entry Zone": sd.entry_score if hasattr(sd, 'entry_score') else 0,
        "Quality Gate": sd.quality if hasattr(sd, 'quality') else 0,
        "Confianca": sd.confidence if hasattr(sd, 'confidence') else 0,
        "Consensus": sd.consensus if hasattr(sd, 'consensus') else 0,
        "Exaustao": ...,
        "Fluxo": ...,
        "Kalman": ...,
        "Trend": ...,
        "SMC": ...,
        "Liquidez": ...,
        "ATR": ...,
    }
```

Each gate gets an individual `GateObservation` appended to its list.

---

### Task 3: Statistics — _compute_stats()

```python
def _compute_stats(self, values: List[float]) -> GateStats:
    if not values:
        return GateStats()
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    mean = total / n
    median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    variance = sum((x - mean) ** 2 for x in sorted_vals) / n
    std = math.sqrt(variance)
    return GateStats(
        total=n, mean=mean, median=median, std=std,
        min_val=sorted_vals[0], max_val=sorted_vals[-1],
        p10=sorted_vals[max(0, int(n * 0.1) - 1)],
        p25=sorted_vals[max(0, int(n * 0.25) - 1)],
        p50=median,
        p75=sorted_vals[min(n - 1, int(n * 0.75))],
        p90=sorted_vals[min(n - 1, int(n * 0.90))],
        p95=sorted_vals[min(n - 1, int(n * 0.95))],
    )
```

---

### Task 4: Threshold Simulation

```python
def _simulate_thresholds(self, gate: str, stats: GateStats, values: List[float]) -> Dict:
    threshold = stats.threshold
    scenarios = [
        ("Atual", 0),
        ("-5%", -0.05),
        ("-10%", -0.10),
        ("+5%", +0.05),
        ("+10%", +0.10),
    ]
    results = {}
    for label, pct_change in scenarios:
        new_th = threshold * (1 + pct_change)
        would_pass = sum(1 for v in values if v >= new_th)
        would_fail = len(values) - would_pass
        approval_rate = would_pass / max(len(values), 1) * 100
        results[label] = {
            "threshold": round(new_th, 4),
            "would_pass": would_pass,
            "would_fail": would_fail,
            "approval_rate": round(approval_rate, 1),
            "pct_change": pct_change,
        }
    return results
```

---

### Task 5: Market Diagnosis

```python
def _diagnose_market(self, stats_by_gate) -> List[str]:
    diagnoses = []
    rvol_stats = stats_by_gate.get("RVOL")
    if rvol_stats and rvol_stats.mean < 0.35:
        diagnoses.append({
            "type": "Mercado com baixo volume",
            "evidence": f"RVOL medio {rvol_stats.mean:.2f} (P90: {rvol_stats.p90:.2f})"
        })
    # ... more diagnoses
    return diagnoses
```

---

### Task 6: Recommendations with Confidence

```python
def _generate_recommendations(self, stats_by_gate, simulations, diagnosis) -> List[Dict]:
    recs = []
    for gate_name, stats in stats_by_gate.items():
        if stats.rejection_rate < 10:
            continue
        gap = stats.threshold - stats.p75
        if gap > stats.threshold * 0.15:
            suggested = round(stats.p75 * 0.95, 2)
            improvement_pct = (stats.p75 - stats.mean) / max(stats.mean, 0.001) * 100
            confidence = min(95, 50 + improvement_pct)
            recs.append({
                "gate": gate_name,
                "current_threshold": stats.threshold,
                "mean_observed": round(stats.mean, 2),
                "p75": round(stats.p75, 2),
                "suggested": suggested,
                "confidence": round(confidence, 0),
                "improvement_pct": round(improvement_pct, 0),
                "reason": f"Mercado apresenta {gate_name} estruturalmente inferior ao threshold configurado"
            })
    return recs
```

---

### Task 7: Integration into main.py

Hook into the existing `_process_scan_result()` at the same point where `rejection_analytics.record_signal()` is called. After the DecisionEngine evaluates the signal, call:
```python
self.calibration_engine.record_signal_all_gates(signal, sd)
```

At cycle end (after rejection_analytics.end_cycle()), call:
```python
report = self.calibration_engine.end_cycle()
if report:
    log.info(report)
    self.telegram.send_calibration_report(report)
```

Add calibration config to scanner_config.py:
```python
CALIBRATION_MIN_SAMPLES = 500
CALIBRATION_ENABLED = True
GATES_FOR_CALIBRATION = ["RVOL", "ADX", "Entry Zone", "Quality Gate", "Confianca", "Consensus", "Exaustao", "Fluxo", "Kalman", "SMC", "Liquidez", "ATR"]
```

---

### Task 8: Tests

```python
# TESTS/test_rfc_v25_x2_calibration.py
# 1. test_record_gate_observation
# 2. test_compute_stats_empty
# 3. test_compute_stats_basic
# 4. test_compute_stats_percentiles
# 5. test_simulate_thresholds
# 6. test_diagnose_low_volume_market
# 7. test_diagnose_lateral_market
# 8. test_diagnose_restrictive_threshold
# 9. test_generate_recommendations
# 10. test_end_cycle_min_samples
# 11. test_calibration_report_format
# 12. test_record_signal_all_gates
```
