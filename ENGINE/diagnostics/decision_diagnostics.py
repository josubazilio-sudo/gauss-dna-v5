import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class FilterRecord:
    filter_name: str
    asset: str
    timeframe: str
    direction: str
    value: float
    threshold: float
    difference: float
    passed: bool
    details: str = ""


@dataclass
class IndicatorValidation:
    name: str
    value: float
    expected_min: float
    expected_max: float
    status: str  # "OK" or "Suspeito"
    note: str = ""


@dataclass
class DecisionDiagnosticsReport:
    timestamp: str = ""
    cycle_number: int = 0
    duration_ms: float = 0.0

    total_analyzed: int = 0
    total_approved: int = 0
    total_rejected: int = 0

    filter_counts: Dict[str, int] = field(default_factory=dict)
    filter_percentages: Dict[str, float] = field(default_factory=dict)
    filter_details: List[FilterRecord] = field(default_factory=list)
    indicator_validations: List[IndicatorValidation] = field(default_factory=list)

    indicators_per_asset: Dict[str, Dict] = field(default_factory=dict)
    ranking: List[Tuple[str, int, float]] = field(default_factory=list)

    report_text: str = ""


FILTER_MAP = [
    ("descalibracao", "Descalibração"),
    ("exaustao", "Exaustão"),
    ("rvol", "RVOL"),
    ("adx", "ADX"),
    ("bos", "BOS/CHoCH"),
    ("choch", "BOS/CHoCH"),
    ("estrutur", "Estrutura"),
    ("structure", "Estrutura"),
    ("entry", "Entry Zone"),
    ("consensus", "Consenso"),
    ("quality", "Quality Gate"),
    ("confidence", "Confiança"),
    ("confian", "Confiança"),
    ("kalman", "Kalman"),
    ("lateral", "Lateral"),
    ("rr", "RR"),
    ("precos", "Preços"),
    ("fv", "Final Validation"),
    ("ouro", "Classificação"),
    ("platina", "Classificação"),
    ("diamante", "Classificação"),
    ("coherence", "Coherence"),
    ("votacao", "Weighted Vote"),
    ("spread", "Spread"),
    ("atr", "ATR"),
    ("liquidez", "Liquidez"),
    ("liquidity", "Liquidez"),
]
INDICATOR_RANGES = {
    "rvol": (0.0, 10.0),
    "adx": (0.0, 100.0),
    "atr_percent": (0.0, 0.05),
    "rsi": (0.0, 100.0),
    "volatility": (0.0, 1.0),
    "structure_strength": (0.0, 1.0),
    "entry_score": (0.0, 1.0),
    "consensus_score": (0.0, 1.0),
    "quality_score": (0.0, 1.0),
    "confidence_score": (0.0, 1.0),
    "liquidity_score": (0.0, 1.0),
    "flow_score": (0.0, 1.0),
    "institutional_score": (0.0, 1.0),
    "momentum_score": (0.0, 1.0),
    "regime_confidence": (0.0, 1.0),
}


def _classify_rejection(reason: str) -> str:
    if not reason:
        return "Desconhecido"
    rl = reason.lower()
    for key, label in FILTER_MAP:
        if key in rl:
            return label
    if "sem dados" in rl:
        return "API"
    if "sem sinal" in rl:
        return "Sem Sinal"
    if "pipeline incompleto" in rl:
        return "Pipeline Incompleto"
    if "consenso" in rl:
        return "Consenso"
    return "Outros"


def _extract_value(reason: str) -> Optional[float]:
    import re
    nums = re.findall(r"[-+]?\d*\.?\d+", reason.replace(",", "."))
    if nums:
        try:
            return float(nums[0])
        except ValueError:
            return None
    return None


class DecisionDiagnostics:
    def __init__(self, audit_dir: Optional[str] = None):
        self._cycle_filters: Dict[str, int] = defaultdict(int)
        self._filter_details: List[FilterRecord] = []
        self._indicator_validations: List[IndicatorValidation] = []
        self._indicators_per_asset: Dict[str, Dict] = {}
        self._cycle_start: float = 0.0
        self._cycle_number: int = 0
        self._total_analyzed: int = 0
        self._total_approved: int = 0
        self._total_rejected: int = 0

        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self._audit_dir = audit_dir or os.path.join(base, "MEMORY", "diagnostics")
        self._ensure_dir()
        self._last_report: Optional[DecisionDiagnosticsReport] = None

    def _ensure_dir(self):
        try:
            os.makedirs(self._audit_dir, exist_ok=True)
        except Exception as e:
            log.warning("DecisionDiagnostics: nao foi possivel criar %s: %s", self._audit_dir, e)

    def start_cycle(self, cycle_number: int):
        self._cycle_filters.clear()
        self._filter_details.clear()
        self._indicator_validations.clear()
        self._indicators_per_asset.clear()
        self._cycle_start = time.time()
        self._cycle_number = cycle_number
        self._total_analyzed = 0
        self._total_approved = 0
        self._total_rejected = 0

    def increment_analyzed(self):
        self._total_analyzed += 1

    def increment_approved(self):
        self._total_approved += 1

    def increment_rejected(self):
        self._total_rejected += 1

    def record_filter_rejection(
        self,
        filter_name: str,
        asset: str,
        timeframe: str = "",
        direction: str = "",
        value: Optional[float] = None,
        threshold: Optional[float] = None,
        details: str = "",
    ):
        self._total_rejected += 1
        classified = _classify_rejection(filter_name)
        self._cycle_filters[classified] += 1

        diff = None
        if value is not None and threshold is not None:
            diff = round(value - threshold, 4)

        self._filter_details.append(FilterRecord(
            filter_name=classified,
            asset=asset,
            timeframe=timeframe,
            direction=direction,
            value=value or 0.0,
            threshold=threshold or 0.0,
            difference=diff or 0.0,
            passed=False,
            details=details or filter_name,
        ))

    def record_indicator(self, name: str, value: float, expected_min: float, expected_max: float):
        status = "OK" if expected_min <= value <= expected_max else "Suspeito"
        note = ""
        if status == "Suspeito":
            if value < expected_min:
                note = f"Abaixo do minimo ({expected_min})"
            else:
                note = f"Acima do maximo ({expected_max})"
        self._indicator_validations.append(IndicatorValidation(
            name=name, value=value,
            expected_min=expected_min, expected_max=expected_max,
            status=status, note=note,
        ))

    def record_asset_indicators(self, asset: str, indicators: Dict):
        self._indicators_per_asset[asset] = dict(indicators)
        for key, (emin, emax) in INDICATOR_RANGES.items():
            val = indicators.get(key)
            if val is not None:
                try:
                    self.record_indicator(key, float(val), emin, emax)
                except (ValueError, TypeError):
                    pass

    def end_cycle(self) -> DecisionDiagnosticsReport:
        elapsed = (time.time() - self._cycle_start) * 1000
        total = max(self._total_rejected + self._total_approved, 1)

        filter_counts = dict(self._cycle_filters)
        total_filter_rejections = sum(filter_counts.values()) or 1

        filter_percentages = {
            k: round(v / total_filter_rejections * 100, 1)
            for k, v in sorted(filter_counts.items(), key=lambda x: -x[1])
        }

        ranking = sorted(
            [(k, v, round(v / total_filter_rejections * 100, 1)) for k, v in filter_counts.items()],
            key=lambda x: -x[1],
        )

        total_rejected_by_filters = sum(filter_counts.values())
        unspecified = max(0, self._total_rejected - total_rejected_by_filters)

        report = DecisionDiagnosticsReport(
            timestamp=str(datetime.now(timezone.utc)),
            cycle_number=self._cycle_number,
            duration_ms=round(elapsed, 1),
            total_analyzed=self._total_analyzed,
            total_approved=self._total_approved,
            total_rejected=self._total_rejected,
            filter_counts=filter_counts,
            filter_percentages=filter_percentages,
            filter_details=list(self._filter_details),
            indicator_validations=list(self._indicator_validations),
            indicators_per_asset=dict(self._indicators_per_asset),
            ranking=ranking,
        )

        report.report_text = self._generate_report_text(report, unspecified)
        self._dump_report(report)
        self._last_report = report
        return report

    def _generate_report_text(self, report: DecisionDiagnosticsReport, unspecified: int) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append(f"QUANTOS DECISION REPORT — CICLO {report.cycle_number}")
        lines.append("=" * 60)
        lines.append(f"Timestamp: {report.timestamp}")
        lines.append(f"Duracao: {report.duration_ms:.0f}ms")
        lines.append("")
        lines.append(f"Ativos analisados: {report.total_analyzed}")
        lines.append(f"Aprovados: {report.total_approved}")
        lines.append(f"Rejeitados: {report.total_rejected}")
        lines.append("")

        approval_rate = (
            round(report.total_approved / max(report.total_analyzed, 1) * 100, 2)
        )
        lines.append(f"Taxa de aprovacao: {approval_rate}%")
        lines.append(f"Taxa de rejeicao: {100 - approval_rate}%")
        lines.append("")

        if report.total_approved > 0 and report.total_analyzed > 0:
            lines.append(f"Sinais por ciclo: {report.total_approved} / {report.total_analyzed}")
            lines.append("")

        lines.append("-" * 60)
        lines.append("REJEICOES POR FILTRO")
        lines.append("-" * 60)

        if report.ranking:
            for rank, (filtro, count, pct) in enumerate(report.ranking, 1):
                bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
                lines.append(f"{rank:2d}. {filtro:20s} {count:5d} ({pct:5.1f}%) {bar}")
        if unspecified > 0:
            lines.append(f"   {'Nao classificado':20s} {unspecified:5d}")

        lines.append("")
        lines.append("-" * 60)
        lines.append("RANKING DOS GARGALOS")
        lines.append("-" * 60)
        if report.ranking:
            for rank, (filtro, count, pct) in enumerate(report.ranking, 1):
                lines.append(f"{rank}o {filtro}: {count} rejeicoes ({pct}%)")
        lines.append("")

        suspeitos = [iv for iv in self._indicator_validations if iv.status == "Suspeito"]
        if suspeitos:
            lines.append("-" * 60)
            lines.append("INDICADORES SUSPEITOS")
            lines.append("-" * 60)
            for iv in suspeitos[:20]:
                lines.append(
                    f"  {iv.name:25s} = {iv.value:.4f}  "
                    f"(esperado: {iv.expected_min:.2f}-{iv.expected_max:.2f})  {iv.note}"
                )
            if len(suspeitos) > 20:
                lines.append(f"  ... e mais {len(suspeitos) - 20} indicadores suspeitos")

        # Per-filter threshold analysis
        lines.append("")
        lines.append("-" * 60)
        lines.append("ANALISE POR FILTRO — VALOR vs THRESHOLD")
        lines.append("-" * 60)

        filter_samples: Dict[str, List[FilterRecord]] = defaultdict(list)
        for fr in self._filter_details:
            filter_samples[fr.filter_name].append(fr)

        for fname, samples in sorted(filter_samples.items(), key=lambda x: -len(x[1])):
            vals = [s.value for s in samples if s.value > 0]
            thresholds = [s.threshold for s in samples if s.threshold > 0]
            if not vals:
                continue
            avg_val = sum(vals) / len(vals)
            avg_th = sum(thresholds) / len(thresholds) if thresholds else 0
            min_val = min(vals)
            max_val = max(vals)
            lines.append(
                f"  {fname:20s} | amostras={len(samples):4d} | "
                f"media={avg_val:.4f} | threshold_medio={avg_th:.4f} | "
                f"min={min_val:.4f} | max={max_val:.4f}"
            )

        lines.append("")
        lines.append("=" * 60)
        lines.append("FIM DO RELATORIO")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _dump_report(self, report: DecisionDiagnosticsReport):
        path = os.path.join(self._audit_dir, f"decision_cycle_{report.cycle_number}.json")
        try:
            data = {
                "cycle": report.cycle_number,
                "timestamp": report.timestamp,
                "duration_ms": report.duration_ms,
                "total_analyzed": report.total_analyzed,
                "total_approved": report.total_approved,
                "total_rejected": report.total_rejected,
                "filter_counts": report.filter_counts,
                "filter_percentages": report.filter_percentages,
                "ranking": [(r[0], r[1], r[2]) for r in report.ranking],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning("DecisionDiagnostics: erro ao escrever relatorio: %s", e)

    def get_last_report_text(self) -> str:
        if self._last_report:
            return self._last_report.report_text
        return "Nenhum relatorio disponivel."

    def get_summary_stats(self) -> Dict:
        if not self._last_report:
            return {}
        r = self._last_report
        return {
            "cycle": r.cycle_number,
            "analyzed": r.total_analyzed,
            "approved": r.total_approved,
            "rejected": r.total_rejected,
            "approval_rate": round(r.total_approved / max(r.total_analyzed, 1) * 100, 2),
            "top_bottleneck": r.ranking[0][0] if r.ranking else None,
            "top_bottleneck_pct": r.ranking[0][2] if r.ranking else 0,
            "duration_ms": r.duration_ms,
        }
