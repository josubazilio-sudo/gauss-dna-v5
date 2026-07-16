import csv
import json
import logging
import os
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class SignalRecord:
    timestamp: str = ""
    symbol: str = ""
    timeframe: str = ""
    direction: str = ""
    result: str = ""  # "APPROVED" or "REJECTED"
    overall_score: float = 0.0
    quality: float = 0.0
    confidence: float = 0.0
    consensus: float = 0.0
    confluence: float = 0.0
    coherence: float = 0.0
    rvol: float = 0.0
    adx: float = 0.0
    rsi: float = 0.0
    atr: float = 0.0
    liquidity: float = 0.0
    structure: float = 0.0
    flow: float = 0.0
    kalman_direction: str = ""
    kalman_confidence: float = 0.0
    trend: str = ""
    entry_score: float = 0.0
    risk_score: float = 0.0
    regime: str = ""
    gate: str = ""
    reject_reason: str = ""
    expected_value: float = 0.0
    found_value: float = 0.0
    difference: float = 0.0
    pct_to_approval: float = 0.0
    cycle_number: int = 0


GATE_THRESHOLDS: Dict[str, Tuple[float, bool]] = {
    "RVOL": (0.45, True),
    "ADX": (20.0, True),
    "Consensus": (0.50, True),
    "Quality Gate": (0.55, True),
    "Confianca": (0.65, True),
    "Entry Zone": (0.40, True),
    "RR": (2.0, True),
    "Estrutura": (0.28, True),
    "Coherence": (50.0, True),
    "Weighted Vote": (60.0, True),
    "Kalman": (0.0, False),
    "Lateral": (0.0, False),
    "Classificacao": (50.0, True),
    "Descalibracao": (0.12, True),
}

GATE_PERCENTAGE_MAP: Dict[str, str] = {
    "RVOL": "rvol",
    "ADX": "adx",
    "Consensus": "consensus",
    "Quality Gate": "quality",
    "Confianca": "confidence",
    "Entry Zone": "entry_score",
    "RR": "risk_reward",
    "Estrutura": "structure",
    "Coherence": "coherence",
    "Weighted Vote": "weighted_vote",
    "Kalman": "kalman",
    "Lateral": "lateral",
    "Classificacao": "classification",
    "Descalibracao": "descalibracao",
    "Scanner": "scanner",
    "Exaustao": "exaustao",
    "API": "api",
    "Sem Sinal": "no_signal",
    "Final Validation": "final_validation",
}

GATE_CLASSIFICATION_MAP: Dict[str, str] = {
    "rvol": "RVOL",
    "adx": "ADX",
    "consensus": "Consensus",
    "consenso": "Consensus",
    "quality": "Quality Gate",
    "quality_gate": "Quality Gate",
    "confidence": "Confianca",
    "confianca": "Confianca",
    "entry": "Entry Zone",
    "entry_score": "Entry Zone",
    "entry_zone": "Entry Zone",
    "rr": "RR",
    "risk_reward": "RR",
    "estrutur": "Estrutura",
    "structure": "Estrutura",
    "bos": "Estrutura",
    "choch": "Estrutura",
    "coherence": "Coherence",
    "weighted_vote": "Weighted Vote",
    "kalman": "Kalman",
    "lateral": "Lateral",
    "exaustao": "Exaustao",
    "scanner": "Scanner",
    "api": "API",
    "no_signal": "Sem Sinal",
    "final_validation": "Final Validation",
    "classificacao": "Classificacao",
    "classification": "Classificacao",
    "descalibracao": "Descalibracao",
    "outros": "Outros",
}

SENSITIVITY_RANGES: Dict[str, List[float]] = {
    "RVOL": [0.50, 0.47, 0.45, 0.42, 0.40, 0.37, 0.35],
    "ADX": [22, 21, 20, 18, 16, 14, 12],
    "Consensus": [0.55, 0.50, 0.45, 0.40, 0.35],
    "Quality Gate": [0.60, 0.55, 0.50, 0.45, 0.40],
    "Confianca": [0.70, 0.65, 0.60, 0.55, 0.50],
    "Entry Zone": [0.45, 0.40, 0.35, 0.30, 0.25],
    "RR": [2.2, 2.0, 1.8, 1.6, 1.5],
    "Estrutura": [0.35, 0.30, 0.28, 0.25, 0.22],
    "Coherence": [60, 55, 50, 45, 40],
    "Weighted Vote": [70, 65, 60, 55, 50],
    "Descalibracao": [0.15, 0.12, 0.10, 0.08, 0.05],
}


def _classify_gate(reason: str) -> str:
    if not reason:
        return "Outros"
    rl = reason.lower()
    for key, label in GATE_CLASSIFICATION_MAP.items():
        if key in rl:
            return label
    return "Outros"


def _compute_pct_to_approval(found: float, expected: float) -> float:
    if expected <= 0:
        return 0.0
    ratio = found / expected if expected != 0 else 0.0
    pct = min(ratio * 100, 100.0)
    return round(max(pct, 0.0), 1)


def _compute_simulation_impact(gate: str, current_threshold: float,
                                new_threshold: float, rejected_values: List[float]) -> int:
    if not rejected_values:
        return 0
    if new_threshold >= current_threshold:
        return 0
    passes = sum(1 for v in rejected_values if v >= new_threshold)
    return passes


class RejectionAnalytics:
    def __init__(self, export_dir: Optional[str] = None):
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self._export_dir = export_dir or os.path.join(base, "analytics")
        self._ensure_dir()

        self._records: List[SignalRecord] = []
        self._cycle_records: List[SignalRecord] = []
        self._cycle_start: float = 0.0
        self._cycle_number: int = 0
        self._scanner_time_ms: float = 0.0
        self._decision_time_ms: float = 0.0
        self._auditor_time_ms: float = 0.0
        self._validator_time_ms: float = 0.0
        self._enabled: bool = True

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def _ensure_dir(self):
        try:
            os.makedirs(self._export_dir, exist_ok=True)
        except Exception as e:
            log.warning("RejectionAnalytics: nao foi possivel criar %s: %s", self._export_dir, e)

    def start_cycle(self, cycle_number: int):
        self._cycle_records.clear()
        self._cycle_start = time.time()
        self._cycle_number = cycle_number
        self._scanner_time_ms = 0.0
        self._decision_time_ms = 0.0
        self._auditor_time_ms = 0.0
        self._validator_time_ms = 0.0

    def record_timing(self, stage: str, duration_ms: float):
        if stage == "scanner":
            self._scanner_time_ms += duration_ms
        elif stage == "decision":
            self._decision_time_ms += duration_ms
        elif stage == "auditor":
            self._auditor_time_ms += duration_ms
        elif stage == "validator":
            self._validator_time_ms += duration_ms

    def record_signal(self, **kwargs):
        if not self._enabled:
            return
        record = SignalRecord(
            timestamp=kwargs.get("timestamp", datetime.now(timezone.utc).isoformat()),
            symbol=kwargs.get("symbol", ""),
            timeframe=kwargs.get("timeframe", ""),
            direction=kwargs.get("direction", ""),
            result=kwargs.get("result", "REJECTED"),
            overall_score=kwargs.get("overall_score", 0.0),
            quality=kwargs.get("quality", 0.0),
            confidence=kwargs.get("confidence", 0.0),
            consensus=kwargs.get("consensus", 0.0),
            confluence=kwargs.get("confluence", 0.0),
            coherence=kwargs.get("coherence", 0.0),
            rvol=kwargs.get("rvol", 0.0),
            adx=kwargs.get("adx", 0.0),
            rsi=kwargs.get("rsi", 0.0),
            atr=kwargs.get("atr", 0.0),
            liquidity=kwargs.get("liquidity", 0.0),
            structure=kwargs.get("structure", 0.0),
            flow=kwargs.get("flow", 0.0),
            kalman_direction=kwargs.get("kalman_direction", ""),
            kalman_confidence=kwargs.get("kalman_confidence", 0.0),
            trend=kwargs.get("trend", ""),
            entry_score=kwargs.get("entry_score", 0.0),
            risk_score=kwargs.get("risk_score", 0.0),
            regime=kwargs.get("regime", ""),
            gate=kwargs.get("gate", ""),
            reject_reason=kwargs.get("reject_reason", ""),
            expected_value=kwargs.get("expected_value", 0.0),
            found_value=kwargs.get("found_value", 0.0),
            difference=kwargs.get("difference", 0.0),
            pct_to_approval=kwargs.get("pct_to_approval", 0.0),
            cycle_number=self._cycle_number,
        )
        self._records.append(record)
        self._cycle_records.append(record)

    def record_rejection(self, gate: str, symbol: str, found_value: float,
                          expected_value: float, timeframe: str = "",
                          direction: str = "", reject_reason: str = "",
                          **extra):
        if not self._enabled:
            return
        diff = round(found_value - expected_value, 6)
        pct = _compute_pct_to_approval(found_value, expected_value)
        kwargs = dict(extra)
        kwargs.update(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            result="REJECTED",
            gate=gate,
            reject_reason=reject_reason or gate,
            found_value=found_value,
            expected_value=expected_value,
            difference=diff,
            pct_to_approval=pct,
        )
        self.record_signal(**kwargs)

    def record_approval(self, symbol: str, timeframe: str = "",
                         direction: str = "", **extra):
        if not self._enabled:
            return
        kwargs = dict(extra)
        kwargs.update(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            result="APPROVED",
            gate="",
            reject_reason="",
            found_value=0.0,
            expected_value=0.0,
            difference=0.0,
            pct_to_approval=100.0,
        )
        self.record_signal(**kwargs)

    # ------------------------------------------------------------------
    # Cycle summary
    # ------------------------------------------------------------------
    def end_cycle(self) -> Dict[str, Any]:
        elapsed = (time.time() - self._cycle_start) * 1000
        summary = self._build_cycle_summary(elapsed)
        self._export_cycle(summary)
        return summary

    def _build_cycle_summary(self, elapsed_ms: float) -> Dict[str, Any]:
        total = len(self._cycle_records)
        approved = sum(1 for r in self._cycle_records if r.result == "APPROVED")
        rejected = total - approved

        # Gate statistics
        gate_counts: Dict[str, int] = defaultdict(int)
        gate_found_vals: Dict[str, List[float]] = defaultdict(list)
        gate_expected_map: Dict[str, float] = {}
        gate_records_by_gate: Dict[str, List[SignalRecord]] = defaultdict(list)
        for rec in self._cycle_records:
            if rec.gate and rec.result == "REJECTED":
                gate_counts[rec.gate] += 1
                gate_records_by_gate[rec.gate].append(rec)
                if rec.found_value > 0:
                    gate_found_vals[rec.gate].append(rec.found_value)
            if rec.expected_value > 0:
                gate_expected_map[rec.gate] = rec.expected_value

        # Ranking
        total_rejected_gates = sum(gate_counts.values()) or 1
        ranking = sorted(
            [(g, c, round(c / total_rejected_gates * 100, 1))
             for g, c in gate_counts.items()],
            key=lambda x: -x[1],
        )

        # Per coin
        coin_analyzed: Dict[str, int] = defaultdict(int)
        coin_approved: Dict[str, int] = defaultdict(int)
        coin_rejected: Dict[str, int] = defaultdict(int)
        coin_gate: Dict[str, Counter] = defaultdict(Counter)
        for rec in self._cycle_records:
            coin_analyzed[rec.symbol] += 1
            if rec.result == "APPROVED":
                coin_approved[rec.symbol] += 1
            else:
                coin_rejected[rec.symbol] += 1
                if rec.gate:
                    coin_gate[rec.symbol][rec.gate] += 1

        # Top coins rejected
        top_rejected_coins = sorted(
            [(s, c) for s, c in coin_rejected.items()],
            key=lambda x: -x[1],
        )[:10]

        # Top coins approved
        top_approved_coins = sorted(
            [(s, c) for s, c in coin_approved.items()],
            key=lambda x: -x[1],
        )[:10]

        # Per timeframe
        tf_stats: Dict[str, Dict] = defaultdict(lambda: {"analyzed": 0, "approved": 0, "rejected": 0})
        for rec in self._cycle_records:
            tf = rec.timeframe or "?"
            tf_stats[tf]["analyzed"] += 1
            if rec.result == "APPROVED":
                tf_stats[tf]["approved"] += 1
            else:
                tf_stats[tf]["rejected"] += 1

        # Threshold analysis
        threshold_analysis = self._analyze_thresholds(gate_counts, gate_found_vals, gate_expected_map)

        # Recommendations
        recommendations = self._generate_recommendations(
            ranking, gate_counts, gate_found_vals, gate_expected_map,
        )

        return {
            "cycle": self._cycle_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round(elapsed_ms, 1),
            "total_analyzed": total,
            "total_approved": approved,
            "total_rejected": rejected,
            "approval_rate": round(approved / max(total, 1) * 100, 2),
            "rejection_rate": round(rejected / max(total, 1) * 100, 2),
            "ranking": ranking,
            "top_10_reasons": ranking[:10],
            "gate_counts": dict(gate_counts),
            "gate_percentages": {
                g: round(c / total_rejected_gates * 100, 1)
                for g, c in sorted(gate_counts.items(), key=lambda x: -x[1])
            },
            "by_coin": {
                "analyzed": dict(coin_analyzed),
                "approved": dict(coin_approved),
                "rejected": dict(coin_rejected),
                "top_rejected": top_rejected_coins,
                "top_approved": top_approved_coins,
                "coin_main_gate": {
                    s: coin_gate[s].most_common(1)[0][0] if coin_gate[s] else ""
                    for s in coin_gate
                },
            },
            "by_timeframe": dict(tf_stats),
            "threshold_analysis": threshold_analysis,
            "recommendations": recommendations,
            "timing_ms": {
                "scanner": round(self._scanner_time_ms, 2),
                "decision": round(self._decision_time_ms, 2),
                "auditor": round(self._auditor_time_ms, 2),
                "validator": round(self._validator_time_ms, 2),
                "total": round(elapsed_ms, 1),
            },
        }

    # ------------------------------------------------------------------
    # Threshold analysis
    # ------------------------------------------------------------------
    def _analyze_thresholds(self, gate_counts: Dict[str, int],
                             gate_found_vals: Dict[str, List[float]],
                             gate_expected_map: Dict[str, float]) -> Dict[str, Any]:
        analysis = {}
        for gate, threshold, is_numeric in sorted(
            [(g, t, n) for g, (t, n) in GATE_THRESHOLDS.items()],
            key=lambda x: -gate_counts.get(x[0], 0),
        ):
            if not is_numeric:
                continue
            found = gate_found_vals.get(gate, [])
            if not found:
                analysis[gate] = {
                    "current_threshold": threshold,
                    "rejection_count": gate_counts.get(gate, 0),
                    "simulations": [],
                    "avg_found": 0.0,
                    "min_found": 0.0,
                    "pct_below_threshold": 0.0,
                }
                continue
            avg_found = round(sum(found) / len(found), 4)
            min_found = round(min(found), 4)
            pct_below = round(
                sum(1 for v in found if v < threshold) / len(found) * 100, 1
            )

            sims = []
            for new_th in SENSITIVITY_RANGES.get(gate, []):
                if new_th < threshold:
                    impact = _compute_simulation_impact(gate, threshold, new_th, found)
                    pct_change = round(impact / max(len(found), 1) * 100, 1)
                    sims.append({
                        "new_threshold": new_th,
                        "would_pass": impact,
                        "pct_of_rejected": pct_change,
                    })

            analysis[gate] = {
                "current_threshold": threshold,
                "rejection_count": gate_counts.get(gate, 0),
                "avg_found": avg_found,
                "min_found": min_found,
                "pct_below_threshold": pct_below,
                "simulations": sims,
            }
        return analysis

    def _generate_recommendations(self, ranking: List[Tuple[str, int, float]],
                                   gate_counts: Dict[str, int],
                                   gate_found_vals: Dict[str, List[float]],
                                   gate_expected_map: Dict[str, float]) -> List[str]:
        recs = []
        if not ranking:
            return recs

        top_gate = ranking[0][0]
        top_pct = ranking[0][2]
        top_count = ranking[0][1]

        recs.append(
            f"{top_gate} eh responsavel por {top_pct}% das "
            f"reprovacoes ({top_count} sinais)."
        )

        th = GATE_THRESHOLDS.get(top_gate)
        if th and th[1]:
            current_val = th[0]
            found = gate_found_vals.get(top_gate, [])
            if found:
                avg_found = sum(found) / len(found)
                diffs = [current_val - v for v in found if v < current_val]
                avg_gap = round(sum(diffs) / max(len(diffs), 1), 4) if diffs else 0.0
                for new_th in SENSITIVITY_RANGES.get(top_gate, []):
                    if new_th < current_val:
                        impact = _compute_simulation_impact(
                            top_gate, current_val, new_th, found,
                        )
                        if impact >= max(len(found) * 0.05, 1):
                            pct_increase = round(
                                impact / max(len(found), 1) * 100, 1,
                            )
                            gap_msg = (
                                f" gap medio de {avg_gap:.4f}"
                                if avg_gap > 0 else ""
                            )
                            recs.append(
                                f"  Reduzir {top_gate} de {current_val} para "
                                f"{new_th} +{pct_increase}% sinais.{gap_msg}"
                            )
                            break

                # Check if any other gate has a notable impact
                if len(ranking) >= 2:
                    second = ranking[1]
                    second_th = GATE_THRESHOLDS.get(second[0])
                    if second_th and second_th[1] and second[2] >= 10:
                        second_found = gate_found_vals.get(second[0], [])
                        if second_found:
                            for new_th in SENSITIVITY_RANGES.get(second[0], []):
                                if new_th < second_th[0]:
                                    impact = _compute_simulation_impact(
                                        second[0], second_th[0], new_th, second_found,
                                    )
                                    if impact >= max(len(second_found) * 0.05, 1):
                                        pct_increase = round(
                                            impact / max(len(second_found), 1) * 100, 1,
                                        )
                                        recs.append(
                                            f"  Reduzir {second[0]} de {second_th[0]} "
                                            f"para {new_th} +{pct_increase}% sinais."
                                        )
                                        break

            recs.append(
                f"  Recomenda-se validar em Paper Trading "
                f"antes de alterar qualquer parametro."
            )

        # Check if structure gate has disproportionate impact
        struct_name = "Estrutura"
        for g, c, p in ranking:
            if g == struct_name:
                recs.append(
                    f"{struct_name} eh responsavel por {p}% das reprovacoes, "
                    f"porem elimina sinais estruturais importantes. "
                    f"Nao eh recomendado flexibilizar este filtro sem "
                    f"analise de impacto em trades vencedores."
                )
                break

        return recs

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_cycle(self, summary: Dict[str, Any]):
        cycle = summary["cycle"]
        # Gate statistics
        gate_path = os.path.join(self._export_dir, f"gate_statistics_{cycle}.json")
        try:
            with open(gate_path, "w", encoding="utf-8") as f:
                json.dump({
                    "cycle": cycle,
                    "timestamp": summary["timestamp"],
                    "gate_counts": summary["gate_counts"],
                    "gate_percentages": summary["gate_percentages"],
                    "ranking": summary["ranking"],
                    "threshold_analysis": summary["threshold_analysis"],
                    "recommendations": summary["recommendations"],
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning("RejectionAnalytics: erro gate_statistics export: %s", e)

        # Summary
        daily_path = os.path.join(self._export_dir, f"cycle_summary_{cycle}.json")
        try:
            with open(daily_path, "w", encoding="utf-8") as f:
                json.dump({
                    "cycle": cycle,
                    "timestamp": summary["timestamp"],
                    "total_analyzed": summary["total_analyzed"],
                    "total_approved": summary["total_approved"],
                    "total_rejected": summary["total_rejected"],
                    "approval_rate": summary["approval_rate"],
                    "top_10_reasons": summary["top_10_reasons"],
                    "by_coin_top_rejected": summary["by_coin"]["top_rejected"],
                    "by_coin_top_approved": summary["by_coin"]["top_approved"],
                    "by_timeframe": summary["by_timeframe"],
                    "timing_ms": summary["timing_ms"],
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning("RejectionAnalytics: erro daily export: %s", e)

        # CSV append
        self._append_csv(self._cycle_records, cycle)

    def _append_csv(self, records: List[SignalRecord], cycle: int):
        approvals_path = os.path.join(self._export_dir, "approvals.csv")
        rejections_path = os.path.join(self._export_dir, "rejections.csv")

        approved_recs = [r for r in records if r.result == "APPROVED"]
        rejected_recs = [r for r in records if r.result == "REJECTED"]

        def _write_csv(path, data):
            if not data:
                return
            write_header = not os.path.exists(path)
            try:
                with open(path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=asdict(data[0]).keys())
                    if write_header:
                        writer.writeheader()
                    for rec in data:
                        writer.writerow(asdict(rec))
            except Exception as e:
                log.warning("RejectionAnalytics: erro csv export %s: %s", path, e)

        if approved_recs:
            _write_csv(approvals_path, approved_recs)
        if rejected_recs:
            _write_csv(rejections_path, rejected_recs)

    # ------------------------------------------------------------------
    # Global analysis over all historical records
    # ------------------------------------------------------------------
    def get_historical_summary(self) -> Dict[str, Any]:
        total = len(self._records)
        approved = sum(1 for r in self._records if r.result == "APPROVED")
        rejected = total - approved

        gate_counts: Dict[str, int] = defaultdict(int)
        gate_found_vals: Dict[str, List[float]] = defaultdict(list)
        for rec in self._records:
            if rec.gate and rec.result == "REJECTED":
                gate_counts[rec.gate] += 1
                if rec.found_value > 0:
                    gate_found_vals[rec.gate].append(rec.found_value)

        ranking = sorted(
            [(g, c, round(c / max(sum(gate_counts.values()), 1) * 100, 1))
             for g, c in gate_counts.items()],
            key=lambda x: -x[1],
        )

        return {
            "total_analyzed": total,
            "total_approved": approved,
            "total_rejected": rejected,
            "approval_rate": round(approved / max(total, 1) * 100, 2),
            "ranking": ranking,
            "gate_counts": dict(gate_counts),
        }

    def get_last_cycle_report_text(self) -> str:
        if not self._cycle_records and not self._records:
            return "Nenhum dado disponivel."

        summary = self._build_cycle_summary(0.0)
        lines = []
        lines.append("=" * 60)
        lines.append(f"QUANTOS ANALYTICS — CICLO {summary['cycle']}")
        lines.append("=" * 60)
        lines.append(f"Timestamp: {summary['timestamp']}")
        lines.append("")
        lines.append(f"Moedas analisadas: {summary['total_analyzed']}")
        lines.append(f"Sinais aprovados: {summary['total_approved']}")
        lines.append(f"Sinais rejeitados: {summary['total_rejected']}")
        lines.append(f"Taxa de aprovacao: {summary['approval_rate']}%")
        lines.append("")

        lines.append("-" * 60)
        lines.append("TOP MOTIVOS DE REPROVACAO")
        lines.append("-" * 60)
        for rank, (gate, count, pct) in enumerate(summary["ranking"], 1):
            bar_len = max(int(pct / 5), 1)
            bar = "#" * bar_len + "." * max(20 - bar_len, 0)
            lines.append(f"{rank:2d}. {gate:20s} {count:5d} ({pct:5.1f}%) {bar}")
        lines.append("")

        lines.append("-" * 60)
        lines.append("TOP MOEDAS REJEITADAS")
        lines.append("-" * 60)
        for sym, cnt in summary["by_coin"]["top_rejected"][:5]:
            main_gate = summary["by_coin"]["coin_main_gate"].get(sym, "?")
            lines.append(f"  {sym:12s} rejeitada={cnt:4d}x motivo_principal={main_gate}")
        lines.append("")

        lines.append("-" * 60)
        lines.append("TOP MOEDAS APROVADAS")
        lines.append("-" * 60)
        for sym, cnt in summary["by_coin"]["top_approved"][:5]:
            lines.append(f"  {sym:12s} aprovada={cnt:4d}x")
        lines.append("")

        lines.append("-" * 60)
        lines.append("TIMEFRAMES")
        lines.append("-" * 60)
        for tf, st in summary["by_timeframe"].items():
            tf_approval = round(
                st["approved"] / max(st["analyzed"], 1) * 100, 1,
            )
            lines.append(
                f"  {tf:6s} analisados={st['analyzed']:4d} "
                f"aprovados={st['approved']:4d} taxa={tf_approval}%"
            )
        lines.append("")

        lines.append("-" * 60)
        lines.append("TEMPO MEDIO (ms)")
        lines.append("-" * 60)
        for stage, tms in summary["timing_ms"].items():
            lines.append(f"  {stage:12s} {tms:>8.2f}")
        lines.append("")

        lines.append("-" * 60)
        lines.append("SIMULACOES DE THRESHOLDS")
        lines.append("-" * 60)
        for gate, ta in summary["threshold_analysis"].items():
            if ta["rejection_count"] == 0:
                continue
            lines.append(
                f"  {gate:20s} atual={ta['current_threshold']:.4f} "
                f"reprovacoes={ta['rejection_count']} "
                f"media_encontrada={ta['avg_found']:.4f}"
            )
            for sim in ta.get("simulations", []):
                if sim["would_pass"] > 0:
                    lines.append(
                        f"    -> {sim['new_threshold']:.4f} "
                        f"+{sim['would_pass']} sinais "
                        f"({sim['pct_of_rejected']}% das reprovacoes)"
                    )
        lines.append("")

        lines.append("-" * 60)
        lines.append("RECOMENDACOES")
        lines.append("-" * 60)
        for rec in summary["recommendations"]:
            lines.append(f"  {rec}")
        lines.append("")

        lines.append("=" * 60)
        lines.append("FIM DO RELATORIO ANALYTICS")
        lines.append("=" * 60)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Accessors for testing
    # ------------------------------------------------------------------
    @property
    def records(self) -> List[SignalRecord]:
        return list(self._records)

    @property
    def cycle_records(self) -> List[SignalRecord]:
        return list(self._cycle_records)

    @property
    def enabled(self) -> bool:
        return self._enabled
