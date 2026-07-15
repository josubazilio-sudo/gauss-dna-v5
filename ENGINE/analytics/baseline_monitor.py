import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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


# 7d = ~2016 cycles at 5min each
_WINDOW_7D = 2016
_TREND_ANORMAL = 25
_TREND_ATENCAO = 10
_IMPACT_SIGNAL_PCT = 5
_IMPACT_WR_DROP_MAX = -1
_IMPACT_WR_CRITICAL = -3
_IMPACT_QUALITY_CRITICAL = -0.05
_IMPACT_QUALITY_FLOOR = -0.02
_VALIDATION_COOLDOWN = 86400


class BaselineRegistry:
    def __init__(self, window_7d: int = _WINDOW_7D):
        self._window_7d = window_7d
        self._cycles: deque[CycleSnapshot] = deque(maxlen=window_7d)
        self._gate_history: Dict[str, deque] = {}
        self._changes: List[ParameterChange] = []
        self._session_start: float = time.time()
        self.last_30min_report: float = 0.0

    def record_cycle(self, snapshot: CycleSnapshot) -> None:
        self._cycles.append(snapshot)
        for gate, pct in snapshot.gate_percentages.items():
            if gate not in self._gate_history:
                self._gate_history[gate] = deque(maxlen=self._window_7d)
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

    def cycles_since(self, since: float, until: Optional[float] = None) -> List[CycleSnapshot]:
        if until is None:
            until = time.time() + 1
        return [c for c in self._cycles if since <= c.timestamp < until]

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
        if delta >= _TREND_ANORMAL:
            status = "anormal"
        elif delta >= _TREND_ATENCAO:
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


def _aggregate_gate_counts_24h(registry: BaselineRegistry) -> Dict[str, int]:
    recent = registry.cycles_since(time.time() - 86400)
    if not recent:
        return {}
    total: Dict[str, int] = {}
    for c in recent:
        for gate, count in c.gate_counts.items():
            total[gate] = total.get(gate, 0) + count
    return total


class BaselineAnalyzer:
    def top_rejection_gates(self, registry: BaselineRegistry, n: int = 10) -> List[Dict[str, Any]]:
        total_gate = _aggregate_gate_counts_24h(registry)
        if not total_gate:
            return []
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
        total_gate = _aggregate_gate_counts_24h(registry)
        if not total_gate:
            return []
        total_rej = sum(total_gate.values()) or 1
        bottlenecks = []
        for gate, count in total_gate.items():
            pct = count / total_rej * 100
            trend = registry.get_gate_trend(gate)
            delta = trend.get("delta_pp", 0)
            reasons = []
            if pct >= 25:
                reasons.append(f"{pct:.1f}% das rejeicoes")
            if delta >= _TREND_ATENCAO:
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
            if delta >= _TREND_ANORMAL:
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
        before = registry.cycles_since(change_time - _VALIDATION_COOLDOWN, change_time - 1)
        after = registry.cycles_since(change_time)
        if len(before) < 3 or len(after) < 3:
            return {
                "change": change.param_name,
                "conclusion": "dados_insuficientes",
                "message": "Menos de 3 ciclos antes ou depois da alteracao. Necessario mais dados.",
            }
        before_avg = self._compute_window_averages(before)
        after_avg = self._compute_window_averages(after)
        approved_before = before_avg.get("total_approved", 0)
        approved_after = after_avg.get("total_approved", 0)
        approved_pct = (
            ((approved_after - approved_before) / max(approved_before, 1)) * 100
            if approved_before > 0 else 0
        )
        wr_delta = round(after_avg.get("approval_rate", 0) - before_avg.get("approval_rate", 0), 2)
        quality_delta = round(after_avg.get("avg_quality", 0) - before_avg.get("avg_quality", 0), 4)
        rr_delta = round(after_avg.get("avg_rr", 0) - before_avg.get("avg_rr", 0), 2)
        if approved_pct >= _IMPACT_SIGNAL_PCT and wr_delta >= _IMPACT_WR_DROP_MAX and quality_delta >= _IMPACT_QUALITY_FLOOR:
            classification = "positiva"
            emoji = "\U0001f7e2"
        elif wr_delta <= _IMPACT_WR_CRITICAL or quality_delta <= _IMPACT_QUALITY_CRITICAL:
            classification = "negativa"
            emoji = "\U0001f534"
        else:
            classification = "neutra"
            emoji = "\U0001f7e1"
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
                "approved_pct": round(approved_pct, 1),
                "approval_rate_pp": wr_delta,
                "avg_quality": quality_delta,
                "avg_rr": rr_delta,
            },
        }

    def pending_impacts(self, registry: BaselineRegistry) -> List[Dict[str, Any]]:
        results = []
        for change in registry.changes_pending_validation:
            if time.time() - change.timestamp < _VALIDATION_COOLDOWN:
                continue
            impact = self.change_impact(registry, change)
            results.append({"change": change, "impact": impact})
        return results


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
        lines.append("=== RELATORIO 30 MINUTOS ===")
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
