from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

def _get(data: Dict[str, Any], *keys: str, default: Any = 0.0) -> Any:
    for k in keys:
        if k in data:
            val = data[k]
            if val is not None:
                return val
    return default

def _scale(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        f = float(val)
        if 0.0 < f <= 1.0:
            return f * 100.0
        return f
    except (ValueError, TypeError):
        return 0.0

def _pct_change(old_val: float, new_val: float) -> float:
    if old_val == 0.0:
        return 0.0
    return abs(new_val - old_val) / abs(old_val) * 100.0

def _contrib(diff: float, threshold: float, weight: float, max_contrib: float) -> float:
    if abs(diff) < threshold:
        return 0.0
    ratio = abs(diff) / threshold
    return min(max_contrib, weight * ratio)

@dataclass
class OperationalImpact:
    impact_score: int = 0
    update_type: Optional[str] = None
    is_send: bool = False

class UpdateEngine:
    """RFC V18.5.2 — Motor de Impacto Operacional para filtrar atualizações."""

    @staticmethod
    def calculate_impact_score(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> OperationalImpact:
        old_dir = str(_get(old_data, "direction", default="")).upper()
        new_dir = str(_get(new_data, "direction", default="")).upper()

        old_entry = float(_get(old_data, "entry", "entry_price", default=0.0))
        new_entry = float(_get(new_data, "entry", "entry_price", default=0.0))

        old_stop = float(_get(old_data, "stop", "stop_loss", default=0.0))
        new_stop = float(_get(new_data, "stop", "stop_loss", default=0.0))

        old_tp = float(_get(old_data, "take_profit", "take_profit_1", default=0.0))
        new_tp = float(_get(new_data, "take_profit", "take_profit_1", default=0.0))

        old_rr = float(_get(old_data, "risk_reward", default=0.0))
        new_rr = float(_get(new_data, "risk_reward", default=0.0))

        old_score = _scale(_get(old_data, "score", "overall_score_value", default=0.0))
        new_score = _scale(_get(new_data, "score", "overall_score_value", default=0.0))

        old_quality = _scale(_get(old_data, "quality", "quality_score", default=0.0))
        new_quality = _scale(_get(new_data, "quality", "quality_score", default=0.0))

        old_prob_data = old_data.get("probability", 0.0)
        old_prob_val = old_prob_data.get("probability", 0.0) if isinstance(old_prob_data, dict) else old_prob_data
        new_prob_data = new_data.get("probability", 0.0)
        new_prob_val = new_prob_data.get("probability", 0.0) if isinstance(new_prob_data, dict) else new_prob_data
        old_prob = _scale(old_prob_val)
        new_prob = _scale(new_prob_val)

        old_confidence = _scale(_get(old_data, "conviction", "confidence", default=0.0))
        new_confidence = _scale(_get(new_data, "conviction", "confidence", default=0.0))

        old_consensus = _scale(_get(old_data, "consensus", "consensus_score", default=0.0))
        new_consensus = _scale(_get(new_data, "consensus", "consensus_score", default=0.0))

        old_confluence = _scale(_get(old_data, "confluence_score", default=0.0))
        new_confluence = _scale(_get(new_data, "confluence_score", default=0.0))

        old_liquidity = _scale(_get(old_data, "liquidity_score", default=0.0))
        new_liquidity = _scale(_get(new_data, "liquidity_score", default=0.0))

        old_flow = _scale(_get(old_data, "flow_score", default=0.0))
        new_flow = _scale(_get(new_data, "flow_score", default=0.0))

        old_structure = _scale(_get(old_data, "structure_score", "structure", default=0.0))
        new_structure = _scale(_get(new_data, "structure_score", "structure", default=0.0))

        old_risk = _scale(_get(old_data, "risk_score", "risk", default=0.0))
        new_risk = _scale(_get(new_data, "risk_score", "risk", default=0.0))

        old_trend = str(_get(old_data, "trend", default="")).lower()
        new_trend = str(_get(new_data, "trend", default="")).lower()

        old_kalman = str(_get(old_data, "kalman_direction", default="")).upper()
        new_kalman = str(_get(new_data, "kalman_direction", default="")).upper()

        conviction_map = {"Muito Alta": 5, "Alta": 4, "Moderada": 3, "Baixa": 2, "Muito Baixa": 1}
        old_conv = conviction_map.get(_get(old_data, "conviction_level", default=""), 0)
        new_conv = conviction_map.get(_get(new_data, "conviction_level", default=""), 0)

        status = str(new_data.get("status", new_data.get("message_type", ""))).lower()
        is_cancelled = status in ("cancelled", "cancelado", "closed", "encerrado")

        score_diff = abs(new_score - old_score)
        quality_diff = abs(new_quality - old_quality)
        prob_diff = abs(new_prob - old_prob)
        confidence_diff = abs(new_confidence - old_confidence)
        consensus_diff = abs(new_consensus - old_consensus)
        confluence_diff = abs(new_confluence - old_confluence)
        liquidity_diff = abs(new_liquidity - old_liquidity)
        flow_diff = abs(new_flow - old_flow)
        structure_diff = abs(new_structure - old_structure)
        risk_diff = abs(new_risk - old_risk)
        rr_diff = abs(new_rr - old_rr)
        entry_pct = _pct_change(old_entry, new_entry)
        stop_pct = _pct_change(old_stop, new_stop)
        tp_pct = _pct_change(old_tp, new_tp)

        is_direction_change = bool(old_dir and new_dir and old_dir != new_dir)
        is_trend_change = bool(old_trend and new_trend and old_trend != new_trend)
        is_kalman_change = bool(old_kalman and new_kalman and old_kalman != new_kalman)
        is_conviction_change = bool(old_conv > 0 and new_conv > 0 and old_conv != new_conv)

        # --- Calculate Operational Impact Score ---
        impact: float = 0.0

        impact += _contrib(score_diff, 2.0, 20.0, 60.0)
        impact += _contrib(quality_diff, 2.0, 12.0, 36.0)
        impact += _contrib(prob_diff, 3.0, 12.0, 36.0)
        impact += _contrib(confidence_diff, 3.0, 12.0, 36.0)
        impact += _contrib(consensus_diff, 5.0, 8.0, 24.0)
        impact += _contrib(confluence_diff, 5.0, 8.0, 24.0)
        impact += _contrib(liquidity_diff, 10.0, 5.0, 15.0)
        impact += _contrib(flow_diff, 10.0, 5.0, 15.0)
        impact += _contrib(structure_diff, 5.0, 8.0, 24.0)
        impact += _contrib(risk_diff, 5.0, 8.0, 24.0)
        impact += _contrib(rr_diff, 0.20, 15.0, 45.0)
        impact += _contrib(tp_pct, 2.0, 8.0, 24.0)
        impact += _contrib(stop_pct, 2.0, 10.0, 30.0)
        impact += _contrib(entry_pct, 1.0, 8.0, 24.0)

        if is_trend_change:
            impact += 40.0
        if is_kalman_change:
            impact += 40.0
        if is_conviction_change:
            impact += 30.0

        impact = min(100.0, impact)
        impact_int = int(round(impact))

        # --- Determine label and send decision ---
        label: Optional[str] = None
        is_send: bool = False

        # Priority 1: Direction reversal (always send, impact 100)
        if is_direction_change:
            label = "🔄 REVERSÃO DE TENDÊNCIA"
            impact_int = max(impact_int, 100)

        # Priority 2: Setup cancelled/closed
        elif is_cancelled:
            label = "❌ SINAL CANCELADO"
            impact_int = max(impact_int, 80)

        # Priority 3: Trend / Kalman change (always send)
        elif is_trend_change:
            label = "🔄 REVERSÃO DE TENDÊNCIA"
            impact_int = max(impact_int, 80)

        elif is_kalman_change:
            label = "🔄 REVERSÃO DE TENDÊNCIA"
            impact_int = max(impact_int, 80)

        # Priority 4: Stop change >= 2% (always send)
        elif stop_pct >= 2.0:
            label = "🛡 STOP AJUSTADO"
            impact_int = max(impact_int, 80)

        # Priority 5: TP change >= 2% (always send)
        elif tp_pct >= 2.0:
            label = "🎯 TAKE PROFIT ATUALIZADO"
            impact_int = max(impact_int, 80)

        # Priority 6: Entry change >= 1% (always send)
        elif entry_pct >= 1.0:
            label = "🎯 ENTRADA AJUSTADA"
            impact_int = max(impact_int, 80)

        # Priority 7: Conviction change (always send)
        elif is_conviction_change:
            label = "📈 SETUP FORTALECIDO" if new_conv > old_conv else "📉 SETUP ENFRAQUECIDO"
            impact_int = max(impact_int, 80)

        # Priority 8+: Regular changes gated by impact score >= 50
        elif impact_int >= 50:
            if score_diff >= 2.0:
                label = "📈 SETUP FORTALECIDO" if new_score > old_score else "📉 SETUP ENFRAQUECIDO"
            elif quality_diff >= 2.0:
                label = "📈 SETUP FORTALECIDO" if new_quality > old_quality else "📉 SETUP ENFRAQUECIDO"
            elif prob_diff >= 3.0:
                label = "📈 SETUP FORTALECIDO" if new_prob > old_prob else "📉 SETUP ENFRAQUECIDO"
            elif confidence_diff >= 3.0:
                label = "📈 SETUP FORTALECIDO" if new_confidence > old_confidence else "📉 SETUP ENFRAQUECIDO"
            elif consensus_diff >= 5.0:
                label = "📈 SETUP FORTALECIDO" if new_consensus > old_consensus else "📉 SETUP ENFRAQUECIDO"
            elif confluence_diff >= 5.0:
                label = "📈 SETUP FORTALECIDO" if new_confluence > old_confluence else "📉 SETUP ENFRAQUECIDO"
            elif liquidity_diff >= 10.0:
                label = "📈 SETUP FORTALECIDO" if new_liquidity > old_liquidity else "📉 SETUP ENFRAQUECIDO"
            elif flow_diff >= 10.0:
                label = "📈 SETUP FORTALECIDO" if new_flow > old_flow else "📉 SETUP ENFRAQUECIDO"
            elif structure_diff >= 5.0:
                label = "📈 SETUP FORTALECIDO" if new_structure > old_structure else "📉 SETUP ENFRAQUECIDO"
            elif risk_diff >= 5.0:
                label = "📈 SETUP FORTALECIDO" if new_risk > old_risk else "📉 SETUP ENFRAQUECIDO"
            elif rr_diff >= 0.20:
                label = "🎯 RR ATUALIZADO"
            elif stop_pct >= 1.0:
                label = "🛡 STOP AJUSTADO"
            elif tp_pct >= 1.0:
                label = "🎯 TAKE PROFIT ATUALIZADO"
            elif entry_pct >= 0.5:
                label = "🎯 ENTRADA AJUSTADA"

        # Apply send decision
        if impact_int >= 50:
            is_send = True

        return OperationalImpact(
            impact_score=impact_int,
            update_type=label,
            is_send=is_send,
        )

    @staticmethod
    def get_update_type_and_score(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Tuple[Optional[str], int]:
        impact = UpdateEngine.calculate_impact_score(old_data, new_data)
        return impact.update_type, impact.impact_score

    @staticmethod
    def get_update_type(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Optional[str]:
        impact = UpdateEngine.calculate_impact_score(old_data, new_data)
        return impact.update_type if impact.is_send else None
