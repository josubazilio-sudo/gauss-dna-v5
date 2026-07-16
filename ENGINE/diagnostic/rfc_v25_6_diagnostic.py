"""RFC V25.6 - Fast Diagnostic Evolution: Root Cause Analysis.

Three-level hierarchical diagnosis with automatic root cause identification,
top near-approved analysis, impact simulation, historical comparison,
bug auto-detection and prioritized recommendation engine.

Pure functions over pre-computed cycle data. Zero recalculation of
indicators. Zero network I/O. Zero side effects on trading pipeline.
"""
import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ENGINE.scanner.scanner_config import (
    QUALITY_GATE_MIN_SCORE, CONFIDENCE_GATE_MIN_SCORE,
    CONSENSUS_MINIMUM_SCORE, VOTE_MIN_CONCORDANCE_PCT,
    HARD_MIN_RVOL, HARD_MIN_ADX, HARD_MIN_STRUCTURE_STRENGTH,
    QUALITY_COMPONENT_CEILINGS,
)

log = logging.getLogger(__name__)

GATE_ORDER_HIERARCHY: List[str] = [
    "API", "Scanner", "Exaustao", "RVOL", "ADX", "Estrutura",
    "Entry Zone", "Quality Gate", "Consensus", "Confianca",
    "Descalibracao", "Kalman", "Lateral", "Coherence",
    "Weighted Vote", "Classificacao", "RR", "Final Validation",
]

_GATE_IMPORTANCE: Dict[str, int] = {
    "Consensus": 10, "Exaustao": 9, "Quality Gate": 8, "Coherence": 7,
    "Confianca": 7, "Estrutura": 6, "RVOL": 5, "ADX": 5, "Entry Zone": 5,
    "Weighted Vote": 5, "Kalman": 4, "Lateral": 3, "Descalibracao": 3,
    "RR": 4, "Classificacao": 3, "Final Validation": 2, "API": 1, "Scanner": 1,
}


def _safe_pct(part: int, total: int) -> float:
    return round(part / max(total, 1) * 100, 1)


def _avg(vals: List[float]) -> float:
    return round(sum(vals) / max(len(vals), 1), 4)


def _parse_rejection_pattern(reason: str) -> Tuple[str, str]:
    rl = reason.lower()
    for kw, label in [
        ("consenso", "Consensus"), ("exaustao", "Exaustao"),
        ("rvol", "RVOL"), ("adx", "ADX"),
        ("estrutur", "Estrutura"), ("entry zone", "Entry Zone"),
        ("entry_score", "Entry Zone"), ("quality", "Quality Gate"),
        ("confianca", "Confianca"), ("confidence", "Confianca"),
        ("descalibracao", "Descalibracao"), ("kalman", "Kalman"),
        ("lateral", "Lateral"), ("coherence", "Coherence"),
        ("votacao ponderada", "Weighted Vote"), ("weighted_vote", "Weighted Vote"),
        ("rr", "RR"), ("classificacao", "Classificacao"),
        ("api", "API"), ("scanner", "Scanner"),
        ("final validation", "Final Validation"),
        ("math_validation", "Final Validation"),
        ("bos", "Estrutura"), ("choch", "Estrutura"),
    ]:
        if kw in rl:
            return label, reason
    return "Outros", reason


def _extract_sub_reason(reason: str, module: str) -> str:
    rl = reason.lower()
    if module == "Consensus":
        for kw, label in [
            ("h4", "H4"), ("h1", "H1"), ("30m", "30m"), ("1d", "1d"),
            ("contrario", "contrario"), ("neutro", "neutro"),
            ("dissenting", "divergente"), ("discordancia", "divergente"),
        ]:
            if kw in rl:
                return label
        return "baixo consenso"
    if module == "Exaustao":
        for kw, label in [
            ("rsi", "RSI extremo"), ("adx_muito_alto", "ADX alto"),
            ("adx_fraco", "ADX fraco"), ("volume_climax", "volume climax"),
            ("velas_alongadas", "velas alongadas"),
            ("kalman_estagnado", "Kalman estagnado"),
            ("divergencia", "divergencia"),
        ]:
            if kw in rl:
                return label
        return "score elevado"
    if module == "Scanner":
        for kw, label in [
            ("liquidez", "Liquidez"), ("volume", "Volume"),
            ("candle", "Candle invalido"), ("dados", "Dados incompletos"),
        ]:
            if kw in rl:
                return label
        return "outro"
    return reason[:60]


# =====================================================================
# LEVEL 1 + 2: Module and sub-reason breakdown
# =====================================================================

def build_module_analysis(
    rejection_summary: Dict[str, Any],
    cycle_records_raw: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Nivel 1: percentage per module. Nivel 2: sub-reason per module."""
    gate_pct: Dict[str, float] = rejection_summary.get("gate_percentages", {}) or {}
    ranking = rejection_summary.get("ranking", []) or []
    total_rejected = sum(c for _, c, _ in ranking) or 1

    level1 = []
    for gate, pct in sorted(gate_pct.items(), key=lambda kv: -kv[1]):
        level1.append({
            "module": gate, "pct": pct, "count": round(pct * total_rejected / 100),
        })

    level2 = defaultdict(lambda: defaultdict(int))
    level2_total = defaultdict(int)
    for rec in cycle_records_raw:
        gate = rec.get("gate", "")
        reason = rec.get("reject_reason", "")
        if not gate:
            module, _ = _parse_rejection_pattern(reason)
        else:
            module = gate
        sub = _extract_sub_reason(reason, module)
        level2[module][sub] += 1
        level2_total[module] += 1

    level2_detail = {}
    for module, subs in level2.items():
        total_m = level2_total[module]
        detail = [
            {"sub_reason": s, "count": c, "pct": _safe_pct(c, total_m)}
            for s, c in sorted(subs.items(), key=lambda kv: -kv[1])
        ]
        level2_detail[module] = detail

    # Nivel 3: root cause analysis
    level3 = _build_root_cause(level1, level2_detail, level2_total)

    return {
        "level1": level1,
        "level2": level2_detail,
        "level3": level3,
    }


# =====================================================================
# LEVEL 3: Root cause analysis
# =====================================================================

def _build_root_cause(
    level1: List[Dict], level2: Dict[str, List[Dict]],
    level2_total: Dict[str, int],
) -> Dict[str, Any]:
    candidates = []
    for entry in sorted(level1, key=lambda x: -x["pct"])[:3]:
        module = entry["module"]
        subs = level2.get(module, [])
        if not subs:
            continue
        top_sub = subs[0]
        second_sub = subs[1] if len(subs) > 1 else None
        pct_of_rejected = entry["pct"]

        if second_sub and top_sub["pct"] + second_sub["pct"] >= 60:
            root_cause = (
                f"{top_sub['pct']}% das recusas em {module} foram por "
                f"{top_sub['sub_reason']} e {second_sub['sub_reason']}"
            )
            confidence = round(min(97.0, top_sub["pct"] + second_sub["pct"]), 1)
        elif top_sub["pct"] >= 35:
            root_cause = (
                f"{top_sub['pct']}% das recusas em {module} foram por "
                f"{top_sub['sub_reason']}"
            )
            confidence = round(min(95.0, top_sub["pct"] + 10), 1)
        else:
            root_cause = (
                f"{module} responsavel por {pct_of_rejected}% das "
                f"reprovacoes, distribuido em {len(subs)} sub-motivos"
            )
            confidence = round(min(80.0, 50.0 + pct_of_rejected / 2), 1)

        candidates.append({
            "module": module,
            "pct_of_rejected": pct_of_rejected,
            "root_cause": root_cause,
            "confidence": confidence,
            "evidence": top_sub.get("sub_reason", ""),
        })

    if candidates:
        top = candidates[0]
        return {
            "primary": top["root_cause"],
            "confidence": top["confidence"],
            "evidence": top["evidence"],
            "details": candidates,
        }
    return {
        "primary": "Nenhuma causa raiz dominante identificada",
        "confidence": 0.0,
        "evidence": "",
        "details": [],
    }


# =====================================================================
# TOP 20 QUASE APROVADOS
# =====================================================================

def build_top_near_approved(
    decisions: List[Dict[str, Any]],
    cycle_records_raw: List[Dict[str, Any]],
    min_count: int = 20,
) -> List[Dict[str, Any]]:
    rejected = [d for d in decisions if not d.get("approved")]
    scored = []
    for d in rejected:
        quality = d.get("quality_score", d.get("quality", 0.0))
        confidence = d.get("confidence_score", d.get("confidence", 0.0))
        consensus = d.get("consensus_score", d.get("consensus", 0.0))
        entry = d.get("entry_score", 0.0)
        overall = d.get("overall_score_value", quality * 100)

        last_gate, delta = _find_closest_gate(d)
        impact = _simulate_gate_impact(last_gate, delta, d) if last_gate else ""

        scored.append({
            "symbol": d.get("symbol", "?"),
            "timeframe": d.get("timeframe", ""),
            "direction": d.get("direction", ""),
            "overall_score": round(overall, 1),
            "quality": round(quality, 4),
            "confidence": round(confidence, 4),
            "consensus": round(consensus, 4),
            "entry_score": round(entry, 4),
            "classification": d.get("classification_label", "reprovado"),
            "last_gate": last_gate or "desconhecido",
            "delta_to_pass": round(delta, 4) if delta else 0.0,
            "reject_reason": d.get("reject_reason", ""),
            "impact": impact,
        })

    scored.sort(key=lambda x: -x["overall_score"])
    return scored[:min_count]


def _find_closest_gate(decision: Dict) -> Tuple[Optional[str], Optional[float]]:
    candidates = [
        ("RVOL", decision.get("rvol"), HARD_MIN_RVOL),
        ("ADX", decision.get("adx"), HARD_MIN_ADX),
        ("Estrutura", decision.get("structure_strength"), HARD_MIN_STRUCTURE_STRENGTH),
        ("Entry Zone", decision.get("entry_score"), 0.40),
        ("Quality Gate", decision.get("quality_score", decision.get("quality")), QUALITY_GATE_MIN_SCORE),
        ("Consensus", decision.get("consensus_score", decision.get("consensus")), CONSENSUS_MINIMUM_SCORE),
        ("Confianca", decision.get("confidence_score", decision.get("confidence")), CONFIDENCE_GATE_MIN_SCORE),
    ]
    best_gate, best_delta = None, None
    for gate, val, threshold in candidates:
        if val is None:
            continue
        gate_ok = decision.get({
            "RVOL": "rvol_ok", "ADX": "adx_ok", "Estrutura": "structure_ok",
            "Entry Zone": "entry_zone_ok", "Quality Gate": "quality_ok",
            "Consensus": "consensus_ok", "Confianca": "confidence_ok",
        }.get(gate, ""), None)
        if gate_ok is not None and gate_ok:
            continue
        delta = threshold - val
        if delta > 0 and (best_delta is None or delta < best_delta):
            best_gate = gate
            best_delta = delta
    return best_gate, best_delta


def _simulate_gate_impact(gate: str, delta: float, decision: Dict) -> str:
    val = decision.get({
        "RVOL": "rvol", "ADX": "adx", "Estrutura": "structure_strength",
        "Entry Zone": "entry_score",
        "Quality Gate": "quality_score",
        "Consensus": "consensus_score",
        "Confianca": "confidence_score",
    }.get(gate, ""), 0.0)
    if val and val > 0:
        pct_increase = round(delta / val * 100, 1) if val > 0 else 0
        return f"-{gate} em {delta:.4f} liberaria +{pct_increase}%"
    return ""


# =====================================================================
# IMPACT ANALYSIS
# =====================================================================

def build_impact_analysis(
    threshold_analysis: Dict[str, Any],
    ranking: List[Tuple[str, int, float]],
) -> Dict[str, Any]:
    impacts = []
    for gate, _, pct in ranking[:5]:
        ta = threshold_analysis.get(gate, {})
        sims = ta.get("simulations", [])
        if not sims:
            impacts.append({
                "gate": gate, "current_pct": pct,
                "estimated_impact": "Sem dados para simulacao",
            })
            continue
        best_sim = sims[0]
        candidates_freed = best_sim.get("would_pass", 0)
        quality_impact = max(-0.5, -candidates_freed * 0.3)
        impacts.append({
            "gate": gate,
            "current_pct": pct,
            "estimated_impact": (
                f"Se {gate} fosse menos restritivo: +{candidates_freed} "
                f"candidatos, qualidade estimada {quality_impact:+.1f}%"
            ),
            "candidates_freed": candidates_freed,
            "quality_impact_pct": round(quality_impact, 1),
            "simulations": [
                {"new_threshold": s["new_threshold"],
                 "would_pass": s["would_pass"],
                 "pct_of_rejected": s["pct_of_rejected"]}
                for s in sims[:3]
            ],
        })
    return {"impacts": impacts}


# =====================================================================
# HISTORICAL COMPARISON
# =====================================================================

def build_historical_comparison(
    current_summary: Dict[str, Any],
    baseline: Any,
    all_records: List[Any],
) -> Dict[str, Any]:
    result = {
        "current_cycle": {
            "approval_rate": current_summary.get("approval_rate", 0.0),
            "total_analyzed": current_summary.get("total_analyzed", 0),
            "total_approved": current_summary.get("total_approved", 0),
        },
        "historical_average": {},
        "gate_deltas": {},
        "anomalies": [],
    }

    avg_approval = baseline.average_approval_rate() if hasattr(baseline, 'average_approval_rate') else None
    if avg_approval is not None:
        current_rate = current_summary.get("approval_rate", 0.0)
        delta = round(current_rate - avg_approval, 1)
        result["historical_average"] = {
            "approval_rate": round(avg_approval, 1),
            "delta": delta,
            "status": "normal" if abs(delta) < 15 else (
                "alerta" if delta < -15 else "melhora"
            ),
        }

    gate_pct: Dict[str, float] = current_summary.get("gate_percentages", {}) or {}
    for gate in sorted(gate_pct.keys()):
        current = gate_pct[gate]
        avg_gate = baseline.average_gate_pct(gate) if hasattr(baseline, 'average_gate_pct') else None
        if avg_gate is not None:
            delta = round(current - avg_gate, 1)
            result["gate_deltas"][gate] = {
                "current": current,
                "historical_avg": round(avg_gate, 1),
                "delta": delta,
                "status": "normal" if abs(delta) < 15 else (
                    "alerta" if delta > 15 else "melhora"
                ),
            }
            if abs(delta) >= 25:
                result["anomalies"].append(
                    f"{gate}: {current:.0f}% (media {avg_gate:.0f}%, "
                    f"delta {delta:+.0f}pp) — comportamento anormal"
                )

    cycle_numbers = sorted(set(
        getattr(r, 'cycle_number', 0) for r in all_records
    )) if all_records else []
    result["cycle_count"] = len(cycle_numbers)
    result["last_cycles"] = cycle_numbers[-10:] if len(cycle_numbers) > 10 else cycle_numbers

    return result


# =====================================================================
# BUG AUTO DETECTION (Enhanced)
# =====================================================================

def build_bug_detection(
    gate_percentages: Dict[str, float],
    baseline: Any,
    threshold_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    bugs = []
    for gate, pct in sorted(gate_percentages.items(), key=lambda kv: -kv[1]):
        avg_pct = baseline.average_gate_pct(gate) if hasattr(baseline, 'average_gate_pct') else None
        if avg_pct is None:
            continue
        delta = pct - avg_pct
        if delta >= 25:
            confianca = round(min(99.0, 50.0 + delta), 1)
            bugs.append({
                "gate": gate,
                "media_historica": round(avg_pct, 1),
                "atual": round(pct, 1),
                "delta": round(delta, 1),
                "confianca": confianca,
                "provável_causa": _suggest_bug_cause(gate, delta, threshold_analysis),
                "evidencias": [
                    f"Media historica: {avg_pct:.0f}%",
                    f"Valor atual: {pct:.0f}%",
                    f"Diferenca: {delta:+.0f}pp",
                ],
            })

    dep_count = sum(1 for g in gate_percentages if gate_percentages[g] > 0)
    deploy_detected = any(
        b["delta"] >= 30 and b["confianca"] >= 85 for b in bugs
    )

    return {
        "bugs": bugs,
        "deploy_anomaly_detected": deploy_detected,
        "total_gates_active": dep_count,
    }


def _suggest_bug_cause(gate: str, delta: float, ta: Dict) -> str:
    suggestions = {
        "Consensus": "Possivel recalculo de pesos ou nova TF",
        "Exaustao": "Filtro de exaustao pode estar muito sensivel",
        "RVOL": "Verificar sincronizacao de volume da API",
        "ADX": "Possivel alteracao no calculo do ADX",
        "Estrutura": "Verificar deteccao de BOS/CHoCH",
        "Quality Gate": "Quality component ceilings ou weights alterados",
        "Confianca": "Confidence score recalibrado",
        "Entry Zone": "Entry zone formula alterada",
        "Coherence": "Coherence score ou weighted vote recalibrados",
        "Weighted Vote": "Vote weights ou threshold alterados",
    }
    base = suggestions.get(gate, f"Comportamento anormal no gate {gate}")
    if delta >= 40:
        base += " (urgencia alta)"
    return base


# =====================================================================
# RECOMMENDATION ENGINE
# =====================================================================

def build_prioritized_recommendations(
    module_analysis: Dict[str, Any],
    impact_analysis: Dict[str, Any],
    historical: Dict[str, Any],
    bug_detection: Dict[str, Any],
) -> List[Dict[str, Any]]:
    recs = []

    level1 = module_analysis.get("level1", [])
    for entry in level1[:3]:
        module = entry["module"]
        pct = entry["pct"]
        importance = _GATE_IMPORTANCE.get(module, 5)
        priority = "Alta" if (pct >= 40 and importance >= 7) else (
            "Media" if pct >= 20 else "Baixa"
        )
        confidence = round(min(98.0, 50.0 + pct * 0.8), 1)
        impact = "Muito Alto" if priority == "Alta" else (
            "Moderado" if priority == "Media" else "Baixo"
        )
        recs.append({
            "priority": priority,
            "action": f"Validar Gate {module}",
            "confidence": confidence,
            "expected_impact": impact,
            "evidence": f"{module} bloqueia {pct}% dos sinais",
            "type": "gate_review",
        })

    for imp in impact_analysis.get("impacts", []):
        if imp.get("candidates_freed", 0) >= 3:
            recs.append({
                "priority": "Media",
                "action": f"Considerar ajuste em {imp['gate']}",
                "confidence": round(min(90.0, imp['candidates_freed'] * 5), 1),
                "expected_impact": "Moderado",
                "evidence": imp["estimated_impact"],
                "type": "threshold_tuning",
            })

    for bug in bug_detection.get("bugs", []):
        if bug["confianca"] >= 85:
            recs.append({
                "priority": "Alta",
                "action": f"Investigar bug suspeito em {bug['gate']}",
                "confidence": bug["confianca"],
                "expected_impact": "Muito Alto",
                "evidence": bug.get("provável_causa", ""),
                "type": "bug_investigation",
            })

    for anomalia in historical.get("anomalies", []):
        recs.append({
            "priority": "Media",
            "action": "Revisar mudanca recente no sistema",
            "confidence": 85.0,
            "expected_impact": "Alto",
            "evidence": anomalia,
            "type": "regression_check",
        })

    recs.sort(key=lambda r: (
        {"Alta": 0, "Media": 1, "Baixa": 2}.get(r["priority"], 3),
        -r["confidence"],
    ))
    return recs


# =====================================================================
# ORCHESTRATOR
# =====================================================================

def build_v25_6_diagnostic(
    rejection_summary: Dict[str, Any],
    cycle_records_raw: List[Dict[str, Any]],
    decisions: List[Dict[str, Any]],
    baseline: Any,
    all_records: List[Any],
) -> Dict[str, Any]:
    module_analysis = build_module_analysis(rejection_summary, cycle_records_raw)
    near_approved = build_top_near_approved(decisions, cycle_records_raw)
    threshold_analysis = rejection_summary.get("threshold_analysis", {})
    ranking = rejection_summary.get("ranking", [])
    impact_analysis = build_impact_analysis(threshold_analysis, ranking)
    historical = build_historical_comparison(
        rejection_summary, baseline, all_records,
    )
    gate_pct = rejection_summary.get("gate_percentages", {}) or {}
    bug_detection = build_bug_detection(gate_pct, baseline, threshold_analysis)
    recommendations = build_prioritized_recommendations(
        module_analysis, impact_analysis, historical, bug_detection,
    )

    return {
        "module_analysis": module_analysis,
        "near_approved": near_approved,
        "impact_analysis": impact_analysis,
        "historical_comparison": historical,
        "bug_detection": bug_detection,
        "recommendations": recommendations,
    }


# =====================================================================
# FORMATTER (text output for logging)
# =====================================================================

def format_v25_6_report(data: Dict[str, Any]) -> str:
    lines = [
        "=" * 60,
        "RFC V25.6 - DIAGNOSTICO AVANCADO (CAUSA RAIZ)",
        "=" * 60,
    ]

    ma = data.get("module_analysis", {})
    lines.append("")
    lines.append("-" * 60)
    lines.append("NIVEL 1 - MODULOS BLOQUEADORES")
    lines.append("-" * 60)
    for entry in ma.get("level1", []):
        bar = "#" * max(int(entry["pct"] / 5), 1) + "." * max(20 - max(int(entry["pct"] / 5), 1), 0)
        lines.append(f"  {entry['module']:.<20}{entry['pct']:5.0f}% {bar}")

    lines.append("")
    lines.append("-" * 60)
    lines.append("NIVEL 2 - DETALHAMENTO POR MODULO")
    lines.append("-" * 60)
    for module, subs in sorted(
        ma.get("level2", {}).items(),
        key=lambda kv: -sum(s["pct"] for s in kv[1]),
    ):
        lines.append(f"  {module}")
        for sub in subs[:5]:
            bar = "#" * max(int(sub["pct"] / 5), 1) + "." * max(10 - max(int(sub["pct"] / 5), 1), 0)
            lines.append(f"    {sub['sub_reason']:.<20}{sub['pct']:5.0f}% {bar}")

    l3 = ma.get("level3", {})
    if l3:
        lines.append("")
        lines.append("-" * 60)
        lines.append(f"NIVEL 3 - CAUSA RAIZ (Confianca: {l3.get('confidence', 0):.0f}%)")
        lines.append("-" * 60)
        lines.append(f"  {l3.get('primary', 'N/A')}")
        for detail in l3.get("details", []):
            lines.append(f"  -> {detail.get('module', '?')}: {detail.get('root_cause', '')}")

    lines.append("")
    lines.append("-" * 60)
    lines.append("TOP 20 QUASE APROVADOS")
    lines.append("-" * 60)
    for i, cand in enumerate(data.get("near_approved", [])[:20], 1):
        lines.append(
            f"  {i:2d}. {cand['symbol']:12s} Score {cand['overall_score']:5.1f} "
            f"| Ultimo Gate: {cand['last_gate']:15s} "
            f"| {cand.get('impact', cand.get('reject_reason', ''))[:50]}"
        )

    hist = data.get("historical_comparison", {})
    lines.append("")
    lines.append("-" * 60)
    lines.append("COMPARACAO HISTORICA")
    lines.append("-" * 60)
    hist_avg = hist.get("historical_average", {})
    if hist_avg:
        status_icon = "\u2705" if hist_avg.get("status") == "normal" else "\u26a0\ufe0f"
        lines.append(f"  Taxa aprovacao atual: {hist.get('current_cycle', {}).get('approval_rate', '?'):.1f}%")
        lines.append(f"  Media historica: {hist_avg.get('approval_rate', '?'):.1f}% "
                      f"(delta {hist_avg.get('delta', 0):+.1f}pp) {status_icon}")
        lines.append(f"  Ciclos analisados: {hist.get('cycle_count', 0)} "
                      f"({len(hist.get('last_cycles', []))} recentes)")
    for anomalia in hist.get("anomalies", []):
        lines.append(f"  \u26a0\ufe0f {anomalia}")

    impact = data.get("impact_analysis", {})
    lines.append("")
    lines.append("-" * 60)
    lines.append("ANALISE DE IMPACTO")
    lines.append("-" * 60)
    for imp in impact.get("impacts", []):
        lines.append(f"  {imp.get('gate', '?')}: {imp.get('estimated_impact', 'N/A')}")
        for sim in imp.get("simulations", [])[:2]:
            lines.append(
                f"    -> {sim['new_threshold']} +{sim['would_pass']} sinais "
                f"({sim['pct_of_rejected']}% das reprovacoes)"
            )

    bugs = data.get("bug_detection", {})
    if bugs.get("bugs"):
        lines.append("")
        lines.append("-" * 60)
        lines.append("AUTO DETECCAO DE BUG")
        lines.append("-" * 60)
        for bug in bugs["bugs"]:
            lines.append(
                f"  \U0001f6a8 {bug['gate']}: {bug['media_historica']:.0f}% -> "
                f"{bug['atual']:.0f}% (confianca {bug['confianca']:.0f}%)"
            )
            lines.append(f"    Causa: {bug.get('provável_causa', 'N/A')}")
        if bugs.get("deploy_anomaly_detected"):
            lines.append("  \U0001f6a8 Anomalia pos-deploy detectada!")

    recs = data.get("recommendations", [])
    lines.append("")
    lines.append("-" * 60)
    lines.append("RECOMENDACOES PRIORIZADAS")
    lines.append("-" * 60)
    if not recs:
        lines.append("  Nenhuma recomendacao neste ciclo.")
    for rec in recs:
        icon = {"Alta": "\U0001f534", "Media": "\U0001f7e1", "Baixa": "\U0001f7e2"}.get(rec["priority"], "\u26ab")
        lines.append(
            f"  {icon} [{rec['priority']}] {rec['action']} | "
            f"Confianca: {rec['confidence']:.0f}% | "
            f"Impacto: {rec['expected_impact']}"
        )
        lines.append(f"    Evidencia: {rec['evidence']}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("FIM RFC V25.6")
    lines.append("=" * 60)

    return "\n".join(lines)
