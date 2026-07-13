import logging
import os
import time
from typing import Dict, List, Optional, Any

from ENGINE.diagnostic.engine import DiagnosticReport

log = logging.getLogger(__name__)


class MIDCollector:
    def __init__(self):
        self._last_api_calls = 0
        self._mem_info = "N/A"
        self._cpu_info = "N/A"

    def collect(self, report: DiagnosticReport, symbols: List[str]) -> Dict[str, Any]:
        now = time.time()
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            self._mem_info = f"{proc.memory_info().rss / 1024 / 1024:.0f}MB"
            self._cpu_info = f"{proc.cpu_percent(interval=0)}%"
        except Exception:
            self._mem_info = "N/A"
            self._cpu_info = "N/A"

        api_calls = self._last_api_calls or sum(
            1 for stages in report.pipeline_audit.values()
            if isinstance(stages, list) and "api" in stages
        )

        return {
            "timestamp": str(report.timestamp),
            "cycle": report.cycle_number,

            "system": {
                "health_score": self._extract_health(report),
                "loop_status": report.loop_status,
                "duration_ms": round(report.duration_ms, 1),
                "memory": self._mem_info,
                "cpu": self._cpu_info,
                "api_calls": api_calls,
                "bug_count": len(report.bugs),
                "next_cycle_in": report.next_cycle_in,
            },

            "market": {
                "total_assets": report.total_assets,
                "approved": report.approved_assets,
                "rejected": sum(report.rejection_reasons.values()),
                "regime_distribution": self._compute_regime_distribution(report),
                "avg_metrics": self._compute_avg_metrics(report),
            },

            "funnel": self._compute_funnel(report),

            "rejection_ranking": self._compute_rejection_ranking(report),

            "opportunities": self._compute_opportunities(report),

            "alerts": [],
        }

    def _extract_health(self, report: DiagnosticReport) -> float:
        h = report.health
        if isinstance(h, dict):
            return h.get("health_score", 100.0)
        return 100.0

    def _compute_regime_distribution(self, report: DiagnosticReport) -> Dict[str, int]:
        counts: Dict[str, int] = {"uptrend": 0, "downtrend": 0, "ranging": 0, "transition": 0}
        for pair, indicators in report.indicators.items():
            if isinstance(indicators, dict) and "regime" in indicators:
                regime = str(indicators["regime"]).lower()
                if regime in counts:
                    counts[regime] += 1
                else:
                    counts["transition"] += 1
        return counts

    def _compute_avg_metrics(self, report: DiagnosticReport) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        for pair, indicators in report.indicators.items():
            if not isinstance(indicators, dict):
                continue
            for key in ("adx", "rvol", "atr_percent", "regime_confidence"):
                val = indicators.get(key)
                if val is not None:
                    try:
                        fval = float(val)
                        totals.setdefault(key, 0.0)
                        totals[key] += fval
                        counts.setdefault(key, 0)
                        counts[key] += 1
                    except (ValueError, TypeError):
                        pass

        avg_metrics = {
            "adx_medio": 0.0,
            "rvol_medio": 0.0,
            "atr_medio": 0.0,
            "volatilidade_media": 0.0,
        }
        for key, label in (("adx", "adx_medio"), ("rvol", "rvol_medio"), ("atr_percent", "atr_medio"), ("regime_confidence", "volatilidade_media")):
            c = counts.get(key, 0)
            if c > 0:
                avg_metrics[label] = round(totals.get(key, 0) / c, 4)

        total_quality = 0.0
        total_consensus = 0.0
        total_confidence = 0.0
        total_entry = 0.0
        qc = cc = confc = ec = 0

        for pair, qg in report.quality_gates.items():
            scores = qg.get("scores", {}) if isinstance(qg, dict) else {}
            if isinstance(scores, dict):
                qv = scores.get("quality_score")
                if qv is not None:
                    total_quality += float(qv); qc += 1
                cv = scores.get("confidence_score")
                if cv is not None:
                    total_confidence += float(cv); confc += 1

        for pair, cs in report.consensus.items():
            val = cs.get("consensus_score") if isinstance(cs, dict) else None
            if val is not None and float(val) > 0:
                try:
                    total_consensus += float(val); cc += 1
                except (ValueError, TypeError):
                    pass

        for pair, ez in report.entry_zones.items():
            val = ez.get("score") if isinstance(ez, dict) else None
            if val is not None:
                try:
                    total_entry += float(val); ec += 1
                except (ValueError, TypeError):
                    pass

        if qc:
            avg_metrics["quality_media"] = round(total_quality / qc, 4)
        if confc:
            avg_metrics["confidence_media"] = round(total_confidence / confc, 4)
        if cc:
            avg_metrics["consensus_medio"] = round(total_consensus / cc, 4)
        if ec:
            avg_metrics["entry_score_medio"] = round(total_entry / ec, 4)

        return avg_metrics

    def _compute_funnel(self, report: DiagnosticReport) -> Dict[str, Any]:
        total = max(report.total_assets, 1)
        stages = ["carregamento", "api", "candles", "indicadores", "estrutura",
                   "smart_money", "entry_zone", "consensus", "quality_gate", "decisao_final"]

        funnel = {}
        for stage in stages:
            count = sum(1 for s in report.pipeline_audit.values() if stage in s)
            funnel[stage] = {
                "count": count,
                "pct": round(count / total * 100, 1),
            }
        funnel["aprovados"] = {"count": report.approved_assets, "pct": round(report.approved_assets / total * 100, 1)}
        funnel["rejeitados"] = {"count": total - report.approved_assets, "pct": round((total - report.approved_assets) / total * 100, 1)}
        return funnel

    def _compute_rejection_ranking(self, report: DiagnosticReport) -> List[Dict]:
        reasons = list(report.rejection_reasons.items())
        reasons.sort(key=lambda x: x[1], reverse=True)
        total_rej = sum(report.rejection_reasons.values()) or 1
        ranking = []
        for reason, count in reasons[:10]:
            ranking.append({"motivo": reason, "count": count, "pct": round(count / total_rej * 100, 1)})
        return ranking

    def _compute_opportunities(self, report: DiagnosticReport) -> List[Dict]:
        candidates = getattr(report, "top_candidates", [])
        return sorted(candidates, key=lambda x: x.get("quality", 0), reverse=True)[:10]

    def record_api_call(self):
        self._last_api_calls += 1

    def reset_api_calls(self):
        self._last_api_calls = 0
