"""
Signal Explainer — Diagnostico detalhado do sinal.

Produz uma explicacao clara contendo:
- Probabilidade historica
- Scores individuais
- Motivos de aprovacao/rejeicao
- Riscos detectados
"""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from ENGINE.scanner.scanner_types import SignalClassification, SignalDirection, PatternType
from ENGINE.decision.signal_decision import SignalDecision
from ENGINE.probability.probability_engine import ProbabilityEngine, ProbabilityResult

log = logging.getLogger(__name__)


@dataclass
class SignalDiagnosis:
    probability: float = 0.0
    conviction: float = 0.0
    institutional: float = 0.0
    flow: float = 0.0
    timing: float = 0.0
    liquidity: float = 0.0
    entry_zone: float = 0.0
    risk_reward: float = 0.0
    regime: str = ""
    approval_reasons: List[str] = field(default_factory=list)
    detected_risks: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    consenso: str = ""
    classification: str = ""
    strong_points: List[str] = field(default_factory=list)
    weak_points: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probability": self.probability,
            "conviction": self.conviction,
            "institutional": self.institutional,
            "flow": self.flow,
            "timing": self.timing,
            "liquidity": self.liquidity,
            "entry_zone": self.entry_zone,
            "risk_reward": self.risk_reward,
            "regime": self.regime,
            "approval_reasons": self.approval_reasons,
            "detected_risks": self.detected_risks,
            "rejection_reasons": self.rejection_reasons,
            "consenso": self.consenso,
            "classification": self.classification,
            "strong_points": self.strong_points,
            "weak_points": self.weak_points,
        }


from ENGINE.common.score_normalizer import scale_1_to_100

class SignalExplainer:

    def __init__(self, prob_engine: Optional[ProbabilityEngine] = None):
        self._prob_engine = prob_engine or ProbabilityEngine()

    def explain(self, sd: SignalDecision) -> SignalDiagnosis:
        diag = SignalDiagnosis()
        diag.probability = self._prob_engine.adjusted_win_probability(sd)
        diag.conviction = round(scale_1_to_100(getattr(sd, 'quality_score', sd.quality)), 1)
        diag.institutional = round(scale_1_to_100(sd.institutional_score), 1)
        diag.flow = round(scale_1_to_100(getattr(sd, 'institutional_score', 0)), 1)
        diag.timing = round(scale_1_to_100(getattr(sd, 'quality', 0)), 1)
        diag.liquidity = round(scale_1_to_100(sd.liquidity_score), 1)
        diag.entry_zone = round(scale_1_to_100(sd.entry_score), 1)
        diag.risk_reward = round(sd.risk_reward, 2)
        diag.regime = sd.trend or "desconhecido"
        diag.consenso = self._describe_consensus(sd)
        diag.classification = getattr(sd, 'classification_label', 'reprovado')

        if sd.approved:
            diag.approval_reasons = self._build_approval_reasons(sd)
            diag.strong_points = self._build_strong_points(sd)
            diag.detected_risks = self._build_risks(sd)
            diag.weak_points = self._build_weak_points(sd)
        else:
            diag.rejection_reasons = self._build_rejection_reasons(sd)
            diag.weak_points = self._build_weak_points(sd)

        return diag

    def _describe_consensus(self, sd: SignalDecision) -> str:
        consensus = sd.consensus
        if consensus >= 0.80:
            return "Forte"
        if consensus >= 0.65:
            return "Moderado"
        if consensus >= 0.50:
            return "Fraco"
        return "Sem consenso"

    def _build_approval_reasons(self, sd: SignalDecision) -> List[str]:
        reasons = []

        if sd.trend_ok:
            reasons.append(f"Tendencia alinhada ({sd.trend or 'desconhecida'})")
        if getattr(sd, 'flow_ok', False):
            reasons.append("Fluxo institucional favoravel")
        if sd.entry_zone_ok:
            reasons.append("Entrada em zona institucional")
        if getattr(sd, 'rvol_ok', False):
            reasons.append("Volume acima da media")
        if sd.consensus >= 0.65:
            reasons.append("Consenso positivo")
        if getattr(sd, 'rr_ok', False) and sd.risk_reward >= 2.0:
            reasons.append(f"Risk/Reward {sd.risk_reward:.1f}")

        if sd.bos > 0:
            reasons.append("BOS confirmado")
        if sd.choch > 0:
            reasons.append("CHoCH confirmado")
        if sd.liquidity_sweep > 0:
            reasons.append("Liquidity Sweep")
        if sd.fvg > 0:
            reasons.append("FVG identificado")

        if not reasons:
            reasons.append(f"Score geral: {sd.quality:.2f}")

        return reasons[:5]

    def _build_strong_points(self, sd: SignalDecision) -> List[str]:
        points = []
        if sd.institutional_score >= 0.75:
            points.append(f"Score institucional alto ({sd.institutional_score:.2f})")
        if sd.structural_score >= 0.70:
            points.append(f"Estrutura forte ({sd.structural_score:.2f})")
        if getattr(sd, 'flow_ok', False):
            points.append("Fluxo confirma movimento")
        if getattr(sd, 'timing_ok', False):
            points.append("Timing favoravel")
        if sd.entry_zone_ok:
            points.append("Entrada em zona de valor")
        if sd.risk_reward >= 2.5:
            points.append(f"RR excelente ({sd.risk_reward:.1f})")
        return points[:3]

    def _build_weak_points(self, sd: SignalDecision) -> List[str]:
        points = []

        if sd.quality < 0.65:
            points.append(f"Score geral baixo ({sd.quality:.2f})")
        if sd.institutional_score < 0.60:
            points.append(f"Score institucional baixo ({sd.institutional_score:.2f})")
        if sd.liquidity_score < 0.50:
            points.append(f"Liquidez reduzida ({sd.liquidity_score:.2f})")
        if not getattr(sd, 'flow_ok', False) and sd.approved:
            points.append("Fluxo nao confirmou")
        if not getattr(sd, 'timing_ok', False) and sd.approved:
            points.append("Timing nao ideal")
        if not sd.entry_zone_ok and sd.approved:
            points.append("Entrada fora de zona ideal")
        if sd.risk_reward < 2.0 and sd.risk_reward > 0:
            points.append(f"RR baixo ({sd.risk_reward:.1f})")

        if not points and not sd.approved:
            points.append("Multiplos filtros reprovaram")

        return points[:3]

    def _build_risks(self, sd: SignalDecision) -> List[str]:
        risks = []

        if sd.risk_reward < 2.5:
            risks.append(f"RR {sd.risk_reward:.1f} — abaixo do ideal")

        kalman_dir = getattr(sd, 'kalman_direction', 'UNKNOWN')
        if kalman_dir == "REVERSAL":
            risks.append("Kalman indicando reversao — cautela")
        elif kalman_dir == "SIDE":
            risks.append("Kalman lateral — ausencia de tendencia no curto prazo")

        kalman_conf = getattr(sd, 'kalman_confidence', 0.0)
        if kalman_conf < 0.4:
            risks.append("Baixa confianca do filtro Kalman")

        if sd.liquidity_score < 0.60:
            risks.append("Liquidez reduzida — possivel derrapagem")

        return risks[:3]

    def _build_rejection_reasons(self, sd: SignalDecision) -> List[str]:
        reasons = [sd.reject_reason] if sd.reject_reason else []
        if not reasons:
            reasons.append("Nao atendeu criterios institucionais minimos")
        return reasons[:3]
