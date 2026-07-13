import logging
import time
from typing import Dict, List, Any, Optional

from .mid_config import (
    ALERT_TREND_THRESHOLD,
    ALERT_RANGE_THRESHOLD,
    ALERT_RVOL_SPIKE,
    ALERT_VOLATILITY_SPIKE,
    ALERT_CONSENSUS_SURGE,
    ALERT_ELITE_COUNT,
    MID_ALERT_COOLDOWN_SECONDS,
)

log = logging.getLogger(__name__)


class MIDAlertEngine:
    def __init__(self):
        self._cooldowns: Dict[str, float] = {}

    def check(self, snapshot: Dict[str, Any], prev_snapshot: Optional[Dict]) -> List[Dict]:
        alerts = []
        now = time.time()

        market = snapshot.get("market", {})
        heatmap = snapshot.get("analyzer", {}).get("heatmap", {})

        trend_pct = heatmap.get("Forte Tendencia", 0)
        range_pct = heatmap.get("Lateralizacao", 0)

        if trend_pct >= ALERT_TREND_THRESHOLD * 100:
            alert = self._make_alert("TREND_SURGE", f"Mais de {ALERT_TREND_THRESHOLD*100:.0f}% dos ativos em tendencia ({trend_pct:.0f}%)", now)
            if alert:
                alerts.append(alert)

        if range_pct >= ALERT_RANGE_THRESHOLD * 100:
            alert = self._make_alert("RANGE_SURGE", f"Mais de {ALERT_RANGE_THRESHOLD*100:.0f}% dos ativos lateralizados ({range_pct:.0f}%)", now)
            if alert:
                alerts.append(alert)

        avg = market.get("avg_metrics", {})
        rvol = avg.get("rvol_medio", 0)
        if rvol >= ALERT_RVOL_SPIKE:
            alert = self._make_alert("RVOL_SPIKE", f"RVOL medio em {rvol:.1f}x — atividade institucional elevada", now)
            if alert:
                alerts.append(alert)

        volatilidade = avg.get("volatilidade_media", 0)
        prev_vol = None
        if prev_snapshot:
            prev_vol = prev_snapshot.get("market", {}).get("avg_metrics", {}).get("volatilidade_media", 0)
            if prev_vol and abs(volatilidade - prev_vol) >= ALERT_VOLATILITY_SPIKE:
                direction = "aumento" if volatilidade > prev_vol else "queda"
                alert = self._make_alert("VOLATILITY_SHIFT", f"{direction.capitalize()} de volatilidade: {prev_vol:.2f} → {volatilidade:.2f}", now)
                if alert:
                    alerts.append(alert)

        prev_consensus = None
        if prev_snapshot:
            prev_consensus = prev_snapshot.get("market", {}).get("avg_metrics", {}).get("consensus_medio", 0)
            consensus = avg.get("consensus_medio", 0)
            if prev_consensus and (consensus - prev_consensus) >= ALERT_CONSENSUS_SURGE:
                alert = self._make_alert("CONSENSUS_SURGE", f"Consensus medio subiu: {prev_consensus:.2f} → {consensus:.2f}", now)
                if alert:
                    alerts.append(alert)

        elite_count = sum(
            1 for opp in snapshot.get("market", {}).get("opportunities", [])
            if opp.get("quality", 0) >= 0.85
        )
        if elite_count >= ALERT_ELITE_COUNT:
            alert = self._make_alert("ELITE_SURGE", f"{elite_count} sinais ELITE detectados", now)
            if alert:
                alerts.append(alert)

        return alerts

    def _make_alert(self, alert_type: str, message: str, now: float) -> Optional[Dict]:
        last = self._cooldowns.get(alert_type, 0)
        if now - last < MID_ALERT_COOLDOWN_SECONDS:
            return None
        self._cooldowns[alert_type] = now
        return {"type": alert_type, "message": message, "timestamp": str(now)}
