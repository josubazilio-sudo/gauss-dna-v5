# Baseline Drift Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create permanent operational health monitor with per-gate drift detection, parameter change validation, and 30-minute automated reports.

**Architecture:** Three classes in `baseline_monitor.py`: `BaselineRegistry` (data storage via deques), `BaselineAnalyzer` (stateless computations), `BaselineReporter` (log+Telegram formatting). Integrated into main.py's cycle end with fail-safe try/except.

**Tech Stack:** Python 3.14, typing, collections.deque, dataclasses

---

### Task 1: Create baseline_monitor.py — Dataclasses + BaselineRegistry

**Files:**
- Create: `ENGINE/analytics/baseline_monitor.py`

- [ ] **Step 1: Write CycleSnapshot and ParameterChange dataclasses**

```python
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class CycleSnapshot:
    cycle: int = 0
    timestamp: float = 0.0
    total_analyzed: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    approval_rate: float = 0.0
    avg_quality: float = 0.0
    avg_confidence: float = 0.0
    avg_consensus: float = 0.0
    avg_rr: float = 0.0
    gate_percentages: Dict[str, float] = field(default_factory=dict)
    gate_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class ParameterChange:
    param_name: str = ""
    old_value: Any = None
    new_value: Any = None
    reason: str = ""
    version: str = ""
    timestamp: float = 0.0
    cycle_applied: int = 0
    validated: bool = False
    impact: Optional[str] = None
    impact_data: Optional[Dict[str, Any]] = None
```

- [ ] **Step 2: Write BaselineRegistry class**

```python
# 24h = ~288 cycles at 5min each, 7d = ~2016
_WINDOW_24H = 288
_WINDOW_7D = 2016


class BaselineRegistry:
    def __init__(self, window_24h: int = _WINDOW_24H, window_7d: int = _WINDOW_7D):
        self._cycles: deque[CycleSnapshot] = deque(maxlen=window_7d)
        self._gate_history: Dict[str, deque] = {}
        self._changes: List[ParameterChange] = []
        self._session_start: float = time.time()
        self.last_30min_report: float = 0.0

    def record_cycle(self, snapshot: CycleSnapshot) -> None:
        self._cycles.append(snapshot)
        for gate, pct in snapshot.gate_percentages.items():
            if gate not in self._gate_history:
                self._gate_history[gate] = deque(maxlen=_WINDOW_7D)
            self._gate_history[gate].append(pct)

    def record_change(self, param_name: str, old_value: Any, new_value: Any,
                      reason: str, version: str, cycle_applied: int) -> None:
        self._changes.append(ParameterChange(
            param_name=param_name,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            version=version,
            timestamp=time.time(),
            cycle_applied=cycle_applied,
        ))

    @property
    def cycles(self) -> List[CycleSnapshot]:
        return list(self._cycles)

    def cycles_since(self, since: float) -> List[CycleSnapshot]:
        return [c for c in self._cycles if c.timestamp >= since]

    @property
    def cycles_24h(self) -> List[CycleSnapshot]:
        return self.cycles_since(time.time() - 86400)

    @property
    def cycles_7d(self) -> List[CycleSnapshot]:
        return list(self._cycles)

    @property
    def changes(self) -> List[ParameterChange]:
        return list(self._changes)

    @property
    def changes_pending_validation(self) -> List[ParameterChange]:
        return [c for c in self._changes if not c.validated]

    def get_gate_trend(self, gate: str, hours: int = 24) -> Dict[str, Any]:
        if gate not in self._gate_history or len(self._gate_history[gate]) < 2:
            return {"gate": gate, "status": "sem_dados_suficientes"}
        all_vals = list(self._gate_history[gate])
        recent_window = max(1, int(len(all_vals) * (hours / 24 / 7)))
        recent = all_vals[-recent_window:]
        historical = all_vals[:-recent_window] if len(all_vals) > recent_window else all_vals
        avg_recent = sum(recent) / len(recent)
        avg_hist = sum(historical) / len(historical) if historical else avg_recent
        delta = round(avg_recent - avg_hist, 1)
        if delta >= 25:
            status = "anormal"
        elif delta >= 10:
            status = "atencao"
        else:
            status = "normal"
        return {
            "gate": gate,
            "avg_historical": round(avg_hist, 1),
            "avg_recent": round(avg_recent, 1),
            "delta_pp": delta,
            "status": status,
        }

    def get_gate_trends(self) -> Dict[str, Dict[str, Any]]:
        return {g: self.get_gate_trend(g) for g in self._gate_history}

    def get_summary_stats(self) -> Dict[str, float]:
        if not self._cycles:
            return {}
        recent = self.cycles_since(time.time() - 3600) or self.cycles_24h
        if not recent:
            return {}
        return {
            "avg_approval_rate": round(sum(c.approval_rate for c in recent) / len(recent), 2),
            "avg_quality": round(sum(c.avg_quality for c in recent) / len(recent), 4),
            "avg_confidence": round(sum(c.avg_confidence for c in recent) / len(recent), 4),
            "avg_consensus": round(sum(c.avg_consensus for c in recent) / len(recent), 4),
            "avg_rr": round(sum(c.avg_rr for c in recent) / len(recent), 2),
            "total_cycles": len(self._cycles),
            "total_analyzed": sum(c.total_analyzed for c in self._cycles),
            "total_approved": sum(c.total_approved for c in self._cycles),
            "session_hours": round((time.time() - self._session_start) / 3600, 1),
        }
```

- [ ] **Step 3: Run basic import check**

Run:
```powershell
python -c "from ENGINE.analytics.baseline_monitor import BaselineRegistry, CycleSnapshot, ParameterChange; print('OK')"
```
Expected: `OK`

---

### Task 2: Create baseline_monitor.py — BaselineAnalyzer

**Files:**
- Modify: `ENGINE/analytics/baseline_monitor.py` (append to file)

- [ ] **Step 1: Write BaselineAnalyzer class**

```python
class BaselineAnalyzer:
    def top_rejection_gates(self, registry: BaselineRegistry, n: int = 10) -> List[Dict[str, Any]]:
        recent = registry.cycles_since(time.time() - 86400)
        if not recent:
            return []
        total_gate: Dict[str, int] = {}
        for c in recent:
            for gate, count in c.gate_counts.items():
                total_gate[gate] = total_gate.get(gate, 0) + count
        total_rej = sum(total_gate.values()) or 1
        sorted_gates = sorted(
            total_gate.items(), key=lambda x: -x[1]
        )[:n]
        result = []
        for gate, count in sorted_gates:
            trend = registry.get_gate_trend(gate)
            result.append({
                "gate": gate,
                "count": count,
                "pct": round(count / total_rej * 100, 1),
                "trend_status": trend.get("status", "sem_dados"),
                "delta_pp": trend.get("delta_pp", 0),
            })
        return result

    def gate_with_greatest_growth(self, registry: BaselineRegistry) -> Optional[Dict[str, Any]]:
        trends = registry.get_gate_trends()
        candidates = [
            t for t in trends.values()
            if t.get("status") in ("anormal", "atencao") and t.get("delta_pp", 0) > 0
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x.get("delta_pp", 0))

    def gate_with_greatest_reduction(self, registry: BaselineRegistry) -> Optional[Dict[str, Any]]:
        trends = registry.get_gate_trends()
        candidates = [
            t for t in trends.values()
            if t.get("delta_pp", 0) < 0
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda x: x.get("delta_pp", 0))

    def potential_bottlenecks(self, registry: BaselineRegistry) -> List[Dict[str, Any]]:
        recent = registry.cycles_since(time.time() - 86400)
        if not recent:
            return []
        total_gate: Dict[str, int] = {}
        for c in recent:
            for gate, count in c.gate_counts.items():
                total_gate[gate] = total_gate.get(gate, 0) + count
        total_rej = sum(total_gate.values()) or 1
        bottlenecks = []
        for gate, count in total_gate.items():
            pct = count / total_rej * 100
            trend = registry.get_gate_trend(gate)
            delta = trend.get("delta_pp", 0)
            reasons = []
            if pct >= 25:
                reasons.append(f"{pct:.1f}% das rejeicoes")
            if delta >= 10:
                reasons.append(f"crescimento de {delta:+.1f}pp vs historico")
            if reasons:
                bottlenecks.append({
                    "gate": gate,
                    "pct": round(pct, 1),
                    "delta_pp": delta,
                    "status": trend.get("status", "desconhecido"),
                    "reasons": reasons,
                })
        return sorted(bottlenecks, key=lambda x: -x["pct"])

    def potential_bugs(self, registry: BaselineRegistry) -> List[Dict[str, Any]]:
        trends = registry.get_gate_trends()
        bugs = []
        for gate, trend in trends.items():
            delta = trend.get("delta_pp", 0)
            if delta >= 25:
                bugs.append({
                    "gate": gate,
                    "delta_pp": delta,
                    "avg_historical": trend.get("avg_historical"),
                    "avg_recent": trend.get("avg_recent"),
                    "suspect_cause": f"Delta de {delta:+.1f}pp indica possivel bug ou mudanca nao intencional",
                })
        return bugs

    def _compute_window_averages(self, cycles: List[CycleSnapshot]) -> Dict[str, float]:
        if not cycles:
            return {}
        n = len(cycles)
        return {
            "approval_rate": round(sum(c.approval_rate for c in cycles) / n, 2),
            "avg_quality": round(sum(c.avg_quality for c in cycles) / n, 4),
            "avg_confidence": round(sum(c.avg_confidence for c in cycles) / n, 4),
            "avg_consensus": round(sum(c.avg_consensus for c in cycles) / n, 4),
            "avg_rr": round(sum(c.avg_rr for c in cycles) / n, 2),
            "total_analyzed": sum(c.total_analyzed for c in cycles),
            "total_approved": sum(c.total_approved for c in cycles),
            "cycle_count": n,
        }

    def change_impact(self, registry: BaselineRegistry, change: ParameterChange) -> Dict[str, Any]:
        change_time = change.timestamp
        before = registry.cycles_since(change_time - 86400, change_time - 1)
        after = registry.cycles_since(change_time)
        if len(before) < 3 or len(after) < 3:
            return {
                "change": change.param_name,
                "conclusion": "dados_insuficientes",
                "message": "Menos de 3 ciclos antes ou depois da alteracao. Necessario mais dados.",
            }
        before_avg = self._compute_window_averages(before)
        after_avg = self._compute_window_averages(after)
        signal_delta = after_avg.get("total_approved", 0) - before_avg.get("total_approved", 0)
        signal_pct = (
            (signal_delta / max(before_avg.get("total_approved", 1), 1)) * 100
            if before_avg.get("total_approved", 0) > 0 else 0
        )
        wr_delta = round(after_avg.get("approval_rate", 0) - before_avg.get("approval_rate", 0), 2)
        quality_delta = round(after_avg.get("avg_quality", 0) - before_avg.get("avg_quality", 0), 4)
        rr_delta = round(after_avg.get("avg_rr", 0) - before_avg.get("avg_rr", 0), 2)
        if signal_pct >= 5 and wr_delta >= -1 and quality_delta >= -0.02:
            classification = "positiva"
            emoji = "🟢"
        elif wr_delta <= -3 or quality_delta <= -0.05:
            classification = "negativa"
            emoji = "🔴"
        else:
            classification = "neutra"
            emoji = "🟡"
        return {
            "change": change.param_name,
            "old_value": change.old_value,
            "new_value": change.new_value,
            "version": change.version,
            "conclusion": f"{emoji} {classification}",
            "classification": classification,
            "before": before_avg,
            "after": after_avg,
            "deltas": {
                "sinais_pct": round(signal_pct, 1),
                "approval_rate_pp": wr_delta,
                "avg_quality": quality_delta,
                "avg_rr": rr_delta,
            },
        }

    def all_changes_validate(self, registry: BaselineRegistry) -> List[Dict[str, Any]]:
        results = []
        for change in registry.changes_pending_validation:
            if time.time() - change.timestamp < 86400:
                continue
            impact = self.change_impact(registry, change)
            change.validated = True
            change.impact = impact.get("classification", "desconhecida")
            change.impact_data = impact
            results.append({"change": change, "impact": impact})
        return results
```

Note: `cycles_since` needs an optional `until` parameter. Let me add it:

- [ ] **Step 2: Update BaselineRegistry.cycles_since to accept optional `until`**

Replace the cycles_since method:

```python
    def cycles_since(self, since: float, until: Optional[float] = None) -> List[CycleSnapshot]:
        if until is None:
            until = time.time() + 1
        return [c for c in self._cycles if since <= c.timestamp < until]
```

- [ ] **Step 3: Run import check**

Run:
```powershell
python -c "from ENGINE.analytics.baseline_monitor import BaselineRegistry, BaselineAnalyzer, CycleSnapshot, ParameterChange; print('OK')"
```
Expected: `OK`

---

### Task 3: Create baseline_monitor.py — BaselineReporter

**Files:**
- Modify: `ENGINE/analytics/baseline_monitor.py` (append to file)

- [ ] **Step 1: Write BaselineReporter class**

```python
class BaselineReporter:
    def __init__(self, analyzer: BaselineAnalyzer):
        self._analyzer = analyzer

    def build_30min_report(self, registry: BaselineRegistry) -> Dict[str, Any]:
        now = time.time()
        recent_24h = registry.cycles_since(now - 86400)
        summary = registry.get_summary_stats()
        trends = registry.get_gate_trends()
        top_gates = self._analyzer.top_rejection_gates(registry)
        bottlenecks = self._analyzer.potential_bottlenecks(registry)
        bugs = self._analyzer.potential_bugs(registry)
        growth = self._analyzer.gate_with_greatest_growth(registry)
        reduction = self._analyzer.gate_with_greatest_reduction(registry)
        total_approved_24h = sum(c.total_approved for c in recent_24h) if recent_24h else 0
        total_analyzed_24h = sum(c.total_analyzed for c in recent_24h) if recent_24h else 0
        approval_24h = round(total_approved_24h / max(total_analyzed_24h, 1) * 100, 2)
        health = "Saudavel" if approval_24h >= 1.0 else "Restritivo" if approval_24h > 0 else "Critico"
        top_near = sum(
            1 for c in recent_24h[-10:] if c.approval_rate > 0 and c.approval_rate < 5
        ) if recent_24h else 0
        return {
            "timestamp": now,
            "scanner_health": health,
            "market": "N/A",
            "total_analyzed_24h": total_analyzed_24h,
            "total_approved_24h": total_approved_24h,
            "approval_rate_24h": approval_24h,
            "top_rejection_gates": top_gates,
            "top_near_approved_indicators": top_near,
            "gate_greatest_growth": growth,
            "gate_greatest_reduction": reduction,
            "potential_bottlenecks": bottlenecks,
            "potential_bugs": bugs,
            "baseline_comparison": {
                "summary_stats": summary,
                "gate_trends": trends,
            },
            "pending_validations": [
                {"param": c.param_name, "version": c.version,
                 "old": c.old_value, "new": c.new_value}
                for c in registry.changes_pending_validation
            ],
        }

    def format_30min_log(self, report: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"=== RELATORIO 30 MINUTOS ===")
        lines.append(f"Scanner: {report.get('scanner_health', 'N/A')}")
        lines.append(f"Analisados 24h: {report.get('total_analyzed_24h', 0)}")
        lines.append(f"Aprovados 24h: {report.get('total_approved_24h', 0)}")
        lines.append(f"Taxa Aprovacao 24h: {report.get('approval_rate_24h', 0):.2f}%")
        lines.append("--- Top Gates Rejeicao ---")
        for g in report.get("top_rejection_gates", []):
            lines.append(f"  {g['gate']}: {g['pct']}% ({g['count']}x) [{g['trend_status']}]")
        growth = report.get("gate_greatest_growth")
        if growth:
            lines.append(f"Maior crescimento: {growth['gate']} ({growth['delta_pp']:+.1f}pp)")
        reduction = report.get("gate_greatest_reduction")
        if reduction:
            lines.append(f"Maior reducao: {reduction['gate']} ({reduction['delta_pp']:+.1f}pp)")
        for b in report.get("potential_bottlenecks", []):
            lines.append(f"Gargalo: {b['gate']} - {'; '.join(b['reasons'])}")
        for b in report.get("potential_bugs", []):
            lines.append(f"BUG: {b['gate']} - {b['suspect_cause']}")
        pending = report.get("pending_validations", [])
        if pending:
            lines.append(f"Validacoes pendentes: {len(pending)}")
            for p in pending:
                lines.append(f"  {p['param']}: {p['old']} -> {p['new']} ({p['version']})")
        lines.append("===========================")
        return "\n".join(lines)

    def format_30min_telegram(self, report: Dict[str, Any]) -> str:
        lines = []
        lines.append("\U0001f916 *QuantOS - Relatorio 30min*")
        lines.append("")
        lines.append(f"Scanner: {report.get('scanner_health', 'N/A')}")
        lines.append(f"Aprovados: {report.get('total_approved_24h', 0)}/{report.get('total_analyzed_24h', 0)} ({report.get('approval_rate_24h', 0):.2f}%)")
        lines.append("")
        top = report.get("top_rejection_gates", [])[:5]
        if top:
            lines.append("*Top Rejeicoes:*")
            for g in top:
                marker = "\u26a0\ufe0f" if g.get("trend_status") == "anormal" else ""
                lines.append(f"  {g['gate']}: {g['pct']}% {marker}")
            lines.append("")
        growth = report.get("gate_greatest_growth")
        if growth:
            lines.append(f"\u26a0\ufe0f *Alerta:* {growth['gate']} ({growth['delta_pp']:+.1f}pp vs historico)")
        bugs = report.get("potential_bugs", [])
        if bugs:
            lines.append(f"\U0001f41b *Bug suspeito:* {bugs[0]['gate']}")
        pending = report.get("pending_validations", [])
        if pending:
            lines.append(f"\U0001f4ca *Validacoes pendentes:* {len(pending)}")
        return "\n".join(lines)

    def build_change_report(self, change: ParameterChange, impact: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"\U0001f4ca *Validacao: {change.param_name}*")
        lines.append(f"Antes: `{change.old_value}` | Depois: `{change.new_value}`")
        lines.append(f"Versao: {change.version} | Motivo: {change.reason}")
        lines.append("")
        deltas = impact.get("deltas", {})
        lines.append(f"Aprovados: {deltas.get('approved_pct', 0):+.1f}%")
        lines.append(f"Approval Rate: {deltas.get('approval_rate_pp', 0):+.2f}pp")
        lines.append(f"Qualidade Media: {deltas.get('avg_quality', 0):+.4f}")
        lines.append(f"RR Medio: {deltas.get('avg_rr', 0):+.2f}")
        lines.append("")
        lines.append(f"*Conclusao:* {impact.get('conclusion', 'N/A')}")
        if impact.get("classification") == "negativa":
            lines.append("\u26a0\ufe0f Considere reverter esta alteracao.")
        elif impact.get("classification") == "positiva":
            lines.append("\u2705 Alteracao validada.")
        elif impact.get("classification") == "neutra":
            lines.append("\U0001f7e1 Impacto neutro. Necessario mais dados.")
        else:
            lines.append("\U0001f7e0 " + impact.get("message", "Aguardando dados."))
        return "\n".join(lines)
```

- [ ] **Step 2: Run final import check**

Run:
```powershell
python -c "from ENGINE.analytics.baseline_monitor import BaselineRegistry, BaselineAnalyzer, BaselineReporter, CycleSnapshot, ParameterChange; print('OK')"
```
Expected: `OK`

---

### Task 4: Write tests for BaselineRegistry

**Files:**
- Create: `TESTS/test_rfc_v25_7_baseline_monitor.py`

- [ ] **Step 1: Write test preamble + TestBaselineRegistry**

```python
import time
import pytest
from ENGINE.analytics.baseline_monitor import (
    BaselineRegistry, BaselineAnalyzer, BaselineReporter,
    CycleSnapshot, ParameterChange,
)


class TestBaselineRegistry:
    def test_record_cycle_updates_history(self):
        reg = BaselineRegistry()
        snap = CycleSnapshot(cycle=1, timestamp=time.time(),
                             total_analyzed=100, total_approved=5,
                             approval_rate=5.0,
                             gate_percentages={"CONSENSO": 40.0},
                             gate_counts={"CONSENSO": 38})
        reg.record_cycle(snap)
        assert len(reg.cycles) == 1
        assert reg.cycles[0].cycle == 1

    def test_cycles_24h_filters_by_time(self):
        reg = BaselineRegistry()
        old = time.time() - 90000  # ~25h ago
        reg.record_cycle(CycleSnapshot(cycle=1, timestamp=old,
                         gate_percentages={}, gate_counts={}))
        reg.record_cycle(CycleSnapshot(cycle=2, timestamp=time.time(),
                         gate_percentages={}, gate_counts={}))
        assert len(reg.cycles) == 2
        assert len(reg.cycles_24h) == 1
        assert reg.cycles_24h[0].cycle == 2

    def test_cycles_7d_respects_deque_maxlen(self):
        reg = BaselineRegistry(window_7d=10)
        for i in range(15):
            reg.record_cycle(CycleSnapshot(cycle=i, timestamp=time.time(),
                             gate_percentages={}, gate_counts={}))
        assert len(reg.cycles) == 10  # maxlen=10

    def test_get_gate_trend_normal(self):
        reg = BaselineRegistry()
        now = time.time()
        for i in range(10):
            reg.record_cycle(CycleSnapshot(cycle=i, timestamp=now + i,
                             gate_percentages={"CONSENSO": 30.0 + i * 0.5},
                             gate_counts={"CONSENSO": 10}))
        trend = reg.get_gate_trend("CONSENSO")
        assert trend["status"] == "normal"

    def test_get_gate_trend_anormal(self):
        reg = BaselineRegistry()
        now = time.time()
        for i in range(10):
            pct = 20.0 if i < 5 else 55.0
            reg.record_cycle(CycleSnapshot(cycle=i, timestamp=now + i,
                             gate_percentages={"EXAUSTAO": pct},
                             gate_counts={"EXAUSTAO": int(pct)}))
        trend = reg.get_gate_trend("EXAUSTAO")
        assert trend["status"] == "anormal"
        assert trend["delta_pp"] >= 25

    def test_get_gate_trend_sem_dados(self):
        reg = BaselineRegistry()
        trend = reg.get_gate_trend("NONE")
        assert trend["status"] == "sem_dados_suficientes"

    def test_record_change_appends(self):
        reg = BaselineRegistry()
        reg.record_change("THRESHOLD", 0.55, 0.50, "Test", "RFC V99", 1)
        assert len(reg.changes) == 1
        assert reg.changes[0].param_name == "THRESHOLD"
        assert reg.changes[0].validated == False

    def test_changes_pending_validation(self):
        reg = BaselineRegistry()
        reg.record_change("A", 1, 2, "T", "V1", 1)
        reg.changes[0].validated = True
        reg.record_change("B", 3, 4, "T", "V1", 2)
        assert len(reg.changes_pending_validation) == 1
        assert reg.changes_pending_validation[0].param_name == "B"

    def test_summary_stats_empty(self):
        reg = BaselineRegistry()
        stats = reg.get_summary_stats()
        assert stats == {}
```

- [ ] **Step 2: Run registry tests**

Run:
```powershell
python -m pytest TESTS/test_rfc_v25_7_baseline_monitor.py::TestBaselineRegistry -v
```
Expected: 8 passed

---

### Task 5: Write tests for BaselineAnalyzer

**Files:**
- Modify: `TESTS/test_rfc_v25_7_baseline_monitor.py` (append)

- [ ] **Step 1: Write TestBaselineAnalyzer class**

```python
class TestBaselineAnalyzer:
    def _registry_with_data(self):
        reg = BaselineRegistry()
        now = time.time()
        # 10 ciclos: CONSENSO dominante, QUALIDADE cresce
        for i in range(10):
            reg.record_cycle(CycleSnapshot(
                cycle=i, timestamp=now + i * 300,
                total_analyzed=100, total_approved=3 if i < 7 else 8,
                total_rejected=97 if i < 7 else 92,
                approval_rate=3.0 if i < 7 else 8.0,
                avg_quality=0.55 if i < 7 else 0.65,
                avg_confidence=0.60, avg_consensus=0.45,
                avg_rr=2.2,
                gate_percentages={
                    "CONSENSO": 44.0, "EXAUSTAO": 29.0,
                    "QUALIDADE": 12.0, "OUTROS": 3.0,
                },
                gate_counts={
                    "CONSENSO": 44, "EXAUSTAO": 29,
                    "QUALIDADE": 12, "OUTROS": 3,
                },
            ))
        return reg

    def test_top_rejection_gates_ordered(self):
        reg = self._registry_with_data()
        analyzer = BaselineAnalyzer()
        top = analyzer.top_rejection_gates(reg)
        assert len(top) > 0
        assert top[0]["gate"] == "CONSENSO"

    def test_gate_greatest_growth(self):
        reg = self._registry_with_data()
        analyzer = BaselineAnalyzer()
        growth = analyzer.gate_with_greatest_growth(reg)
        assert growth is not None

    def test_gate_greatest_reduction(self):
        reg = self._registry_with_data()
        analyzer = BaselineAnalyzer()
        reduction = analyzer.gate_with_greatest_reduction(reg)
        assert reduction is not None

    def test_potential_bottlenecks(self):
        reg = self._registry_with_data()
        analyzer = BaselineAnalyzer()
        bottlenecks = analyzer.potential_bottlenecks(reg)
        assert any(b["gate"] == "CONSENSO" for b in bottlenecks)

    def test_potential_bugs_empty_with_small_deltas(self):
        reg = self._registry_with_data()
        analyzer = BaselineAnalyzer()
        bugs = analyzer.potential_bugs(reg)
        # Deltas nao devem atingir 25pp com dados normais
        assert len(bugs) == 0

    def test_potential_bugs_detects_large_delta(self):
        reg = BaselineRegistry()
        now = time.time()
        for i in range(10):
            pct = 10.0 if i < 5 else 45.0
            reg.record_cycle(CycleSnapshot(
                cycle=i, timestamp=now + i,
                gate_percentages={"BUGADO": pct},
                gate_counts={"BUGADO": int(pct)},
            ))
        analyzer = BaselineAnalyzer()
        bugs = analyzer.potential_bugs(reg)
        assert len(bugs) >= 1
        assert bugs[0]["gate"] == "BUGADO"

    def test_change_impact_dados_insuficientes(self):
        reg = BaselineRegistry()
        change = ParameterChange(param_name="TEST", old_value=1, new_value=2,
                                 timestamp=time.time() - 43200, cycle_applied=1)
        analyzer = BaselineAnalyzer()
        result = analyzer.change_impact(reg, change)
        assert result["conclusion"] == "dados_insuficientes"
```

- [ ] **Step 2: Run analyzer tests**

Run:
```powershell
python -m pytest TESTS/test_rfc_v25_7_baseline_monitor.py::TestBaselineAnalyzer -v
```
Expected: 7 passed

---

### Task 6: Write tests for BaselineReporter

**Files:**
- Modify: `TESTS/test_rfc_v25_7_baseline_monitor.py` (append)

- [ ] **Step 1: Write TestBaselineReporter class**

```python
class TestBaselineReporter:
    def _setup(self):
        reg = BaselineRegistry()
        now = time.time()
        for i in range(10):
            reg.record_cycle(CycleSnapshot(
                cycle=i, timestamp=now + i * 300,
                total_analyzed=100, total_approved=3,
                approval_rate=3.0,
                avg_quality=0.55, avg_confidence=0.60,
                avg_consensus=0.45, avg_rr=2.2,
                gate_percentages={"CONSENSO": 44.0, "EXAUSTAO": 29.0},
                gate_counts={"CONSENSO": 44, "EXAUSTAO": 29},
            ))
        reg.record_change("TEST", 0.55, 0.50, "Test", "RFC V99", 1)
        return reg

    def test_build_30min_report_structure(self):
        reg = self._setup()
        analyzer = BaselineAnalyzer()
        reporter = BaselineReporter(analyzer)
        report = reporter.build_30min_report(reg)
        assert "scanner_health" in report
        assert "total_analyzed_24h" in report
        assert "top_rejection_gates" in report
        assert "potential_bottlenecks" in report
        assert "potential_bugs" in report
        assert "pending_validations" in report

    def test_format_30min_log_includes_key_fields(self):
        reg = self._setup()
        analyzer = BaselineAnalyzer()
        reporter = BaselineReporter(analyzer)
        report = reporter.build_30min_report(reg)
        text = reporter.format_30min_log(report)
        assert "RELATORIO 30 MINUTOS" in text
        assert "CONSENSO" in text
        assert "EXAUSTAO" in text

    def test_format_30min_telegram_includes_emojis(self):
        reg = self._setup()
        analyzer = BaselineAnalyzer()
        reporter = BaselineReporter(analyzer)
        report = reporter.build_30min_report(reg)
        text = reporter.format_30min_telegram(report)
        assert "QuantOS" in text
        assert "Top Rejeicoes" in text

    def test_build_change_report_includes_conclusion(self):
        reg = self._setup()
        analyzer = BaselineAnalyzer()
        reporter = BaselineReporter(analyzer)
        change = reg.changes[0]
        impact = analyzer.change_impact(reg, change)
        text = reporter.build_change_report(change, impact)
        assert change.param_name in text
        assert "Conclusao" in text
```

- [ ] **Step 2: Run reporter tests**

Run:
```powershell
python -m pytest TESTS/test_rfc_v25_7_baseline_monitor.py::TestBaselineReporter -v
```
Expected: 4 passed

---

### Task 7: Modify main.py — Integrate BaselineRegistry

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add import at top of main.py**

Find the existing diagnostic imports (around line 30-40) and add:

```python
from ENGINE.analytics.baseline_monitor import (
    BaselineRegistry, BaselineAnalyzer, BaselineReporter, CycleSnapshot,
)
```

- [ ] **Step 2: Add init in QuantOSApp constructor**

Find `self._diag_baseline = DiagnosticBaseline()` (~line 250) and add after it:

```python
        self._baseline_registry = BaselineRegistry()
        self._baseline_analyzer = BaselineAnalyzer()
        self._baseline_reporter = BaselineReporter(self._baseline_analyzer)
```

- [ ] **Step 3: Add cycle recording + 30min report after rejection_summary**

Find the block after `rejection_summary = self._rejection_analytics.end_cycle()` (around line 513-518) and add after the analytics log loop:

```python
                try:
                    _recs = self._rejection_analytics.cycle_records
                    _qual = [r.quality for r in _recs if r.quality]
                    _conf = [r.confidence for r in _recs if r.confidence]
                    _cons = [r.consensus for r in _recs if r.consensus]
                    _snap = CycleSnapshot(
                        cycle=self._scan_count,
                        timestamp=time.time(),
                        total_analyzed=rejection_summary.get("total_analyzed", 0),
                        total_approved=rejection_summary.get("total_approved", 0),
                        total_rejected=rejection_summary.get("total_rejected", 0),
                        approval_rate=rejection_summary.get("approval_rate", 0.0),
                        avg_quality=round(sum(_qual) / max(len(_qual), 1), 4) if _qual else 0.0,
                        avg_confidence=round(sum(_conf) / max(len(_conf), 1), 4) if _conf else 0.0,
                        avg_consensus=round(sum(_cons) / max(len(_cons), 1), 4) if _cons else 0.0,
                        avg_rr=0.0,
                        gate_percentages=rejection_summary.get("gate_percentages", {}),
                        gate_counts=rejection_summary.get("gate_counts", {}),
                    )
                    self._baseline_registry.record_cycle(_snap)
                except Exception as e:
                    log.warning("BaselineRegistry: erro ao registrar ciclo: %s", e)
```

- [ ] **Step 4: Add 30min timer after cycle recording**

Add immediately after the cycle recording block:

```python
                try:
                    _now = time.time()
                    if _now - self._baseline_registry.last_30min_report >= 1800:
                        self._baseline_registry.last_30min_report = _now
                        _report = self._baseline_reporter.build_30min_report(self._baseline_registry)
                        for _line in self._baseline_reporter.format_30min_log(_report).split("\n"):
                            log.info("30MIN| %s", _line)
                        self._telegram.send_diagnostic(
                            self._baseline_reporter.format_30min_telegram(_report)
                        )
                        _impacts = self._baseline_analyzer.pending_impacts(
                            self._baseline_registry
                        )
                        for _v in _impacts:
                            _c = _v["change"]
                            _i = _v["impact"]
                            _c.validated = True
                            _c.impact = _i.get("classification", "desconhecida")
                            _c.impact_data = _i
                            _msg = self._baseline_reporter.build_change_report(_c, _i)
                            log.info("CHANGE_VALIDATION| %s", _msg.replace("\n", " | "))
                            self._telegram.send_diagnostic(_msg)
                except Exception as e:
                    log.warning("30MIN: erro ao gerar relatorio: %s", e)
```

- [ ] **Step 5: Run existing tests to verify no regression**

Run:
```powershell
python -m pytest TESTS/test_rfc_v25_5_fast_diagnostic.py TESTS/test_decision_engine_recalibracao.py TESTS/test_rfc_v21_math_auditor.py -v --tb=short
```
Expected: All passed (97+)

---

### Task 8: Run all tests

**Files:**
- No file changes

- [ ] **Step 1: Run new baseline monitor tests**

Run:
```powershell
python -m pytest TESTS/test_rfc_v25_7_baseline_monitor.py -v
```
Expected: ~19 passed

- [ ] **Step 2: Run full test suite**

Run:
```powershell
python -m pytest TESTS/ -v --tb=short 2>&1 | Select-Object -Last 20
```
Expected: All tests pass (518+19 = ~537)

---

### Task 9: Commit

**Files:**
- `ENGINE/analytics/baseline_monitor.py` (created)
- `main.py` (modified)
- `TESTS/test_rfc_v25_7_baseline_monitor.py` (created)

- [ ] **Step 1: Commit**

```bash
git add ENGINE/analytics/baseline_monitor.py main.py TESTS/test_rfc_v25_7_baseline_monitor.py
git commit -m "feat: RFC V25.7 Baseline Drift Monitor + validacao cientifica

- BaselineRegistry: armazena snapshots de ciclo, gate trends, changes
- BaselineAnalyzer: top gates, bottlenecks, bugs, change impact
- BaselineReporter: relatorio 30min (log + Telegram), change validation
- Integrado em main.py com fail-safe try/except
- 19 novos testes passando"
```
