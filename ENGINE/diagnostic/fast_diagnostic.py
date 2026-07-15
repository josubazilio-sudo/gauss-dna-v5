"""RFC V25.5 — Diagnostico Rapido Inteligente (Fast Diagnostic).

Roda ao final de CADA ciclo do scanner. Nao recalcula nenhum indicador —
le exclusivamente o resumo ja produzido por
`ENGINE.analytics.rejection_analytics.RejectionAnalytics.end_cycle()`
(gate_percentages, approval_rate, total_analyzed, etc., ja calculados por
main.py durante o proprio ciclo) mais 3 valores agregados triviais
(media de ADX, regime dominante, % de candles silenciosamente perdidos)
que ja estao disponiveis em memoria — nenhuma chamada de rede, nenhum
recalculo de RSI/ADX/ATR/estrutura.

Custo esperado: operacoes aritmeticas simples sobre estruturas ja em
memoria (dezenas a poucas centenas de itens) — sub-milissegundo, bem
dentro do teto de 2 segundos exigido pela RFC.

Baseline: media movel dos ultimos N ciclos (em memoria, por processo —
reinicia com o pm2/systemd; nao persistido em disco de proposito, para
manter o modulo leve e sem I/O extra).
"""
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# --- Thresholds (documentados, ajustaveis; nenhum e recalculado a partir
# de dados de mercado — sao limites de heuristica de diagnostico) --------
BASELINE_WINDOW = 20
MIN_BASELINE_SAMPLES = 3
GARGALO_PCT_THRESHOLD = 35.0          # % das reprovacoes concentradas em 1 gate
GATE_CRITICAL_PCT_OF_TOTAL = 90.0     # % do total analisado bloqueado por 1 gate
BUG_DELTA_THRESHOLD = 25.0            # pontos percentuais acima da media historica
ZERO_SIGNAL_STREAK_ALERT = 5          # ciclos consecutivos com 0 aprovados
APPROVAL_DROP_RATIO_ALERT = 0.5       # queda relativa (cai para <50% da media)
SILENT_DROP_PCT_ALERT = 15.0          # % de candles perdidos silenciosamente
ADX_FORTE_MIN = 25.0
ADX_FRACO_MAX = 18.0


class DiagnosticBaseline:
    """Media movel dos ultimos `BASELINE_WINDOW` ciclos, em memoria."""

    def __init__(self, window: int = BASELINE_WINDOW):
        self._window = window
        self._gate_history: Dict[str, deque] = {}
        self._approval_history: deque = deque(maxlen=window)

    def sample_count(self) -> int:
        return len(self._approval_history)

    def average_gate_pct(self, gate: str) -> Optional[float]:
        hist = self._gate_history.get(gate)
        if not hist or len(hist) < MIN_BASELINE_SAMPLES:
            return None
        return sum(hist) / len(hist)

    def average_approval_rate(self) -> Optional[float]:
        if len(self._approval_history) < MIN_BASELINE_SAMPLES:
            return None
        return sum(self._approval_history) / len(self._approval_history)

    def update(self, gate_percentages: Dict[str, float], approval_rate: float) -> None:
        self._approval_history.append(approval_rate)
        seen = set(gate_percentages.keys())
        for gate, pct in gate_percentages.items():
            hist = self._gate_history.setdefault(gate, deque(maxlen=self._window))
            hist.append(pct)
        # Gates que nao apareceram neste ciclo contam como 0% (senao a
        # media fica enviesada para cima por amostras ausentes).
        for gate, hist in self._gate_history.items():
            if gate not in seen:
                hist.append(0.0)


@dataclass
class FastDiagnosticResult:
    scanner_saudavel: bool
    mercado: str
    analisados: int
    aprovados: int
    recusados: int
    taxa_aprovacao: float
    top_motivos: List[Dict[str, Any]] = field(default_factory=list)
    gargalos: List[str] = field(default_factory=list)
    bug_suspeito: Optional[Dict[str, Any]] = None
    sugestoes: List[str] = field(default_factory=list)
    alerta_imediato: Optional[str] = None


_SUGESTOES_POR_GATE = {
    "RVOL": "Conferir sincronizacao dos candles e calculo do RVOL.",
    "ADX": "Validar calculo do ADX.",
    "Kalman": "Validar Gate Kalman.",
    "Consensus": "Revisar consenso multi-timeframe.",
    "Exaustao": "Revisar filtro de Exaustao.",
    "Entry Zone": "Revisar Entry Zone.",
    "Estrutura": "Conferir deteccao de BOS/CHoCH.",
    "Coherence": "Validar Coherence Score.",
}


def _classify_market(avg_adx: float, regime_mode: str) -> str:
    if avg_adx >= ADX_FORTE_MIN and regime_mode in ("uptrend", "downtrend"):
        return "Forte"
    if avg_adx < ADX_FRACO_MAX:
        return "Fraco"
    return "Lateral"


def _detect_bug(gate_percentages: Dict[str, float], baseline: DiagnosticBaseline) -> Optional[Dict[str, Any]]:
    best = None
    for gate, pct in gate_percentages.items():
        avg = baseline.average_gate_pct(gate)
        if avg is None:
            continue
        delta = pct - avg
        if delta >= BUG_DELTA_THRESHOLD:
            confianca = round(min(99.0, 50.0 + delta), 1)
            candidate = {
                "gate": gate, "media_historica": round(avg, 1),
                "atual": round(pct, 1), "delta": round(delta, 1),
                "confianca": confianca,
            }
            if best is None or delta > best["delta"]:
                best = candidate
    return best


def build_fast_diagnostic(
    cycle_summary: Dict[str, Any],
    baseline: DiagnosticBaseline,
    zero_signal_streak: int,
    avg_adx: float = 0.0,
    regime_mode: str = "",
    silent_drop_pct: float = 0.0,
) -> FastDiagnosticResult:
    total = int(cycle_summary.get("total_analyzed", 0))
    approved = int(cycle_summary.get("total_approved", 0))
    rejected = int(cycle_summary.get("total_rejected", 0))
    taxa = float(cycle_summary.get("approval_rate", 0.0))
    gate_pct: Dict[str, float] = cycle_summary.get("gate_percentages", {}) or {}
    ranking = cycle_summary.get("ranking", []) or []

    mercado = _classify_market(avg_adx, regime_mode)
    top_motivos = [
        {"gate": g, "percentual": p} for g, _c, p in ranking[:5]
    ]

    gargalos: List[str] = []
    for gate, pct in sorted(gate_pct.items(), key=lambda kv: -kv[1]):
        if pct >= GARGALO_PCT_THRESHOLD:
            gargalos.append(f"⚠ {gate} bloqueando muitos ativos ({pct:.0f}% das reprovacoes).")

    bug_suspeito = _detect_bug(gate_pct, baseline)

    sugestoes: List[str] = []
    for g in [gate for gate, _ in sorted(gate_pct.items(), key=lambda kv: -kv[1])[:2]]:
        s = _SUGESTOES_POR_GATE.get(g)
        if s:
            sugestoes.append(f"✔ {s}")
    if silent_drop_pct >= SILENT_DROP_PCT_ALERT:
        sugestoes.append("✔ Validar API (candles nao carregados acima do normal).")

    alert_reasons: List[str] = []
    if zero_signal_streak >= ZERO_SIGNAL_STREAK_ALERT:
        alert_reasons.append(
            f"Zero sinais aprovados por {zero_signal_streak} ciclos consecutivos."
        )
    for gate, pct_of_rejected in gate_pct.items():
        count = cycle_summary.get("gate_counts", {}).get(gate, 0)
        pct_of_total = (count / total * 100) if total > 0 else 0.0
        if pct_of_total >= GATE_CRITICAL_PCT_OF_TOTAL:
            alert_reasons.append(
                f"Gate {gate} reprovou {pct_of_total:.0f}% de todos os ativos analisados."
            )
    if silent_drop_pct >= SILENT_DROP_PCT_ALERT:
        alert_reasons.append(
            f"API/candles inconsistentes: {silent_drop_pct:.0f}% dos ativos nao carregaram dados."
        )
    baseline_approval = baseline.average_approval_rate()
    if (
        baseline_approval is not None and baseline_approval > 0
        and taxa < baseline_approval * APPROVAL_DROP_RATIO_ALERT
    ):
        alert_reasons.append(
            f"Queda abrupta na taxa de aprovacao: {taxa:.1f}% (media recente: {baseline_approval:.1f}%)."
        )
    if bug_suspeito and bug_suspeito["confianca"] >= 90.0:
        alert_reasons.append(
            f"Possivel bug em {bug_suspeito['gate']}: "
            f"{bug_suspeito['media_historica']:.0f}% -> {bug_suspeito['atual']:.0f}% "
            f"(confianca {bug_suspeito['confianca']:.0f}%)."
        )

    scanner_saudavel = not alert_reasons and not gargalos

    alerta_imediato = None
    if alert_reasons:
        linhas = ["\U0001f6a8 QuantOS — ALERTA IMEDIATO"] + [f"• {r}" for r in alert_reasons]
        alerta_imediato = "\n".join(linhas)

    return FastDiagnosticResult(
        scanner_saudavel=scanner_saudavel,
        mercado=mercado,
        analisados=total,
        aprovados=approved,
        recusados=rejected,
        taxa_aprovacao=taxa,
        top_motivos=top_motivos,
        gargalos=gargalos,
        bug_suspeito=bug_suspeito,
        sugestoes=sugestoes,
        alerta_imediato=alerta_imediato,
    )


def format_fast_diagnostic_log(result: FastDiagnosticResult) -> str:
    lines = [
        "=" * 50,
        "DIAGNOSTICO RAPIDO (FAST)",
        "=" * 50,
        f"Scanner saudavel: {'SIM' if result.scanner_saudavel else 'NAO'}",
        f"Mercado: {result.mercado}",
        f"Ativos analisados: {result.analisados}",
        f"Ativos aprovados: {result.aprovados}",
        f"Ativos recusados: {result.recusados}",
        f"Taxa de aprovacao: {result.taxa_aprovacao:.1f}%",
        "",
        "TOP MOTIVOS DE BLOQUEIO",
    ]
    for m in result.top_motivos:
        lines.append(f"  {m['gate']:.<25}{m['percentual']:.0f}%")
    if result.gargalos:
        lines.append("")
        lines.append("GARGALOS")
        lines.extend(f"  {g}" for g in result.gargalos)
    if result.bug_suspeito:
        b = result.bug_suspeito
        lines.append("")
        lines.append("\U0001f6a8 Possivel bug detectado")
        lines.append(
            f"  Motivo: {b['gate']} passou de media historica de "
            f"{b['media_historica']:.0f}% para {b['atual']:.0f}% de reprovacao."
        )
        lines.append(f"  Confianca: {b['confianca']:.0f}%")
    if result.sugestoes:
        lines.append("")
        lines.append("SUGESTOES")
        lines.extend(f"  {s}" for s in result.sugestoes)
    lines.append("=" * 50)
    return "\n".join(lines)


def format_detailed_diagnostic(summary: Dict[str, Any]) -> str:
    lines = [
        f"DIAGNOSTICO DETALHADO (Ciclo #{summary.get('cycle', '?')})",
        f"Analisados: {summary.get('total_analyzed', 0)} | "
        f"Aprovados: {summary.get('total_approved', 0)} | "
        f"Rejeitados: {summary.get('total_rejected', 0)} | "
        f"Taxa: {summary.get('approval_rate', 0):.1f}%",
        "",
    ]

    ranking = summary.get("ranking", []) or []
    if ranking:
        lines.append("RANKING DE REJEICAO")
        for gate, count, pct in ranking[:6]:
            bar = "#" * int(pct / 10) + "." * (10 - int(pct / 10))
            lines.append(f"  {gate:.<18} {count:>3}x {bar} {pct:.0f}%")
        lines.append("")

    by_coin = summary.get("by_coin", {}) or {}
    top_rej = by_coin.get("top_rejected", []) or []
    coin_gates = by_coin.get("coin_main_gate", {}) or {}
    if top_rej:
        lines.append("MOEDAS MAIS REJEITADAS")
        for symbol, count in top_rej[:8]:
            gate = coin_gates.get(symbol, "")
            lines.append(f"  {symbol:.<10} {count}x rejeitado" + (f"  <- {gate}" if gate else ""))
        lines.append("")

    tf_stats = summary.get("by_timeframe", {}) or {}
    if tf_stats:
        lines.append("POR TIMEFRAME")
        for tf in ["30m", "1h", "4h", "1d"]:
            s = tf_stats.get(tf, {})
            if s.get("analyzed", 0) > 0:
                a = s.get("approved", 0)
                r = s.get("rejected", 0)
                lines.append(f"  {tf:.<6} {s['analyzed']} sinais   OK{a} NOK{r}")
        lines.append("")

    thr = summary.get("threshold_analysis", {}) or {}
    if thr:
        sims = []
        for gate, ta in thr.items():
            for s in ta.get("simulations", [])[:2]:
                sims.append((gate, s.get("new_threshold", 0), s.get("would_pass", 0), s.get("pct_of_rejected", 0)))
        if sims:
            lines.append("SE AJUSTAR THRESHOLD (passariam)")
            for gate, new_th, would_pass, pct in sims[:5]:
                if would_pass > 0:
                    lines.append(f"  {gate}: {new_th} -> +{would_pass} sinais ({pct:.0f}%)")

    lines.append(f"Tempo: {summary.get('duration_ms', 0):.0f}ms")
    return "\n".join(lines)
