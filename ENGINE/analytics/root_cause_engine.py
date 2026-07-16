"""RFC V26.X — Root Cause Diagnostic Engine (RCDE).

O diagnostico do QuantOS nao deve apenas informar que um gate reprovou —
deve investigar POR QUE, com hipoteses ranqueadas por confianca e
evidencias concretas.

Reuso deliberado (nada recalculado do zero):
- GATE_ORDER / mapeamento gate -> campo *_ok: mesmo usado em
  ENGINE/diagnostic/advanced_report.py, para nomes de gate consistentes
  em todo o sistema.
- Estatisticas por gate (media/P75/P90/threshold): lidas do
  GateCalibrationEngine.last_data quando disponivel — evita duplicar o
  calculo de percentis ja implementado na RFC V25.X.2.
- Condicao de mercado (ADX medio, regime dominante, silent_drop_pct):
  os mesmos 3 agregados triviais ja usados no Fast Diagnostic (RFC
  V25.5) — nenhum indicador e recalculado.

Este modulo so decide COMO interpretar esses dados: quando investigar,
quais hipoteses ponderar, e como pontuar a saude de cada gate.
"""
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ENGINE.diagnostic.advanced_report import GATE_ORDER

WINDOW = 200                       # historico maximo por gate (execucoes)
CYCLE_RATE_HISTORY = 10            # ciclos recentes guardados p/ deteccao de streak
# RFC V26.X pede "aprovacao<5% OU rejeicao>95%" como gatilho — como
# rejeicao = 100 - aprovacao, as duas condicoes sao matematicamente
# identicas; um unico piso de aprovacao cobre ambas.
INVESTIGATION_APPROVAL_FLOOR = 5.0     # % — abaixo disso, gate em crise
INVESTIGATION_STREAK = 3           # ciclos consecutivos em crise p/ investigar
REGRESSION_DELTA_PCT = 30.0        # queda %, vs media historica, p/ virar regressao
MIN_SAMPLES_FOR_CONFIDENCE = 10    # amostra minima p/ confianca alta na investigacao


@dataclass
class Hypothesis:
    cause: str
    stars: int              # 1-5
    weight: float           # peso relativo, usado no calculo de confianca


@dataclass
class GateInvestigation:
    gate: str
    current_rate: float
    historical_avg: float
    delta: float
    status: str              # "NORMAL" ou "ANORMAL"
    hypotheses: List[Hypothesis] = field(default_factory=list)
    confidence: float = 0.0
    recommended_actions: List[str] = field(default_factory=list)
    suspected_bug: bool = False


@dataclass
class RegressionAlert:
    gate: str
    delta_pct: float
    current_rate: float
    historical_avg: float
    suspected_since: str = ""


@dataclass
class RCDEReport:
    timestamp: str
    overall_health_score: float
    health_scores: Dict[str, float] = field(default_factory=dict)
    investigations: List[GateInvestigation] = field(default_factory=list)
    regressions: List[RegressionAlert] = field(default_factory=list)
    total_analyzed: int = 0
    total_approved: int = 0
    duplicates_blocked: int = 0


_GENERIC_ACTIONS: Dict[str, List[str]] = {
    "RVOL": ["Validar calculo de RVOL", "Comparar volume atual vs media historica",
             "Verificar sincronizacao de candles da API", "Comparar threshold com historico"],
    "ADX": ["Validar calculo ADX", "Comparar ADX atual vs TradingView",
            "Verificar periodo utilizado", "Verificar smoothing", "Validar ATR interno",
            "Validar dados OHLC", "Comparar threshold com historico"],
    "Estrutura (BOS/CHoCH)": ["Validar deteccao de BOS/CHoCH", "Verificar dados de estrutura",
                              "Comparar threshold com historico"],
    "Entry Zone": ["Validar calculo de Entry Zone", "Verificar distancia ao preco atual",
                   "Comparar threshold com historico"],
    "Quality": ["Validar componentes do Quality Score", "Verificar ceilings de normalizacao",
                "Comparar threshold com historico"],
    "Consensus": ["Revisar concordancia multi-timeframe", "Validar pesos por timeframe",
                  "Comparar threshold com historico"],
    "Confidence": ["Validar calculo de Confidence Score", "Comparar threshold com historico"],
    "Kalman": ["Validar filtro de Kalman", "Verificar estado de tendencia (trend_state)"],
    "Risk/RR": ["Validar calculo de RR", "Verificar SL/TP calculados"],
}


class GateOutcomeTracker:
    """Historico de resultados (aprovado/reprovado) por gate, em memoria."""

    def __init__(self, window: int = WINDOW):
        self._window = window
        self._history: Dict[str, deque] = {g: deque(maxlen=window) for g, _ in GATE_ORDER}
        self._cycle_rate_history: Dict[str, deque] = {
            g: deque(maxlen=CYCLE_RATE_HISTORY) for g, _ in GATE_ORDER
        }

    def record_cycle(self, decisions: List[Dict[str, Any]]) -> Dict[str, float]:
        """Registra os resultados *_ok de todas as decisions do ciclo (
        aprovadas E rejeitadas — mesma lista de dicts que
        report.decisions/SignalDecision.to_dict() ja populam) e retorna a
        taxa de aprovacao do CICLO ATUAL por gate (usada para deteccao de
        streak)."""
        cycle_outcomes: Dict[str, List[bool]] = {g: [] for g, _ in GATE_ORDER}
        for sd in decisions:
            for gate, gate_field in GATE_ORDER:
                ok = sd.get(gate_field)
                if ok is None:
                    continue  # gate nunca avaliado neste sinal (early exit em gate anterior)
                self._history[gate].append(bool(ok))
                cycle_outcomes[gate].append(bool(ok))

        cycle_rates: Dict[str, float] = {}
        for gate, outcomes in cycle_outcomes.items():
            if not outcomes:
                continue
            rate = round(sum(outcomes) / len(outcomes) * 100, 1)
            self._cycle_rate_history[gate].append(rate)
            cycle_rates[gate] = rate
        return cycle_rates

    def historical_avg(self, gate: str) -> Optional[float]:
        hist = self._history.get(gate)
        if not hist:
            return None
        return round(sum(hist) / len(hist) * 100, 1)

    def sample_count(self, gate: str) -> int:
        return len(self._history.get(gate, []))

    def in_crisis_streak(self, gate: str) -> bool:
        """True se as ultimas INVESTIGATION_STREAK taxas de ciclo do gate
        estiverem todas em crise. "aprovacao<5%" e "rejeicao>95%" sao a
        mesma condicao (rate = taxa de aprovacao; rejeicao = 100 - rate),
        entao basta checar o piso de aprovacao."""
        rates = self._cycle_rate_history.get(gate)
        if not rates or len(rates) < INVESTIGATION_STREAK:
            return False
        recent = list(rates)[-INVESTIGATION_STREAK:]
        return all(r <= INVESTIGATION_APPROVAL_FLOOR for r in recent)

    def last_cycle_rate(self, gate: str) -> Optional[float]:
        rates = self._cycle_rate_history.get(gate)
        return rates[-1] if rates else None


def _build_hypotheses(
    gate: str,
    delta: float,
    calibration_stats: Optional[Dict[str, Any]],
    regime_mode: str,
    silent_drop_pct: float,
) -> List[Hypothesis]:
    """Pondera as hipoteses genericas com evidencia real disponivel:
    gap threshold-vs-observado (GateCalibrationEngine), regime de
    mercado (Fast Diagnostic) e candles perdidos (silent drops)."""
    causes = {
        "threshold": (f"Threshold excessivamente alto para o gate {gate}", 5.0),
        "bug": (f"Bug no calculo de {gate}", 4.0),
        "dados": ("Dados OHLC/indicadores incompletos", 3.0),
        "mercado": (f"Condicao de mercado atipica ({regime_mode or 'desconhecido'})", 2.0),
        "api": ("API retornando candles invalidos ou atrasados", 1.0),
    }

    scores = {k: base for k, (_, base) in causes.items()}

    # Evidencia 1: gap entre o valor tipico observado (P75) e o threshold —
    # gap grande sugere threshold mal calibrado, nao bug.
    if calibration_stats:
        gap_pct = calibration_stats.get("gap_pct")
        if gap_pct is not None:
            if gap_pct > 0.15:
                scores["threshold"] += 2.0
                scores["bug"] -= 0.5
            elif gap_pct < 0.02:
                # observado praticamente colado no threshold — pode ser
                # calculo correto batendo num limite legitimo, reduz
                # suspeita de bug e de threshold mal calibrado.
                scores["bug"] -= 1.0
                scores["threshold"] -= 1.0

    # Evidencia 2: mercado lateral/fraco pesa mais para ADX/RVOL.
    if regime_mode == "Lateral" and gate in ("ADX", "RVOL"):
        scores["mercado"] += 1.5
    else:
        scores["mercado"] -= 0.5

    # Evidencia 3: candles perdidos indicam problema de dados/API real.
    if silent_drop_pct >= 15.0:
        scores["dados"] += 2.0
        scores["api"] += 1.5
    else:
        scores["dados"] -= 0.5
        scores["api"] -= 0.5

    ranked = sorted(causes.keys(), key=lambda k: -scores[k])
    hypotheses = []
    for key in ranked:
        label, _ = causes[key]
        stars = max(1, min(5, round(scores[key])))
        hypotheses.append(Hypothesis(cause=label, stars=stars, weight=scores[key]))
    hypotheses.sort(key=lambda h: -h.stars)
    return hypotheses


def _confidence_from_sample(sample_count: int, delta: float) -> float:
    """Confianca cresce com o tamanho da amostra e com a magnitude do
    desvio — poucos dados nunca geram confianca alta, mesmo com desvio
    grande (evita conclusao precipitada com amostra pequena)."""
    sample_factor = min(1.0, sample_count / (MIN_SAMPLES_FOR_CONFIDENCE * 3))
    magnitude_factor = min(1.0, abs(delta) / 60.0)
    confidence = 40.0 + 55.0 * sample_factor * (0.4 + 0.6 * magnitude_factor)
    return round(min(99.0, confidence), 0)


class RootCauseDiagnosticEngine:
    """RFC V26.X: investiga automaticamente gates em crise, calcula saude
    por modulo e detecta regressoes — executado ao final de cada ciclo."""

    def __init__(self):
        self._tracker = GateOutcomeTracker()
        self._last_report: Optional[RCDEReport] = None

    def record_cycle(self, decisions: List[Dict[str, Any]]) -> Dict[str, float]:
        return self._tracker.record_cycle(decisions)

    def investigate(
        self,
        total_analyzed: int,
        total_approved: int,
        avg_adx: float = 0.0,
        regime_mode: str = "",
        silent_drop_pct: float = 0.0,
        calibration_data: Optional[Dict[str, Any]] = None,
        duplicates_blocked: int = 0,
    ) -> RCDEReport:
        health_scores: Dict[str, float] = {}
        investigations: List[GateInvestigation] = []
        regressions: List[RegressionAlert] = []

        stats_by_gate = (calibration_data or {}).get("stats_by_gate", {})

        for gate, _field in GATE_ORDER:
            current = self._tracker.last_cycle_rate(gate)
            avg = self._tracker.historical_avg(gate)
            if current is None:
                continue

            health_scores[gate] = round(current, 0)

            if avg is None:
                continue
            delta = round(current - avg, 1)

            calib = stats_by_gate.get(gate) or stats_by_gate.get(_field)
            calib_ctx = None
            if calib and calib.get("threshold", 0) > 0:
                gap = calib["threshold"] - calib.get("p75", 0)
                calib_ctx = {"gap_pct": gap / max(calib["threshold"], 0.001)}

            if self._tracker.in_crisis_streak(gate):
                hyps = _build_hypotheses(gate, delta, calib_ctx, regime_mode, silent_drop_pct)
                sample = self._tracker.sample_count(gate)
                confidence = _confidence_from_sample(sample, delta)
                top = hyps[0] if hyps else None
                investigations.append(GateInvestigation(
                    gate=gate,
                    current_rate=current,
                    historical_avg=avg,
                    delta=delta,
                    status="ANORMAL",
                    hypotheses=hyps,
                    confidence=confidence,
                    recommended_actions=_GENERIC_ACTIONS.get(gate, ["Comparar threshold com historico"]),
                    suspected_bug=bool(top and top.stars >= 4 and "Bug" in top.cause),
                ))

            if avg > 0 and delta <= -REGRESSION_DELTA_PCT:
                regressions.append(RegressionAlert(
                    gate=gate, delta_pct=delta, current_rate=current,
                    historical_avg=avg,
                    suspected_since=_recent_changelog_hint(),
                ))

        overall = round(sum(health_scores.values()) / len(health_scores), 0) if health_scores else 100.0

        report = RCDEReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            overall_health_score=overall,
            health_scores=health_scores,
            investigations=investigations,
            regressions=regressions,
            total_analyzed=total_analyzed,
            total_approved=total_approved,
            duplicates_blocked=duplicates_blocked,
        )
        self._last_report = report
        return report

    @property
    def last_report(self) -> Optional[RCDEReport]:
        return self._last_report


def _recent_changelog_hint(path: Optional[str] = None) -> str:
    """Le apenas o titulo da entrada mais recente do CHANGELOG.md como
    pista de correlacao — nao e git blame preciso, e uma correlacao
    temporal para orientar investigacao manual."""
    try:
        base = path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "CHANGELOG.md",
        )
        with open(base, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("## ["):
                    return line.lstrip("#").strip()
    except Exception:
        pass
    return "desconhecido — ver CHANGELOG.md"


# ---------------------------------------------------------------------------
# Formatacao
# ---------------------------------------------------------------------------

def format_rcde_investigation(inv: GateInvestigation) -> str:
    lines = [
        "━" * 26,
        "ROOT CAUSE ANALYSIS",
        "",
        f"Gate afetado:\n{inv.gate}",
        "",
        f"Taxa atual:\n{inv.current_rate:.0f}%",
        "",
        f"Media historica:\n{inv.historical_avg:.0f}%",
        "",
        f"Diferenca:\n{inv.delta:+.0f}%",
        "",
        f"Status:\n{inv.status}",
        "",
        "Possiveis causas",
        "",
    ]
    for h in inv.hypotheses:
        stars = "★" * h.stars + "☆" * (5 - h.stars)
        lines.append(f"{stars} {h.cause}")
    lines.append("")
    lines.append(f"Confianca:\n{inv.confidence:.0f}%")
    lines.append("")
    if inv.suspected_bug:
        lines.append("\U0001f6a8 SUSPEITA DE BUG")
        lines.append("")
    lines.append("ACAO RECOMENDADA")
    lines.append("")
    for action in inv.recommended_actions:
        lines.append(f"✔ {action}")
    lines.append("━" * 26)
    return "\n".join(lines)


def format_rcde_report(report: RCDEReport) -> str:
    lines = [
        "=" * 50,
        "ROOT CAUSE DIAGNOSTIC ENGINE",
        "=" * 50,
        f"Analisados: {report.total_analyzed} | Aprovados: {report.total_approved} | "
        f"Duplicados bloqueados: {report.duplicates_blocked}",
        "",
        "HEALTH SCORE",
    ]
    for gate, _ in GATE_ORDER:
        score = report.health_scores.get(gate)
        if score is None:
            continue
        lines.append(f"  {gate:.<20}{score:.0f}")
    lines.append(f"  {'Sistema Geral':.<20}{report.overall_health_score:.0f}")
    lines.append("")

    if report.regressions:
        lines.append("-" * 50)
        lines.append("REGRESSAO DETECTADA")
        lines.append("-" * 50)
        for r in report.regressions:
            lines.append(
                f"  {r.gate}: {r.historical_avg:.0f}% -> {r.current_rate:.0f}% "
                f"({r.delta_pct:+.0f}pp)"
            )
            lines.append(f"    Possivel origem: {r.suspected_since}")
        lines.append("")

    if report.investigations:
        lines.append("-" * 50)
        lines.append("INVESTIGACOES ATIVAS")
        lines.append("-" * 50)
        for inv in report.investigations:
            lines.append(format_rcde_investigation(inv))
            lines.append("")
    else:
        lines.append("Nenhum gate em investigacao neste ciclo.")

    lines.append("=" * 50)
    return "\n".join(lines)


def format_rcde_telegram(report: RCDEReport) -> str:
    """Versao compacta para o diagnostico unico diario do Telegram —
    mesma informacao de format_rcde_report(), sem os separadores de log."""
    lines = [
        "\U0001fa7a *QuantOS — Diagnostico Diario*",
        "",
        f"Saude geral: {report.overall_health_score:.0f}/100",
        f"Analisados: {report.total_analyzed} | Aprovados: {report.total_approved} | "
        f"Duplicados bloqueados: {report.duplicates_blocked}",
        "",
        "*Saude por gate:*",
    ]
    for gate, _ in GATE_ORDER:
        score = report.health_scores.get(gate)
        if score is None:
            continue
        marker = "\U0001f7e2" if score >= 70 else "\U0001f7e1" if score >= 30 else "\U0001f534"
        lines.append(f"  {marker} {gate}: {score:.0f}")

    if report.regressions:
        lines.append("")
        lines.append("⚠️ *Regressoes detectadas:*")
        for r in report.regressions:
            lines.append(
                f"  {r.gate}: {r.historical_avg:.0f}% -> {r.current_rate:.0f}% "
                f"({r.delta_pct:+.0f}pp)"
            )
            lines.append(f"    Possivel origem: {r.suspected_since}")

    if report.investigations:
        lines.append("")
        lines.append("\U0001f50e *Investigacoes ativas:*")
        for inv in report.investigations:
            lines.append(f"  *{inv.gate}* — {inv.current_rate:.0f}% (media {inv.historical_avg:.0f}%)")
            if inv.hypotheses:
                top = inv.hypotheses[0]
                stars = "★" * top.stars + "☆" * (5 - top.stars)
                lines.append(f"    {stars} {top.cause}")
            if inv.suspected_bug:
                lines.append("    \U0001f6a8 SUSPEITA DE BUG")
            lines.append(f"    Confianca: {inv.confidence:.0f}%")
    else:
        lines.append("")
        lines.append("✅ Nenhum gate em investigacao.")

    return "\n".join(lines)
