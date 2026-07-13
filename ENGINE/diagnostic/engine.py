import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_HEALTH_ALERT_THRESHOLD = 90

STAGES = [
    "carregamento",
    "api",
    "candles",
    "indicadores",
    "estrutura",
    "smart_money",
    "entry_zone",
    "consensus",
    "quality_gate",
    "decisao_final",
]


@dataclass
class DiagnosticReport:
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cycle_number: int = 0
    duration_ms: float = 0.0
    exchange: str = "MEXC"

    total_assets: int = 0
    approved_assets: int = 0

    pipeline_steps: Dict[str, int] = field(default_factory=dict)
    pipeline_funnel: Dict[str, int] = field(default_factory=dict)
    rejection_reasons: Dict[str, int] = field(default_factory=dict)
    top_candidates: List[Dict[str, Any]] = field(default_factory=list)
    approved_signals: List[Dict[str, Any]] = field(default_factory=list)

    assets_loaded: List[str] = field(default_factory=list)
    pipeline_audit: Dict[str, List[str]] = field(default_factory=dict)
    indicators: Dict[str, Dict] = field(default_factory=dict)
    structures: Dict[str, Dict] = field(default_factory=dict)
    smart_money: Dict[str, Dict] = field(default_factory=dict)
    entry_zones: Dict[str, Dict] = field(default_factory=dict)
    consensus: Dict[str, Dict] = field(default_factory=dict)
    quality_gates: Dict[str, Dict] = field(default_factory=dict)
    final_decisions: Dict[str, Dict] = field(default_factory=dict)
    bugs: List[Dict] = field(default_factory=list)
    health: Optional[Dict] = None
    entry_zone_analysis: Dict[str, Dict] = field(default_factory=dict)
    timestamps: Dict[str, float] = field(default_factory=dict)
    cycle_start: float = 0.0
    loop_status: str = "STOPPED"
    last_heartbeat: float = 0.0
    next_cycle_in: int = 60
    trade_outcomes: List[Dict] = field(default_factory=list)
    cycle_overall_scores: List[float] = field(default_factory=list)
    cycle_retornos: List[float] = field(default_factory=list)

    # RFC Diagnostico Avancado V7.0: snapshot completo de cada SignalDecision
    # processada no ciclo (sd.to_dict()), reaproveitado pelo advanced_report.py
    # para o funil granular, checklist por ativo e ranking de bloqueadores —
    # sem recalcular nenhum indicador.
    decisions: List[Dict[str, Any]] = field(default_factory=list)


class DiagnosticEngine:
    # Etapas que TODO ativo percorre — smart_money e quality_gate
    # sao opcionais (so existem para ativos com sinal candidato).
    CORE_STAGES = [
        "carregamento", "api", "candles", "indicadores",
        "estrutura", "entry_zone", "consensus", "decisao_final",
    ]

    def __init__(self):
        self._current_report: Optional[DiagnosticReport] = None
        self._audit_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "MEMORY", "audit",
        )
        self._setup_audit_dir()
        self._last_summary: Optional[Dict] = None

    def _setup_audit_dir(self):
        try:
            os.makedirs(self._audit_dir, exist_ok=True)
        except Exception as e:
            log.warning("DiagnosticEngine: nao foi possivel criar %s: %s", self._audit_dir, e)

    def _stage_done(self, pair: str, stage: str):
        if pair not in self._current_report.pipeline_audit:
            self._current_report.pipeline_audit[pair] = []
        if stage not in self._current_report.pipeline_audit[pair]:
            self._current_report.pipeline_audit[pair].append(stage)

    # --- Cycle lifecycle ---------------------------------------------------

    def start_cycle(self, cycle: int):
        self._current_report = DiagnosticReport(
            cycle_number=cycle,
            cycle_start=time.time(),
            timestamp=datetime.now(timezone.utc),
        )

    def set_loop_status(self, status: str, last_heartbeat: float, next_cycle_in: int = 60):
        if self._current_report:
            self._current_report.loop_status = status
            self._current_report.last_heartbeat = last_heartbeat
            self._current_report.next_cycle_in = next_cycle_in

    def end_cycle(self, duration: float) -> Optional[DiagnosticReport]:
        if not self._current_report:
            return None
        self._current_report.duration_ms = duration
        for pair in self._current_report.pipeline_audit:
            self._record_final_decision_from_audit(pair)
        self._generate_health()
        self._dump_cycle_audit()
        self._update_summary()
        return self._current_report

    # --- Stage 1-2: Market data / API --------------------------------------

    def record_market_data(
        self, pair: str, loaded: bool,
        api_ms: float = 0.0, error: Optional[str] = None,
    ):
        if not self._current_report:
            return
        is_first = pair not in self._current_report.assets_loaded
        if is_first:
            self._current_report.total_assets += 1
            self._current_report.assets_loaded.append(pair)
        self._current_report.timestamps[pair] = time.time()
        if loaded:
            if is_first:
                self._stage_done(pair, "carregamento")
                self._stage_done(pair, "api")
        else:
            self._current_report.final_decisions[pair] = {
                "status": "REJECTED",
                "primary_reason": "Carregamento",
                "expected": True,
                "obtained": False,
                "difference": "N/A",
                "secondary_reasons": [error or "Falha no carregamento"],
                "final_decision": "Rejected at API",
                "timestamp": str(datetime.now(timezone.utc)),
                "processing_time_ms": (time.time() - self._current_report.cycle_start) * 1000
                if self._current_report.cycle_start else 0,
            }

    # --- Stage 3: Candles --------------------------------------------------

    def record_candles(self, pair: str, tf_counts: Dict[str, int]):
        if not self._current_report:
            return
        self._stage_done(pair, "candles")
        if pair not in self._current_report.indicators:
            self._current_report.indicators[pair] = {}
        self._current_report.indicators[pair]["candles"] = tf_counts

    # --- Stage 4: Indicators -----------------------------------------------

    def record_indicators(self, pair: str, indicators: Dict[str, float]):
        if not self._current_report:
            return
        self._stage_done(pair, "indicadores")
        self._current_report.indicators[pair] = {
            **self._current_report.indicators.get(pair, {}),
            **indicators,
        }

    # --- Stage 5: Structure ------------------------------------------------

    def record_structure(self, pair: str, structure: Dict[str, Any]):
        if not self._current_report:
            return
        self._stage_done(pair, "estrutura")
        self._current_report.structures[pair] = structure

    # --- Stage 6: Smart Money ----------------------------------------------

    def record_smart_money(
        self, pair: str,
        order_blocks: int = 0, fvgs: int = 0,
        sweeps: int = 0, mitigacoes: int = 0,
    ):
        if not self._current_report:
            return
        self._stage_done(pair, "smart_money")
        self._current_report.smart_money[pair] = {
            "order_blocks": order_blocks,
            "fvgs": fvgs,
            "liquidity_sweeps": sweeps,
            "mitigacoes": mitigacoes,
        }

    # --- Stage 7: Entry Zone -----------------------------------------------

    def record_entry_zone(
        self, pair: str,
        zone_type: str = "", score: float = 0.0,
        distance: float = 0.0, approved: bool = False,
    ):
        if not self._current_report:
            return
        self._stage_done(pair, "entry_zone")
        self._current_report.entry_zones[pair] = {
            "zone_type": zone_type,
            "score": score,
            "distance": distance,
            "approved": approved,
        }

    # --- Entry Zone Analysis (detailed breakdown, transparency only) -------

    def record_entry_zone_analysis(self, pair: str, analysis: Dict):
        if not self._current_report:
            return
        self._current_report.entry_zone_analysis[pair] = analysis

    # --- Stage 8: Consensus ------------------------------------------------

    def record_consensus(self, pair: str, consensus_data: Dict[str, Any]):
        if not self._current_report:
            return
        self._stage_done(pair, "consensus")
        self._current_report.consensus[pair] = consensus_data

    # --- Stage 9: Quality Gate ---------------------------------------------

    def record_quality_gate(
        self, pair: str,
        scores: Dict[str, float],
        passed: bool,
        rejection_reasons: Optional[List[str]] = None,
    ):
        if not self._current_report:
            return
        self._stage_done(pair, "quality_gate")
        self._current_report.quality_gates[pair] = {
            "scores": scores,
            "passed": passed,
            "rejection_reasons": rejection_reasons or [],
        }

    # --- Stage 10-11: Final Decision ---------------------------------------

    def record_final_decision(
        self, pair: str,
        status: str,
        primary_reason: str = "",
        expected: Any = None,
        obtained: Any = None,
        secondary_reasons: Optional[List[str]] = None,
        final_decision: str = "",
        direction: str = "",
        trace_id: str = "",
    ):
        if not self._current_report:
            return
        self._stage_done(pair, "decisao_final")

        log.info(
            "DIAG-SD[%s] %s | status=%s dir=%s | trace_id=%s",
            pair, trace_id, status, direction, trace_id,
        )

        diff = None
        if expected is not None and obtained is not None:
            try:
                diff = round(float(obtained) - float(expected), 4)
            except (ValueError, TypeError):
                diff = "N/A"

        proc_time = (
            (time.time() - self._current_report.timestamps.get(pair, self._current_report.cycle_start)) * 1000
            if self._current_report.cycle_start else 0
        )

        decision = {
            "status": status,
            "direction": direction,
            "trace_id": trace_id,
            "primary_reason": primary_reason,
            "expected": expected,
            "obtained": obtained,
            "difference": diff,
            "secondary_reasons": secondary_reasons or [],
            "final_decision": final_decision,
            "timestamp": str(datetime.now(timezone.utc)),
            "processing_time_ms": round(proc_time, 1),
        }
        self._current_report.final_decisions[pair] = decision

        if status == "APPROVED":
            self._current_report.approved_assets += 1
        else:
            reason_key = primary_reason or final_decision or "Rejeitado"
            self._current_report.rejection_reasons[reason_key] = (
                self._current_report.rejection_reasons.get(reason_key, 0) + 1
            )
            quality = 0.0
            qg = self._current_report.quality_gates.get(pair, {})
            if qg:
                quality = qg.get("scores", {}).get("quality_score", 0.0)
            if quality > 0.5:
                self._current_report.top_candidates.append({
                    "asset": pair,
                    "quality": quality,
                    "reason": primary_reason,
                    "expected": expected,
                    "obtained": obtained,
                    "difference": diff,
                })
                self._current_report.top_candidates = sorted(
                    self._current_report.top_candidates,
                    key=lambda x: x["quality"], reverse=True,
                )[:10]

    def _record_final_decision_from_audit(self, pair: str):
        if pair in self._current_report.final_decisions:
            return
        stages = self._current_report.pipeline_audit.get(pair, [])
        last_stage = stages[-1] if stages else "nenhum"
        core_completed = [s for s in stages if s in self.CORE_STAGES]

        # CORRECAO V18.1: A maioria dos ativos nao gera sinal e para
        # naturalmente no estagio "estrutura" (ou antes) porque o scanner
        # nao encontrou entry_zone/consensus validos para eles. Isso e
        # COMPORTAMENTO NORMAL, nao "Pipeline Incompleto". So flag como
        # incompleto se o ativo comecou a ser processado mas nao tem
        # decision_final — e atingiu estagios avancados (> indicadores).
        if last_stage in ("carregamento", "api", "candles", "indicadores", "estrutura"):
            self.record_final_decision(
                pair=pair,
                status="REJECTED",
                primary_reason=f"Sem sinal (filtro em: {last_stage})",
                final_decision=f"Rejected: no signal generated at stage {last_stage}",
                secondary_reasons=[f"Scanner nao gerou sinal — etapa: {last_stage}"],
            )
            return

        if len(core_completed) >= len(self.CORE_STAGES):
            return
        self.record_final_decision(
            pair=pair,
            status="REJECTED",
            primary_reason="Pipeline Incompleto",
            final_decision=f"Rejected at stage: {last_stage}",
            secondary_reasons=[f"Processamento interrompido no estagio: {last_stage}"],
        )
        self.record_bug(
            module="DiagnosticEngine",
            function="_record_final_decision_from_audit",
            last_stage=last_stage,
            probable_cause=f"Ativo {pair} comecou etapas avancadas ({last_stage}) mas nao completou o pipeline.",
        )

    # --- Bug detection -----------------------------------------------------

    def record_bug(
        self, module: str, function: str,
        last_stage: str, probable_cause: str,
    ):
        if not self._current_report:
            return
        bug = {
            "module": module,
            "function": function,
            "last_stage": last_stage,
            "probable_cause": probable_cause,
            "timestamp": str(datetime.now(timezone.utc)),
        }
        self._current_report.bugs.append(bug)
        log.error("BUG DETECTADO - Modulo: %s | Funcao: %s | Estagio: %s | Causa: %s",
                  module, function, last_stage, probable_cause)

    def detect_silent_drops(self, monitored_pairs: List[str]):
        if not self._current_report:
            return
        for pair in monitored_pairs:
            if pair in self._current_report.final_decisions:
                continue
            stages = self._current_report.pipeline_audit.get(pair, [])
            last_stage = stages[-1] if stages else "nenhum"

            # CORRECAO V18.1: Ativos sem sinal param naturalmente em
            # estagios iniciais — nao e silent drop.
            if last_stage in ("carregamento", "api", "candles", "indicadores", "estrutura"):
                continue

            # So considera etapas CORE — smart_money e quality_gate
            # sao opcionais (so existem para ativos com sinal).
            core_completed = [s for s in stages if s in self.CORE_STAGES]
            if len(core_completed) < len(self.CORE_STAGES):
                completed = ", ".join(stages) if stages else "nenhum"
                self.record_bug(
                    module="DiagnosticEngine",
                    function="detect_silent_drops",
                    last_stage=last_stage,
                    probable_cause=f"Ativo {pair} desapareceu do pipeline. "
                                   f"Etapas concluidas: {completed}. "
                                   f"Esperado (core): {', '.join(self.CORE_STAGES)}",
                )

    # --- Health Score ------------------------------------------------------

    def _generate_health(self):
        if not self._current_report:
            return
        r = self._current_report
        total = max(r.total_assets, 1)

        stages_ok = sum(
            1 for s in r.pipeline_audit.values()
            if all(stage in s for stage in self.CORE_STAGES)
        )
        pipeline_pct = stages_ok / total * 100

        rejected_count = sum(r.rejection_reasons.values())
        approved_count = r.approved_assets
        bug_count = len(r.bugs)
        silent_drops = total - len(r.pipeline_audit)

        # Saude baseia-se em bugs reais e drops silenciosos,
        # nao em etapas opcionais que faltam por design.
        health = 100.0
        health -= bug_count * 10.0
        health -= silent_drops * 8.0
        health = max(0, min(100, health))

        now = time.time()
        last_cycle_ago = int(now - r.cycle_start) if r.cycle_start else 0
        heartbeat_ago = int(now - r.last_heartbeat) if r.last_heartbeat else 0
        next_cycle = r.cycle_start + r.duration_ms / 1000 + r.next_cycle_in if r.cycle_start and r.duration_ms else 0
        next_in = max(0, int(next_cycle - now)) if next_cycle else r.next_cycle_in

        r.health = {
            "api": 100,
            "candles": pipeline_pct,
            "pipeline": pipeline_pct,
            "silent_drops": silent_drops,
            "rejected": rejected_count,
            "approved": approved_count,
            "bugs": bug_count,
            "health_score": round(health, 1),
            "loop_status": r.loop_status,
            "last_heartbeat_ago_s": heartbeat_ago,
            "last_cycle_ago_s": last_cycle_ago,
            "next_cycle_in_s": next_in,
        }

        if health < _HEALTH_ALERT_THRESHOLD:
            log.warning("HEALTH ALERT: Score %.1f%% abaixo do limite %d%%", health, _HEALTH_ALERT_THRESHOLD)

        if r.loop_status == "ERROR":
            log.error("HEALTH ALERT: Loop Principal em estado ERROR")
        elif heartbeat_ago > 300 and r.loop_status == "RUNNING":
            log.warning("HEALTH ALERT: Sem heartbeat ha %ds — loop pode estar travado", heartbeat_ago)

    # --- Dashboard Metrics -------------------------------------------------

    def record_trade_outcome(
        self,
        trade_id: str,
        result: str,
        pnl_pct: float,
        pnl_usdt: float,
        overall_score: float = 0.0,
        retorno_pct: float = 0.0,
        holding_hours: float = 0.0,
    ):
        if not self._current_report:
            return
        outcome = {
            "trade_id": trade_id,
            "result": result,
            "pnl_pct": pnl_pct,
            "pnl_usdt": pnl_usdt,
            "overall_score": overall_score,
            "retorno_pct": retorno_pct,
            "holding_hours": holding_hours,
            "timestamp": str(datetime.now(timezone.utc)),
        }
        self._current_report.trade_outcomes.append(outcome)
        if overall_score > 0:
            self._current_report.cycle_overall_scores.append(overall_score)
        if retorno_pct != 0:
            self._current_report.cycle_retornos.append(retorno_pct)
        summary = self._load_summary()
        trade_log = summary.setdefault("trade_log", [])
        trade_log.append(outcome)
        if len(trade_log) > 1000:
            trade_log[:] = trade_log[-1000:]
        self._compute_dashboard_metrics(summary)
        self._write_summary(summary)

    def _compute_dashboard_metrics(self, summary: Dict):
        trade_log = summary.get("trade_log", [])
        wins = [t for t in trade_log if t.get("result") == "WIN"]
        losses = [t for t in trade_log if t.get("result") == "LOSS"]
        total_trades = len(wins) + len(losses)

        win_rate = round(len(wins) / total_trades * 100, 2) if total_trades > 0 else None

        total_pnl = sum(t.get("pnl_usdt", 0) for t in trade_log)
        gross_profit = sum(t.get("pnl_usdt", 0) for t in wins)
        gross_loss = abs(sum(t.get("pnl_usdt", 0) for t in losses))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (
            None if gross_profit == 0 else float("inf")
        )

        drawdown = 0.0
        peak = 0.0
        cumulative = 0.0
        for t in trade_log:
            cumulative += t.get("pnl_usdt", 0)
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > drawdown:
                drawdown = dd
        max_drawdown = round(drawdown, 2) if trade_log else None

        avg_win = round(sum(t.get("pnl_usdt", 0) for t in wins) / len(wins), 2) if wins else None
        avg_loss = round(sum(t.get("pnl_usdt", 0) for t in losses) / len(losses), 2) if losses else None
        expectancy = round(avg_win * win_rate / 100 - abs(avg_loss) * (1 - win_rate / 100), 2) if avg_win and avg_loss and win_rate else None

        overall_scores = [t.get("overall_score", 0) for t in trade_log if t.get("overall_score", 0) > 0]
        avg_overall = round(sum(overall_scores) / len(overall_scores), 1) if overall_scores else None

        retornos = [t.get("retorno_pct", 0) for t in trade_log if t.get("retorno_pct", 0) != 0]
        avg_retorno = round(sum(retornos) / len(retornos), 2) if retornos else None

        summary.update({
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "drawdown": max_drawdown,
            "total_trades": total_trades,
            "total_wins": len(wins),
            "total_losses": len(losses),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_pnl": round(total_pnl, 2),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "avg_overall_score": avg_overall,
            "avg_retorno_pct": avg_retorno,
            "last_update": str(datetime.now(timezone.utc)),
        })

    def get_dashboard_metrics(self) -> Dict:
        summary = self._load_summary()
        return {
            "win_rate": summary.get("win_rate"),
            "profit_factor": summary.get("profit_factor"),
            "drawdown": summary.get("drawdown"),
            "total_trades": summary.get("total_trades", 0),
            "total_wins": summary.get("total_wins", 0),
            "total_losses": summary.get("total_losses", 0),
            "gross_profit": summary.get("gross_profit"),
            "gross_loss": summary.get("gross_loss"),
            "net_pnl": summary.get("net_pnl"),
            "avg_win": summary.get("avg_win"),
            "avg_loss": summary.get("avg_loss"),
            "expectancy": summary.get("expectancy"),
            "avg_overall_score": summary.get("avg_overall_score"),
            "avg_retorno_pct": summary.get("avg_retorno_pct"),
            "total_cycles": summary.get("total_cycles", 0),
            "avg_quality": summary.get("avg_quality"),
            "avg_confidence": summary.get("avg_confidence"),
            "avg_consensus": summary.get("avg_consensus"),
            "avg_entry_score": summary.get("avg_entry_score"),
            "avg_processing_time_ms": summary.get("avg_processing_time_ms"),
            "last_update": summary.get("last_update", ""),
        }

    # --- Summary persistence -----------------------------------------------

    def _load_summary(self) -> Dict:
        path = os.path.join(self._audit_dir, "summary.json")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            log.warning("DiagnosticEngine: erro ao ler summary.json: %s", e)
        return {
            "total_cycles": 0,
            "total_assets_analyzed": 0,
            "total_signals_approved": 0,
            "total_signals_rejected": 0,
            "total_silent_drops": 0,
            "total_bugs": 0,
            "avg_processing_time_ms": 0.0,
            "avg_quality": 0.0,
            "avg_consensus": 0.0,
            "avg_confidence": 0.0,
            "avg_entry_score": 0.0,
            "profit_factor": None,
            "win_rate": None,
            "drawdown": None,
            "last_cycle": 0,
            "last_update": "",
        }

    def _update_summary(self):
        if not self._current_report:
            return
        r = self._current_report
        summary = self._load_summary()

        total_cycles = summary["total_cycles"] + 1
        total_approved = summary["total_signals_approved"] + r.approved_assets
        total_rejected = summary["total_signals_rejected"] + sum(r.rejection_reasons.values())
        total_silent = summary["total_silent_drops"] + (r.health["silent_drops"] if r.health else 0)
        total_bugs = summary["total_bugs"] + len(r.bugs)

        q_scores = [g.get("scores", {}).get("quality_score", 0) for g in r.quality_gates.values()]
        # So inclui consensus de pares que GERARAM sinal (score > 0),
        # evitando que os 500 ativos sem sinal (consensus=0)
        # distorcamin a media para ~0.04.
        c_scores = [c.get("consensus_score", 0) for c in r.consensus.values() if c.get("consensus_score", 0) > 0]
        e_scores = [e.get("score", 0) for e in r.entry_zones.values()]

        def safe_avg(vals):
            return round(sum(vals) / len(vals), 4) if vals else 0.0

        old_total = summary["total_cycles"]
        new_avg_time = (
            (summary["avg_processing_time_ms"] * old_total + r.duration_ms) / total_cycles
            if old_total > 0 else r.duration_ms
        )

        summary.update({
            "total_cycles": total_cycles,
            "total_assets_analyzed": summary["total_assets_analyzed"] + r.total_assets,
            "total_signals_approved": total_approved,
            "total_signals_rejected": total_rejected,
            "total_silent_drops": total_silent,
            "total_bugs": total_bugs,
            "avg_processing_time_ms": round(new_avg_time, 1),
            "avg_quality": safe_avg(q_scores) if old_total == 0 else round(
                (summary["avg_quality"] * old_total + safe_avg(q_scores)) / total_cycles, 4
            ),
            "avg_consensus": safe_avg(c_scores) if old_total == 0 else round(
                (summary["avg_consensus"] * old_total + safe_avg(c_scores)) / total_cycles, 4
            ),
            "avg_confidence": safe_avg(
                [g.get("scores", {}).get("confidence_score", 0) for g in r.quality_gates.values()]
            ) if old_total == 0 else round(
                (summary["avg_confidence"] * old_total + safe_avg(
                    [g.get("scores", {}).get("confidence_score", 0) for g in r.quality_gates.values()]
                )) / total_cycles, 4
            ),
            "avg_entry_score": safe_avg(e_scores) if old_total == 0 else round(
                (summary["avg_entry_score"] * old_total + safe_avg(e_scores)) / total_cycles, 4
            ),
            "last_cycle": r.cycle_number,
            "last_update": str(datetime.now(timezone.utc)),
        })

        self._write_summary(summary)
        self._last_summary = summary

    def _write_summary(self, summary: Dict):
        path = os.path.join(self._audit_dir, "summary.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning("DiagnosticEngine: erro ao escrever summary.json: %s", e)

    # --- Cycle audit dump --------------------------------------------------

    def _dump_cycle_audit(self):
        if not self._current_report:
            return
        r = self._current_report
        path = os.path.join(self._audit_dir, f"pipeline_{r.cycle_number}.json")
        try:
            data = {
                "cycle": r.cycle_number,
                "timestamp": str(r.timestamp),
                "duration_ms": r.duration_ms,
                "total_assets": r.total_assets,
                "approved_assets": r.approved_assets,
                "pipeline_steps": dict(r.pipeline_steps),
                "pipeline_funnel": dict(r.pipeline_funnel),
                "rejection_reasons": dict(r.rejection_reasons),
                "top_candidates": r.top_candidates[:10],
                "approved_signals": r.approved_signals,
                "indicators": {k: dict(v) for k, v in r.indicators.items()},
                "structures": {k: dict(v) for k, v in r.structures.items()},
                "smart_money": {k: dict(v) for k, v in r.smart_money.items()},
                "entry_zones": {k: dict(v) for k, v in r.entry_zones.items()},
                "consensus": {k: dict(v) if isinstance(v, dict) else str(v) for k, v in r.consensus.items()},
                "quality_gates": {k: dict(v) for k, v in r.quality_gates.items()},
                "final_decisions": {k: dict(v) for k, v in r.final_decisions.items()},
                "bugs": r.bugs,
                "health": r.health,
                "pipeline_audit": {k: list(v) for k, v in r.pipeline_audit.items()},
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning("DiagnosticEngine: erro ao escrever pipeline_%d.json: %s", r.cycle_number, e)

    # --- RFC Diagnostico Avancado V7.0 --------------------------------------

    def record_decision(self, decision: Dict[str, Any]):
        """Guarda o snapshot completo de uma SignalDecision (sd.to_dict()) do
        ciclo atual, para o advanced_report.py consumir sem recalcular nada."""
        if not self._current_report:
            return
        self._current_report.decisions.append(decision)

    # --- Legacy API (backward compat) --------------------------------------

    def record_step(self, step_name: str, count: int):
        if self._current_report:
            current = self._current_report.pipeline_steps.get(step_name, 0)
            self._current_report.pipeline_steps[step_name] = current + count

    def record_pipeline_funnel(self, funnel: Dict[str, int]):
        if self._current_report:
            self._current_report.pipeline_funnel = dict(funnel)

    def record_funnel_stage(self, stage: str, count: int):
        if self._current_report:
            self._current_report.pipeline_funnel[stage] = count

    def record_rejection(self, asset: str, reason: str, quality: float):
        if not self._current_report:
            return
        self._current_report.rejection_reasons[reason] = (
            self._current_report.rejection_reasons.get(reason, 0) + 1
        )
        if quality > 0.5:
            self._current_report.top_candidates.append({
                "asset": asset, "quality": quality, "reason": reason,
            })
            self._current_report.top_candidates = sorted(
                self._current_report.top_candidates, key=lambda x: x["quality"], reverse=True,
            )[:5]

    def record_signal(self, signal: Any):
        if not self._current_report:
            return
        from ENGINE.scanner.ssr import ssr_from_scores
        scores = signal.scores
        ssr_val = ssr_from_scores(
            quality_score=getattr(scores, 'quality_score', 0),
            confidence_score=getattr(scores, 'confidence_score', 0),
            consensus_score=getattr(scores, 'consensus_score', 0),
            entry_score=getattr(scores, 'entry_score', 0),
            institutional_score=getattr(scores, 'institutional_score', 0),
            structural_score=getattr(scores, 'structural_score', 0),
            liquidity_score=getattr(scores, 'liquidity_score', 0),
            market_score=getattr(scores, 'market_score', 0),
        )
        self._current_report.approved_signals.append({
            "asset": signal.ticker,
            "direction": signal.direction.value,
            "quality": getattr(scores, 'quality_score', 0),
            "consensus": signal.explanation if hasattr(signal, "explanation") else "N/A",
            "ssr": ssr_val,
        })
