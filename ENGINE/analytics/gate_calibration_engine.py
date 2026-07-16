import json
import logging
import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GateObservation:
    timestamp: str = ""
    symbol: str = ""
    timeframe: str = ""
    direction: str = ""
    result: str = ""
    gate: str = ""
    value: float = 0.0
    threshold: float = 0.0
    rejected: bool = False


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


@dataclass
class SimulationResult:
    label: str = ""
    threshold: float = 0.0
    would_pass: int = 0
    would_fail: int = 0
    approval_rate: float = 0.0
    pct_change: float = 0.0
    win_rate_impact: float = 0.0
    profit_factor_impact: float = 0.0
    drawdown_impact: float = 0.0
    expectancy_impact: float = 0.0


@dataclass
class CalibrationRecommendation:
    gate: str = ""
    current_threshold: float = 0.0
    mean_observed: float = 0.0
    p75_observed: float = 0.0
    p90_observed: float = 0.0
    suggested_threshold: float = 0.0
    confidence: float = 0.0
    additional_signals_per_cycle: int = 0
    reason: str = ""
    evidence: str = ""


@dataclass
class MarketDiagnosis:
    condition: str = ""
    severity: str = ""  # low, medium, high
    evidence: str = ""
    suggestion: str = ""


# ---------------------------------------------------------------------------
# Gate calibration engine
# ---------------------------------------------------------------------------

GATES_CONFIGURATION: Dict[str, float] = {
    "RVOL": 0.45,
    "ADX": 20.0,
    "Entry Zone": 0.40,
    "Quality Gate": 0.55,
    "Confianca": 0.65,
    "Consensus": 0.50,
    "Exaustao": 0.0,
    "Fluxo": 0.12,
    "Kalman": 0.0,
    "SMC": 0.28,
    "Liquidez": 0.60,
    "ATR": 0.05,
}

NUMERIC_GATES = {g for g, t in GATES_CONFIGURATION.items() if t > 0}


class GateCalibrationEngine:
    def __init__(self, export_dir: Optional[str] = None,
                 min_samples: int = 500,
                 enabled: bool = True):
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self._export_dir = export_dir or os.path.join(base, "analytics", "calibration")
        self._min_samples = min_samples
        self._enabled = enabled

        self._observations: Dict[str, List[GateObservation]] = defaultdict(list)
        self._cycle_number: int = 0
        self._cycle_start: float = 0.0
        self._total_signals: int = 0
        self._approved_signals: int = 0
        self._rejected_signals: int = 0
        self._last_report: str = ""
        self._last_data: Dict[str, Any] = {}

        self._ensure_dir()

    def _ensure_dir(self):
        try:
            os.makedirs(self._export_dir, exist_ok=True)
        except Exception as e:
            log.warning("GateCalibrationEngine: nao foi possivel criar %s: %s",
                        self._export_dir, e)

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------

    def start_cycle(self, cycle_number: int):
        self._cycle_number = cycle_number
        self._cycle_start = time.time()
        self._total_signals = 0
        self._approved_signals = 0
        self._rejected_signals = 0
        for gate in self._observations:
            self._observations[gate].clear()

    def record_gate_observation(self, gate: str, symbol: str, timeframe: str,
                                 direction: str, value: float, threshold: float,
                                 result: str = "REJECTED"):
        if not self._enabled:
            return
        if gate not in NUMERIC_GATES and threshold <= 0:
            return
        obs = GateObservation(
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            result=result,
            gate=gate,
            value=round(value, 6),
            threshold=threshold,
            rejected=(result == "REJECTED"),
        )
        self._observations[gate].append(obs)

    def record_signal_all_gates(self, symbol: str, timeframe: str, direction: str,
                                 result: str, signal, sd,
                                 kludge: Optional[Dict] = None):
        if not self._enabled:
            return
        self._total_signals += 1
        if result == "APPROVED":
            self._approved_signals += 1
        else:
            self._rejected_signals += 1

        gates = {
            "RVOL": getattr(signal, 'rvol', 0.0) or 0.0,
            "ADX": getattr(signal, 'adx', 0.0) or 0.0,
            "Entry Zone": getattr(sd, 'entry_score', 0.0) or 0.0,
            "Quality Gate": getattr(sd, 'quality', 0.0) or 0.0,
            "Confianca": getattr(sd, 'confidence', 0.0) or 0.0,
            "Consensus": getattr(sd, 'consensus', 0.0) or 0.0,
            "SMC": getattr(signal, 'structure_strength', 0.0) or 0.0,
            "Liquidez": getattr(sd, 'liquidity_score', 0.0) or 0.0,
        }
        if hasattr(signal, 'atr_value') and signal.atr_value:
            gates["ATR"] = signal.atr_value
        flow = getattr(signal, 'scores', None)
        if flow and hasattr(flow, 'flow_score'):
            gates["Fluxo"] = flow.flow_score or 0.0
        kalman_conf = getattr(signal, 'kalman_confidence', 0.0) or 0.0
        if kalman_conf > 0:
            gates["Kalman"] = kalman_conf

        for gate_name, value in gates.items():
            threshold = GATES_CONFIGURATION.get(gate_name, 0.0)
            self.record_gate_observation(
                gate=gate_name, symbol=symbol, timeframe=timeframe,
                direction=direction, value=value, threshold=threshold,
                result=result,
            )

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def _compute_stats(self, values: List[float],
                       threshold: float = 0.0,
                       total_signals: int = 0,
                       rejected_count: int = 0) -> GateStats:
        if not values:
            return GateStats(threshold=threshold)

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        total = sum(sorted_vals)
        mean = total / n
        if n % 2 == 1:
            median = float(sorted_vals[n // 2])
        else:
            median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

        variance = sum((x - mean) ** 2 for x in sorted_vals) / n
        std = math.sqrt(variance)

        def _percentile(p: float) -> float:
            idx = max(0, min(n - 1, int(n * p / 100)))
            return sorted_vals[idx]

        approved = total_signals - rejected_count if total_signals > 0 else 0
        rejection_rate = (rejected_count / max(total_signals, 1)) * 100

        return GateStats(
            total=n,
            approved=approved,
            rejected=rejected_count,
            rejection_rate=round(rejection_rate, 1),
            mean=round(mean, 4),
            median=round(median, 4),
            std=round(std, 4),
            min_val=round(sorted_vals[0], 4),
            max_val=round(sorted_vals[-1], 4),
            p10=round(_percentile(10), 4),
            p25=round(_percentile(25), 4),
            p50=round(median, 4),
            p75=round(_percentile(75), 4),
            p90=round(_percentile(90), 4),
            p95=round(_percentile(95), 4),
            threshold=threshold,
        )

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def _simulate_thresholds(self, gate: str, stats: GateStats,
                              values: List[float]) -> Dict[str, SimulationResult]:
        if not values or stats.threshold <= 0:
            return {}

        base_th = stats.threshold
        scenarios = [
            ("Atual", 0.0),
            ("-5%", -0.05),
            ("-10%", -0.10),
            ("+5%", 0.05),
            ("+10%", 0.10),
        ]

        results = {}
        for label, pct_change in scenarios:
            new_th = round(base_th * (1 + pct_change), 4)
            if new_th <= 0:
                new_th = 0.001

            would_pass = sum(1 for v in values if v >= new_th)
            would_fail = len(values) - would_pass
            approval_rate = (would_pass / max(len(values), 1)) * 100

            win_rate_impact = self._estimate_win_rate_impact(
                gate, pct_change)
            pf_impact = win_rate_impact * 0.6
            dd_impact = abs(pct_change) * 1.5 if pct_change < 0 else abs(pct_change) * 0.5
            exp_impact = win_rate_impact * 0.8

            results[label] = SimulationResult(
                label=label,
                threshold=new_th,
                would_pass=would_pass,
                would_fail=would_fail,
                approval_rate=round(approval_rate, 1),
                pct_change=round(pct_change * 100, 0),
                win_rate_impact=round(win_rate_impact, 1),
                profit_factor_impact=round(pf_impact, 1),
                drawdown_impact=round(dd_impact, 1),
                expectancy_impact=round(exp_impact, 1),
            )
        return results

    def _estimate_win_rate_impact(self, gate: str, pct_change: float) -> float:
        base = {
            "RVOL": 0.3, "ADX": 0.4, "Entry Zone": 0.5,
            "Quality Gate": 0.6, "Confianca": 0.4, "Consensus": 0.5,
            "SMC": 0.3, "Liquidez": 0.2, "ATR": 0.2, "Fluxo": 0.2,
            "Kalman": 0.3, "Exaustao": 0.3,
        }.get(gate, 0.3)
        return round(base * abs(pct_change) * 100, 1)

    # ------------------------------------------------------------------
    # Market diagnosis
    # ------------------------------------------------------------------

    GATE_PRIORITY = [
        "RVOL", "ADX", "Entry Zone", "Quality Gate", "Confianca",
        "Consensus", "Exaustao", "Fluxo", "Kalman", "SMC", "Liquidez", "ATR",
    ]

    def _diagnose_market(self, stats_by_gate: Dict[str, GateStats]
                          ) -> List[MarketDiagnosis]:
        diagnoses = []

        rvol = stats_by_gate.get("RVOL")
        if rvol and rvol.total >= 10:
            if rvol.mean < 0.35 and rvol.p90 < 0.55:
                diagnoses.append(MarketDiagnosis(
                    condition="Mercado com baixo volume",
                    severity="high" if rvol.mean < 0.25 else "medium",
                    evidence=(
                        f"RVOL medio={rvol.mean:.2f} P90={rvol.p90:.2f} "
                        f"threshold={rvol.threshold:.2f}"
                    ),
                    suggestion="Aguardar aumento de volume ou ajustar threshold RVOL"
                ))

        adx = stats_by_gate.get("ADX")
        if adx and adx.total >= 10:
            if adx.mean < 18 and adx.p75 < 20:
                diagnoses.append(MarketDiagnosis(
                    condition="Mercado lateral (tendencia fraca)",
                    severity="medium",
                    evidence=(
                        f"ADX medio={adx.mean:.1f} P75={adx.p75:.1f} "
                        f"threshold={adx.threshold:.1f}"
                    ),
                    suggestion="Considerar estrategia de range ou aguardar tendencia"
                ))
            elif adx.mean > 35:
                diagnoses.append(MarketDiagnosis(
                    condition="Mercado em tendencia forte",
                    severity="low",
                    evidence=f"ADX medio={adx.mean:.1f} > 35",
                    suggestion="Condicao favoravel para estrategias direcionais"
                ))

        cons = stats_by_gate.get("Consensus")
        if cons and cons.total >= 10:
            if cons.mean > 0.65:
                diagnoses.append(MarketDiagnosis(
                    condition="Alto consenso multi-timeframe",
                    severity="low",
                    evidence=f"Consensus medio={cons.mean:.2f} P25={cons.p25:.2f}",
                    suggestion="Sinais com forte concordancia entre timeframes"
                ))

        quality = stats_by_gate.get("Quality Gate")
        if quality and quality.total >= 10:
            if quality.mean < 0.45 and quality.p90 < 0.55:
                diagnoses.append(MarketDiagnosis(
                    condition="Quality Gate excessivamente restritivo",
                    severity="high" if quality.p75 < 0.40 else "medium",
                    evidence=(
                        f"Quality medio={quality.mean:.2f} "
                        f"P75={quality.p75:.2f} P90={quality.p90:.2f} "
                        f"threshold={quality.threshold:.2f}"
                    ),
                    suggestion="Quality Gate pode estar bloqueando sinais viaveis"
                ))

        exaustao = stats_by_gate.get("Exaustao")
        if exaustao and exaustao.total > 0:
            rej_rate = (exaustao.rejected / max(exaustao.total, 1)) * 100
            if rej_rate > 30:
                diagnoses.append(MarketDiagnosis(
                    condition="Exaustao tecnica elevada",
                    severity="medium",
                    evidence=f"Exaustao rejeitando {rej_rate:.0f}% dos sinais",
                    suggestion="Verificar condicoes de sobrecompra/sobrevenda"
                ))

        return diagnoses

    # ------------------------------------------------------------------
    # Recommendations with confidence
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        stats_by_gate: Dict[str, GateStats],
        simulations: Dict[str, Dict[str, SimulationResult]],
        diagnoses: List[MarketDiagnosis],
    ) -> List[CalibrationRecommendation]:

        recs = []
        for gate_name in self.GATE_PRIORITY:
            stats = stats_by_gate.get(gate_name)
            if not stats or stats.total < 10:
                continue
            if stats.threshold <= 0:
                continue

            if stats.rejection_rate < 5:
                continue

            gap = stats.threshold - stats.p75
            gap_pct = gap / max(stats.threshold, 0.001)

            if gap_pct > 0.10:
                suggested = round(stats.p75 * 0.95, 4)
                spread = stats.p90 - stats.p25
                if spread > 0:
                    confidence = min(95.0, max(50.0, 100 - (spread * 100)))
                else:
                    confidence = 50.0

                additional = 0
                gate_sim = simulations.get(gate_name, {})
                for scenario in ["-5%", "-10%"]:
                    sim = gate_sim.get(scenario)
                    if sim and sim.threshold >= suggested:
                        additional = sim.would_pass - stats.approved
                        break

                reason = (
                    f"Mercado apresenta {gate_name} estruturalmente "
                    f"inferior ao threshold configurado"
                )
                evidence = (
                    f"threshold_atual={stats.threshold:.2f} "
                    f"media_observada={stats.mean:.2f} "
                    f"P75={stats.p75:.2f} P90={stats.p90:.2f} "
                    f"gap={gap:.2f} ({gap_pct*100:.0f}%) "
                    f"rejeicoes={stats.rejected}/{stats.total}"
                )

                recs.append(CalibrationRecommendation(
                    gate=gate_name,
                    current_threshold=stats.threshold,
                    mean_observed=round(stats.mean, 4),
                    p75_observed=round(stats.p75, 4),
                    p90_observed=round(stats.p90, 4),
                    suggested_threshold=suggested,
                    confidence=round(confidence, 0),
                    additional_signals_per_cycle=max(0, additional),
                    reason=reason,
                    evidence=evidence,
                ))

        recs.sort(key=lambda r: -r.confidence)
        return recs

    # ------------------------------------------------------------------
    # Cycle end
    # ------------------------------------------------------------------

    def end_cycle(self, force: bool = False) -> Optional[str]:
        if not self._enabled:
            return None

        total = sum(len(v) for v in self._observations.values())
        if total < self._min_samples and not force:
            log.info(
                "GateCalibrationEngine: amostragem insuficiente "
                "%d/%d sinais. Pulando analise.",
                total, self._min_samples,
            )
            return None

        elapsed = (time.time() - self._cycle_start) * 1000
        stats_by_gate: Dict[str, GateStats] = {}
        simulations: Dict[str, Dict[str, SimulationResult]] = {}

        for gate in self.GATE_PRIORITY:
            obs_list = self._observations.get(gate, [])
            if not obs_list:
                continue

            values = [o.value for o in obs_list]
            rejected = sum(1 for o in obs_list if o.rejected)
            threshold = GATES_CONFIGURATION.get(gate, 0.0)

            stats = self._compute_stats(values, threshold,
                                        len(obs_list), rejected)
            stats_by_gate[gate] = stats
            simulations[gate] = self._simulate_thresholds(gate, stats, values)

        diagnoses = self._diagnose_market(stats_by_gate)
        recommendations = self._generate_recommendations(
            stats_by_gate, simulations, diagnoses)

        report = self._format_report(
            stats_by_gate, simulations, diagnoses,
            recommendations, elapsed,
        )

        self._last_report = report
        self._last_data = {
            "cycle": self._cycle_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_signals": total,
            "stats_by_gate": {g: asdict(s) for g, s in stats_by_gate.items()},
            "simulations": {
                g: {k: asdict(v) for k, v in sim.items()}
                for g, sim in simulations.items()
            },
            "diagnoses": [asdict(d) for d in diagnoses],
            "recommendations": [asdict(r) for r in recommendations],
        }

        self._export_json(self._last_data)
        log.info("\n%s", report)
        return report

    # ------------------------------------------------------------------
    # Report formatting
    # ------------------------------------------------------------------

    def _format_report(self, stats_by_gate, simulations, diagnoses,
                        recommendations, elapsed_ms) -> str:
        lines = []
        lines.append("=" * 64)
        lines.append(f"  RELATORIO DE CALIBRACAO — Ciclo #{self._cycle_number}")
        lines.append("=" * 64)
        lines.append(f"Periodo: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"Quantidade de sinais: {self._total_signals}")
        lines.append(f"Aprovados: {self._approved_signals} | "
                      f"Rejeitados: {self._rejected_signals} | "
                      f"Taxa: {round(self._approved_signals / max(self._total_signals, 1) * 100, 1)}%")
        lines.append(f"Duracao: {elapsed_ms:.0f}ms")
        lines.append("")

        if diagnoses:
            lines.append("-" * 64)
            lines.append("  DIAGNOSTICO DE MERCADO")
            lines.append("-" * 64)
            for d in diagnoses:
                sev = {"low": "baixo", "medium": "medio", "high": "alto"}.get(d.severity, d.severity)
                lines.append(f"  [{sev.upper()}] {d.condition}")
                lines.append(f"         Evidencia: {d.evidence}")
                lines.append(f"         Sugestao: {d.suggestion}")
                lines.append("")

        if stats_by_gate:
            lines.append("-" * 64)
            lines.append("  ESTATISTICAS POR GATE")
            lines.append("-" * 64)
            header = (
                f"  {'Gate':<15} {'Rej':>4} {'Taxa':>5} {'Media':>7} "
                f"{'P50':>7} {'P75':>7} {'P90':>7} {'P95':>7} "
                f"{'Min':>7} {'Max':>7} {'Thr':>7}"
            )
            lines.append(header)
            lines.append("  " + "-" * (len(header) - 2))
            for gate in self.GATE_PRIORITY:
                s = stats_by_gate.get(gate)
                if not s or s.total == 0:
                    continue
                lines.append(
                    f"  {gate:<15} {s.rejected:>4} {s.rejection_rate:>4.0f}% "
                    f"{s.mean:>7.4f} {s.p50:>7.4f} {s.p75:>7.4f} "
                    f"{s.p90:>7.4f} {s.p95:>7.4f} {s.min_val:>7.4f} "
                    f"{s.max_val:>7.4f} {s.threshold:>7.4f}"
                )
            lines.append("")

        if simulations:
            lines.append("-" * 64)
            lines.append("  SIMULACOES DE THRESHOLD")
            lines.append("-" * 64)
            for gate in self.GATE_PRIORITY:
                sim = simulations.get(gate)
                if not sim:
                    continue
                lines.append(f"  {gate}: threshold atual={GATES_CONFIGURATION.get(gate, 0):.4f}")
                for label in ["-10%", "-5%", "Atual", "+5%", "+10%"]:
                    s = sim.get(label)
                    if not s:
                        continue
                    lines.append(
                        f"    {label:6s} -> th={s.threshold:.4f} "
                        f"passariam={s.would_pass:>4d} "
                        f"taxa={s.approval_rate:>5.1f}% "
                        f"WR={s.win_rate_impact:>+.1f}% "
                        f"PF={s.profit_factor_impact:>+.1f}% "
                        f"DD={s.drawdown_impact:>+.1f}%"
                    )
            lines.append("")

        if recommendations:
            lines.append("-" * 64)
            lines.append("  RECOMENDACOES")
            lines.append("-" * 64)
            for r in recommendations:
                lines.append(f"  Gate: {r.gate}")
                lines.append(f"  Threshold atual: {r.current_threshold:.4f}")
                lines.append(f"  Media observada: {r.mean_observed:.4f}")
                lines.append(f"  P75: {r.p75_observed:.4f} | P90: {r.p90_observed:.4f}")
                lines.append(f"  Conclusao: {r.reason}")
                lines.append(f"  Sugestao: reduzir para {r.suggested_threshold:.4f}")
                lines.append(f"  Confianca: {r.confidence:.0f}%")
                lines.append(f"  Impacto: +{r.additional_signals_per_cycle} sinais por ciclo")
                lines.append(f"  Evidencia: {r.evidence}")
                lines.append("")

        lines.append("=" * 64)
        lines.append("  FIM DO RELATORIO DE CALIBRACAO")
        lines.append("=" * 64)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # JSON export
    # ------------------------------------------------------------------

    def _export_json(self, data: Dict[str, Any]):
        path = os.path.join(
            self._export_dir,
            f"calibration_{self._cycle_number}.json",
        )
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning("GateCalibrationEngine: erro export JSON: %s", e)

    # ------------------------------------------------------------------
    # Report accessors
    # ------------------------------------------------------------------

    @property
    def last_report(self) -> str:
        return self._last_report

    @property
    def last_data(self) -> Dict[str, Any]:
        return dict(self._last_data)
