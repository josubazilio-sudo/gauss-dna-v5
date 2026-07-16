"""RFC V6.7 — Diagnóstico Baseado Apenas nas Moedas Escaneadas.
RFC Diagnostico Avancado V7.0 — ferramenta de auditoria institucional.

Le exclusivamente dados ja calculados por DiagnosticEngine/DecisionEngine
(via DiagnosticReport.decisions, populado por main.py com sd.to_dict()).
Nao recalcula nenhum indicador, nao altera Decision Engine, gates,
thresholds, scoring ou Paper Trading. Modulo somente-leitura.

RFC V6.7: todas as estatisticas usam exclusivamente report.decisions
(ativos escaneados) como denominador, nunca report.total_assets (universo
completo da exchange). Adiciona bloco RESUMO DO CICLO, market statistics
filtradas por escaneados, metricas de eficiencia e guarda para decisions
vazia.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ENGINE.common.score_normalizer import scale_1_to_100
from ENGINE.scanner.scanner_config import (
    HARD_MIN_RVOL, HARD_MIN_ADX, HARD_MIN_STRUCTURE_STRENGTH,
    ENTRY_ZONE_SCORE_MIN, QUALITY_GATE_MIN_SCORE, CONSENSUS_MINIMUM_SCORE,
    CONFIDENCE_GATE_MIN_SCORE, CLASSIFICATION_RANGES,
)

# Ordem real de avaliacao em ENGINE/decision/decision_engine.py:evaluate_signal.
# Cada tupla: (rotulo exibido, campo *_ok em SignalDecision).
# Observacao de fidelidade: RSI, ATR, Liquidez e Volume nao sao gates
# independentes com flag propria no DecisionEngine atual — eles alimentam
# scores compostos (Quality, Market, Risk). Por isso nao aparecem como
# estagios do funil aqui; usar os campos reais evita diagnostico ficticio.
GATE_ORDER: List[Tuple[str, str]] = [
    ("RVOL", "rvol_ok"),
    ("ADX", "adx_ok"),
    ("Estrutura (BOS/CHoCH)", "structure_ok"),
    ("Entry Zone", "entry_zone_ok"),
    ("Quality", "quality_ok"),
    ("Consensus", "consensus_ok"),
    ("Confidence", "confidence_ok"),
    ("Kalman", "kalman_ok"),
    ("Risk/RR", "rr_ok"),
]

_GATE_THRESHOLDS = {
    "rvol_ok": ("rvol", HARD_MIN_RVOL, ">="),
    "adx_ok": ("adx", HARD_MIN_ADX, ">="),
    "structure_ok": ("structure_strength", HARD_MIN_STRUCTURE_STRENGTH, ">="),
    "entry_zone_ok": ("entry_score", ENTRY_ZONE_SCORE_MIN, ">="),
    "quality_ok": ("quality", QUALITY_GATE_MIN_SCORE, ">="),
    "consensus_ok": ("consensus", CONSENSUS_MINIMUM_SCORE, ">="),
    "confidence_ok": ("confidence", CONFIDENCE_GATE_MIN_SCORE, ">="),
}

_HEALTH_LEVELS = [
    (85, "Excelente"),
    (70, "Boa"),
    (50, "Neutra"),
    (30, "Ruim"),
    (0, "Critica"),
]


def _classify_health(score: float) -> str:
    for floor, label in _HEALTH_LEVELS:
        if score >= floor:
            return label
    return "Critica"


def _safe_avg(vals: List[float]) -> float:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def _safe_avg_nonzero(vals: List[float]) -> float:
    vals = [v for v in vals if v is not None and v > 0]
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def _scale_quality(val: float) -> float:
    if val > 1:
        return val
    return val * 100


# --- Bloco 0: Resumo do Ciclo (RFC V6.7) ------------------------------------

def build_cycle_summary(report) -> Dict[str, Any]:
    """RFC V6.7: bloco RESUMO DO CICLO.

    Todas as contagens e medias usam exclusivamente report.decisions
    (ativos que chegaram ao DecisionEngine), nunca report.total_assets.
    Inclui metricas de eficiencia do scanner.
    """
    decisions = report.decisions
    funnel = report.pipeline_funnel or {}

    if not decisions:
        return {"mensagem": "Sem ativos suficientes para gerar estatisticas do ciclo."}

    total = len(decisions)
    approved = sum(1 for d in decisions if d.get("approved"))
    rejected = total - approved

    validas = report.total_assets
    escaneadas = total

    # Pipeline funnel: candles = passaram carregamento,
    # decision_engine = chegaram ao motor de decisao
    liquidez = funnel.get("candles", 0) or validas
    fluxo = funnel.get("decision_engine", 0) or total

    # Medias dos scores (escala 0-100)
    scores = [_scale_quality(d.get("quality", 0)) for d in decisions]
    qualities = [_scale_quality(d.get("quality_score", d.get("quality", 0))) for d in decisions]
    confidences = [_scale_quality(d.get("confidence", 0)) for d in decisions]

    eficiencia = round(escaneadas / validas * 100, 1) if validas > 0 else 0.0
    taxa_aprovacao = round(approved / escaneadas * 100, 1) if escaneadas > 0 else 0.0
    taxa_rejeicao = round(rejected / escaneadas * 100, 1) if escaneadas > 0 else 0.0

    return {
        "exchange": report.exchange,
        "validas": validas,
        "liquidez": liquidez,
        "fluxo": fluxo,
        "escaneadas": escaneadas,
        "aprovadas": approved,
        "reprovadas": rejected,
        "taxa_aprovacao": taxa_aprovacao,
        "score_medio": _safe_avg(scores),
        "qualidade_media": _safe_avg(qualities),
        "conviccao_media": _safe_avg(confidences),
        "eficiencia_scanner": eficiencia,
        "taxa_conversao": taxa_aprovacao,
        "taxa_rejeicao": taxa_rejeicao,
    }


# --- Bloco 1: Resumo do Scanner ---------------------------------------------

def build_scanner_summary(report) -> Dict[str, Any]:
    health = report.health or {}
    return {
        "exchange": report.exchange,
        "candles": health.get("candles", 0),
        "tempo_ms": report.duration_ms,
        "quantidade_moedas": report.total_assets,
        "erros": len(report.bugs),
        "api_status": health.get("api", 0),
        "cycle_number": report.cycle_number,
    }


# --- Bloco 2: Funil granular --------------------------------------------------

def build_granular_funnel(decisions: List[Dict]) -> List[Dict[str, Any]]:
    """Funil real: 'quantidade' = decisoes que PASSARAM o gate (flag is True),
    nao apenas as que chegaram a ser avaliadas. O DecisionEngine sai no
    primeiro gate reprovado (early return), entao contar apenas 'True'
    reflete corretamente quantas decisoes seguiram para o proximo estagio."""
    total = len(decisions)
    stages = []
    remaining = total
    for label, flag in GATE_ORDER:
        passed = sum(1 for d in decisions if d.get(flag) is True)
        passed = min(passed, remaining)
        loss = remaining - passed
        stages.append({"estagio": label, "quantidade": passed, "perda": -loss})
        remaining = passed
    aprovados = sum(1 for d in decisions if d.get("approved"))
    stages.append({"estagio": "Aprovados", "quantidade": aprovados, "perda": -(remaining - aprovados)})
    return stages


# --- Bloco 3: Top quase-aprovados --------------------------------------------

def _delta_to_pass(decision: Dict) -> Optional[Tuple[str, float]]:
    """Acha o gate mais proximo de passar entre os que reprovaram (menor delta)."""
    best = None
    for label, flag in GATE_ORDER:
        if decision.get(flag) is False:
            field_name, threshold, _ = _GATE_THRESHOLDS.get(flag, (None, None, None))
            if field_name is None:
                continue
            value = decision.get(field_name)
            if value is None:
                continue
            delta = threshold - value
            if best is None or delta < best[1]:
                best = (label, delta)
    return best


def build_top_near_approved(decisions: List[Dict], min_count: int = 10) -> List[Dict[str, Any]]:
    rejected = [d for d in decisions if not d.get("approved")]
    ranked = sorted(rejected, key=lambda d: d.get("quality", 0.0), reverse=True)
    result = []
    for d in ranked[:min_count]:
        near = _delta_to_pass(d)
        faltou = f"+{round(near[1] * 100, 1)} {near[0]}" if near else d.get("reject_reason", "")
        result.append({
            "ativo": d.get("symbol"),
            "score": round(d.get("quality", 0.0) * 100, 1),
            "qualidade": round(d.get("quality_score", 0.0) * 100, 1),
            "confianca": round(d.get("confidence", 0.0) * 100, 1),
            "timing": round(d.get("entry_score", 0.0) * 100, 1),
            "categoria": d.get("classification_label", "reprovado"),
            "faltou": faltou,
        })
    return result


# --- Bloco 4: Diagnostico por ativo ------------------------------------------

def build_per_asset_diagnostics(decisions: List[Dict]) -> List[Dict[str, Any]]:
    out = []
    for d in decisions:
        checklist = {label: d.get(flag) for label, flag in GATE_ORDER}
        out.append({
            "ativo": d.get("symbol"),
            "timeframe": d.get("timeframe"),
            "checklist": checklist,
            "categoria": d.get("classification_label", "reprovado"),
            "tp": d.get("take_profit_1"),
            "status": "APROVADO" if d.get("approved") else "REPROVADO",
            "motivo_principal": d.get("reject_reason", ""),
        })
    return out


# --- Bloco 5: Ranking dos bloqueadores ----------------------------------------

def build_blocker_ranking(decisions: List[Dict]) -> List[Dict[str, Any]]:
    rejected = [d for d in decisions if not d.get("approved")]
    total_rejected = len(rejected)
    if total_rejected == 0:
        return []
    counts: Dict[str, int] = {}
    for d in rejected:
        blocker = None
        for label, flag in GATE_ORDER:
            if d.get(flag) is False:
                blocker = label
                break
        if blocker is None:
            blocker = d.get("reject_reason") or "Outro"
        counts[blocker] = counts.get(blocker, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {"motivo": name, "quantidade": count, "percentual": round(count / total_rejected * 100, 1)}
        for name, count in ranked
    ]


# --- Bloco 6: Saude do mercado -------------------------------------------------

def build_market_health(decisions: List[Dict], report) -> Dict[str, Any]:
    if not decisions:
        health_score = (report.health or {}).get("health_score", 0.0)
        return {"classificacao": _classify_health(health_score), "health_score": health_score}

    def _avg(field_name):
        vals = [d.get(field_name, 0.0) for d in decisions if d.get(field_name) is not None]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    avg_liquidity = _avg("liquidity_score")
    avg_risk = _avg("risk_score")
    avg_market = _avg("market_score")
    health_score = (report.health or {}).get("health_score", 0.0)
    return {
        "liquidez_media": avg_liquidity,
        "risco_medio": avg_risk,
        "mercado_medio": avg_market,
        "health_score": health_score,
        "classificacao": _classify_health(health_score),
    }


# --- Bloco 7: Recomendacao automatica ------------------------------------------

def build_auto_recommendation(blocker_ranking: List[Dict], market_health: Dict) -> str:
    if not blocker_ranking:
        return "Scanner saudavel. Nenhum bloqueador dominante neste ciclo."
    top = blocker_ranking[0]
    saude = market_health.get("classificacao", "Neutra")
    return (
        f"Mercado {saude.lower()}. Maior gargalo: {top['motivo']} "
        f"({top['percentual']:.1f}% das reprovacoes). "
        "Os sinais estao sendo bloqueados principalmente por esse criterio."
    )


# --- Bloco 8: Resumo executivo -------------------------------------------------

def build_executive_summary(scanner_summary: Dict, market_health: Dict, blocker_ranking: List[Dict]) -> str:
    lines = [
        f"O scanner analisou {scanner_summary['quantidade_moedas']} ativos "
        f"na exchange {scanner_summary['exchange']}.",
        f"O mercado apresenta condicao {market_health.get('classificacao', 'Neutra')} "
        f"(health score {market_health.get('health_score', 0):.1f}).",
    ]
    if blocker_ranking:
        top = blocker_ranking[0]
        lines.append(f"O principal gargalo esta em {top['motivo']} "
                     f"({top['percentual']:.1f}% das reprovacoes).")
    else:
        lines.append("Nenhum bloqueador dominante identificado neste ciclo.")
    lines.append(f"Erros detectados no ciclo: {scanner_summary['erros']}.")
    return "\n".join(lines[:5])


# --- Bloco 9: Estatisticas gerais ----------------------------------------------

def build_general_stats(decisions: List[Dict], report) -> Dict[str, Any]:
    """RFC V6.7: todas as medias usam decisions (escaneados), nao total_assets."""
    total = len(decisions)
    approved = sum(1 for d in decisions if d.get("approved"))
    rejected = total - approved
    duration_min = (report.duration_ms / 1000.0 / 60.0) if report.duration_ms else 0.0
    ativos_por_min = round(total / duration_min, 2) if duration_min > 0 else 0.0

    tier_counts: Dict[str, int] = {}
    for d in decisions:
        tier = (d.get("classification_label") or "reprovado").upper()
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    return {
        "taxa_aprovacao": round(approved / total * 100, 2) if total else 0.0,
        "taxa_reprovacao": round(rejected / total * 100, 2) if total else 0.0,
        "tempo_medio_por_ativo_ms": round(report.duration_ms / total, 1) if total else 0.0,
        "ativos_por_minuto": ativos_por_min,
        "distribuicao_categorias": tier_counts,
    }


# --- Bloco 10: Market Statistics (RFC V6.7) -----------------------------------

def build_market_statistics(report) -> Dict[str, Any]:
    """RFC V6.7: medias de RSI, ADX, RVOL, ATR calculadas exclusivamente
    sobre os ativos presentes em report.decisions (escaneados).

    Os dados brutos de indicadores vêm de report.indicators, que contém
    dicts {pair: {rsi, adx, rvol, atr_percent, ...}} registrados em
    main.py para cada ativo que carregou candles. Esta função filtra
    apenas os pares que tambem estao em report.decisions.
    """
    decisions = report.decisions
    if not decisions:
        return {"mensagem": "Sem ativos suficientes para gerar estatisticas do ciclo."}

    symbols = [d.get("symbol") for d in decisions if d.get("symbol")]
    indicators = report.indicators or {}
    relevant = {sym: indicators[sym] for sym in symbols if sym in indicators}

    if not relevant:
        return {"mensagem": "Sem dados de indicadores para os ativos escaneados."}

    return {
        "rsi_medio": _safe_avg_nonzero([ind.get("rsi", 0) for ind in relevant.values()]),
        "adx_medio": _safe_avg_nonzero([ind.get("adx", 0) for ind in relevant.values()]),
        "rvol_medio": _safe_avg_nonzero([ind.get("rvol", 0) for ind in relevant.values()]),
        "atr_medio": _safe_avg_nonzero([ind.get("atr_percent", 0) for ind in relevant.values()]),
    }


# --- Bloco 11: Flow Trace (RFC V26.2) -----------------------------------------

# (rotulo exibido, chave em report.pipeline_funnel; "" = usa total_assets)
FLOW_STAGES: List[Tuple[str, str]] = [
    ("Scanner", ""),
    ("Candles/API", "candles"),
    ("Indicadores", "indicadores"),
    ("Estrutura", "estrutura"),
    ("Entry Zone", "entry_zone"),
    ("Consensus", "consensus"),
    ("Quality Gate", "quality_gate"),
    ("Decision Engine", "decision_engine"),
    ("Aprovados", "aprovados"),
]


def build_flow_trace(report) -> List[Dict[str, Any]]:
    """RFC V26.2: rastreamento por estagio do pipeline. Reaproveita
    exclusivamente report.pipeline_funnel e report.total_assets, ja
    preenchidos por main.py/DiagnosticEngine a cada ciclo — nenhum dado
    novo e coletado, nenhuma alteracao em Scanner ou Decision Engine."""
    funnel = report.pipeline_funnel or {}
    total_assets = report.total_assets or 0

    trace: List[Dict[str, Any]] = []
    previous = total_assets
    for label, key in FLOW_STAGES:
        if not key:
            count = total_assets
            status = "executado" if total_assets > 0 else "nao_executado"
        else:
            count = funnel.get(key)
            if count is None:
                status, count = "nao_executado", 0
            elif label == "Aprovados":
                status = "aprovado" if count > 0 else "bloqueado"
            elif count <= 0 and previous > 0:
                status = "bloqueado"
            elif count < previous:
                status = "parcialmente_bloqueado"
            else:
                status = "executado"
        trace.append({"estagio": label, "quantidade": count, "status": status})
        previous = count
    return trace


def _interruption_point(flow_trace: List[Dict[str, Any]]) -> str:
    """Primeiro estagio totalmente bloqueado (quantidade cai a 0) — usado
    no resumo executivo para explicar onde o pipeline foi interrompido."""
    for stage in flow_trace:
        if stage["status"] == "bloqueado":
            return stage["estagio"]
    return ""


def _build_metadata(report) -> Dict[str, Any]:
    return {
        "cycle_number": report.cycle_number,
        "exchange": report.exchange,
        "duration_ms": report.duration_ms,
        "total_assets": report.total_assets,
        "decisions_count": len(report.decisions or []),
    }


# --- Orquestrador -------------------------------------------------------------

def build_advanced_report(report) -> Dict[str, Any]:
    """Ponto de entrada unico: recebe o DiagnosticReport do ciclo (com
    report.decisions ja populado por main.py) e devolve sempre o mesmo
    conjunto de chaves — com ou sem candidatos no ciclo. Somente leitura —
    nenhum campo de Signal/SignalDecision/ScannerScore e alterado ou
    recalculado.

    RFC V26.2: contrato estavel. Nunca omite chaves; quando decisions esta
    vazio, o resumo executivo reflete o cenario real (pipeline interrompido
    antes do Decision Engine), nunca uma mensagem generica de "saudavel"."""
    decisions = report.decisions
    flow_trace = build_flow_trace(report)
    metadata = _build_metadata(report)
    timestamp = datetime.now(timezone.utc).isoformat()

    if not decisions:
        scanner_summary = build_scanner_summary(report)
        market_health = build_market_health(decisions, report)
        interruption = _interruption_point(flow_trace)
        executive_summary = (
            "O ciclo foi encerrado sem candidatos no Decision Engine. "
            f"{scanner_summary.get('quantidade_moedas', 0)} ativos foram escaneados na "
            f"exchange {scanner_summary.get('exchange', '?')}, filtrados antes desta etapa"
            + (f" (interrupcao em: {interruption})" if interruption else "")
            + ". Nenhuma decisao operacional foi executada."
        )
        return {
            "resumo_ciclo": {"mensagem": "Sem ativos suficientes para gerar estatisticas do ciclo."},
            "resumo_scanner": scanner_summary,
            "funil_granular": [],
            "top_quase_aprovados": [],
            "diagnostico_por_ativo": [],
            "ranking_bloqueadores": [],
            "saude_mercado": market_health,
            "recomendacao_automatica": (
                "Nenhum candidato chegou ao Decision Engine neste ciclo."
                + (f" Interrupcao em: {interruption}." if interruption else "")
            ),
            "resumo_executivo": executive_summary,
            "estatisticas_gerais": {
                "taxa_aprovacao": 0.0, "taxa_reprovacao": 0.0,
                "tempo_medio_por_ativo_ms": 0.0, "ativos_por_minuto": 0.0,
                "distribuicao_categorias": {},
            },
            "mercado_estatisticas": {"mensagem": "Sem ativos suficientes para gerar estatisticas do ciclo."},
            "flow_trace": flow_trace,
            "metadata": metadata,
            "timestamp": timestamp,
        }

    cycle_summary = build_cycle_summary(report)
    scanner_summary = build_scanner_summary(report)
    funnel = build_granular_funnel(decisions)
    near_approved = build_top_near_approved(decisions)
    per_asset = build_per_asset_diagnostics(decisions)
    blockers = build_blocker_ranking(decisions)
    market_health = build_market_health(decisions, report)
    recommendation = build_auto_recommendation(blockers, market_health)
    executive_summary = build_executive_summary(scanner_summary, market_health, blockers)
    stats = build_general_stats(decisions, report)
    market_stats = build_market_statistics(report)

    return {
        "resumo_ciclo": cycle_summary,
        "resumo_scanner": scanner_summary,
        "funil_granular": funnel,
        "top_quase_aprovados": near_approved,
        "diagnostico_por_ativo": per_asset,
        "ranking_bloqueadores": blockers,
        "saude_mercado": market_health,
        "recomendacao_automatica": recommendation,
        "resumo_executivo": executive_summary,
        "estatisticas_gerais": stats,
        "mercado_estatisticas": market_stats,
        "flow_trace": flow_trace,
        "metadata": metadata,
        "timestamp": timestamp,
    }
