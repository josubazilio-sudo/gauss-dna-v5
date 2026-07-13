import logging
from typing import Dict, List, Any

log = logging.getLogger(__name__)


class MIDAnalyzer:
    def analyze(self, snapshot: Dict[str, Any], history: List[Dict]) -> Dict[str, Any]:
        insights = {
            "heatmap": self._build_heatmap(snapshot),
            "trends": self._build_trends(snapshot, history),
            "bottleneck": self._find_bottleneck(snapshot),
        }
        return insights

    def _build_heatmap(self, snapshot: Dict) -> Dict[str, float]:
        dist = snapshot.get("market", {}).get("regime_distribution", {})
        total = max(sum(dist.values()), 1)
        uptrend_pct = round((dist.get("uptrend", 0) + dist.get("downtrend", 0)) / total * 100, 1)
        transition_pct = round(dist.get("transition", 0) / total * 100, 1)
        ranging_pct = round(dist.get("ranging", 0) / total * 100, 1)
        return {
            "Forte Tendencia": uptrend_pct,
            "Transicao": transition_pct,
            "Lateralizacao": ranging_pct,
        }

    def _build_trends(self, snapshot: Dict, history: List[Dict]) -> Dict:
        if not history:
            return {}

        latest = snapshot.get("market", {}).get("avg_metrics", {})

        def _avg(key):
            vals = [s.get("market", {}).get("avg_metrics", {}).get(key, 0) for s in history[-10:]]
            return round(sum(vals) / max(len(vals), 1), 4)

        return {
            "health_trend": [s.get("system", {}).get("health_score", 100) for s in history[-10:]],
            "quality_trend": [s.get("market", {}).get("avg_metrics", {}).get("quality_media", 0) for s in history[-10:]],
            "consensus_trend": [s.get("market", {}).get("avg_metrics", {}).get("consensus_medio", 0) for s in history[-10:]],
            "duration_trend": [s.get("system", {}).get("duration_ms", 0) for s in history[-10:]],
            "signal_count_trend": [s.get("market", {}).get("approved", 0) for s in history[-10:]],
        }

    def _find_bottleneck(self, snapshot: Dict) -> str:
        funnel = snapshot.get("funnel", {})
        max_drop = 0
        bottleneck = "N/A"
        prev_count = snapshot.get("market", {}).get("total_assets", 0)
        stages = ["api", "candles", "indicadores", "estrutura", "smart_money",
                   "entry_zone", "consensus", "quality_gate", "decisao_final"]
        for stage in stages:
            info = funnel.get(stage, {})
            curr = info.get("count", 0)
            drop = prev_count - curr
            if drop > max_drop:
                max_drop = drop
                bottleneck = stage
            prev_count = curr
        return bottleneck
