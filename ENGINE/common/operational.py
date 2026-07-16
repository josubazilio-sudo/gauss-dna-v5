import logging
from typing import Dict, List, Optional, Tuple

from ENGINE.scanner.scanner_config import (
    EXPECTANCY_WEIGHTS,
    PENALTY_ATR_ELEVADO, PENALTY_ESTRUTURA_FRACA,
    PENALTY_LIQUIDEZ_INSUFICIENTE, PENALTY_RVOL_BAIXO,
    PENALTY_CONTRA_TENDENCIA, PENALTY_KALMAN_CONTRARIO,
    PENALTY_PROXIMO_RESISTENCIA, PENALTY_PROXIMO_SUPORTE,
    PENALTY_MERCADO_LATERAL, PENALTY_SPREAD_ELEVADO,
    PENALTY_BAIXO_CONSENSO,
    CLASSIFICATION_RANGES,
    VOTE_WEIGHTS, COHERENCE_RANGES,
    CONSENSUS_MINIMUM_SCORE, VOTE_MIN_CONCORDANCE_PCT,
    QUALITY_GATE_MIN_SCORE, CONFIDENCE_GATE_MIN_SCORE,
)
from ENGINE.scanner.scanner_types import Penalty
from ENGINE.common.score_normalizer import scale_1_to_100

log = logging.getLogger(__name__)

OVERALL_SCORE_WEIGHTS = {
    "quality": 0.20,
    "confidence": 0.15,
    "consensus": 0.12,
    "structure": 0.10,
    "liquidity": 0.10,
    "momentum": 0.10,
    "trend_alignment": 0.08,
    "kalman_alignment": 0.08,
    "risk_inverted": 0.07,
}

_TIER_EMOJI = {
    "diamante": "\U0001f48e",
    "platina": "\U0001f4a0",
    "ouro": "\U0001f3c6",
    "prata": "\U0001f948",
    "bronze": "\U0001f949",
    "reprovado": "❌",
}


def _normalize(val: float) -> float:
    if val > 1:
        return val / 100.0
    return val


def _derive_tier(overall_score: float) -> Tuple[str, str]:
    """V18.3: classifica (0-100) usando CLASSIFICATION_RANGES com PLATINA."""
    for tier_name in ('DIAMANTE', 'PLATINA', 'OURO', 'PRATA', 'BRONZE'):
        cfg = CLASSIFICATION_RANGES[tier_name]
        if cfg['min'] <= overall_score <= cfg['max']:
            label = tier_name.lower()
            return label, tier_name
    return "reprovado", "REPROVADO"


def _penalty_impact(weight: float, base_score: float = 1.0) -> int:
    """Calcula impacto numerico (0-100) de uma penalizacao no score."""
    return -int(round(weight * 100 * base_score))


def compute_penalties(signal_data: dict) -> List[Penalty]:
    """V19.1: penalizacoes detalhadas com origem, peso e impacto."""
    penalties = []
    atr = signal_data.get("atr_value", signal_data.get("atr", 0))
    entry = signal_data.get("entry_price", 0)
    atr_pct = (atr / entry * 100) if entry > 0 and atr > 0 else 0
    if atr_pct > 3.0:
        impact = _penalty_impact(PENALTY_ATR_ELEVADO["weight"])
        penalties.append(Penalty(
            reason=f"ATR elevado ({atr_pct:.1f}%)",
            weight=PENALTY_ATR_ELEVADO["weight"],
            source="risk_manager",
        ))

    structure = signal_data.get("structural_score", signal_data.get("structure_strength", 0))
    structure = _normalize(structure)
    if structure < 0.4:
        impact = _penalty_impact(PENALTY_ESTRUTURA_FRACA["weight"])
        penalties.append(Penalty(
            reason=f"Estrutura fraca ({structure:.2f})",
            weight=PENALTY_ESTRUTURA_FRACA["weight"],
            source="scanner_structure",
        ))

    liquidity = signal_data.get("liquidity_score", 0)
    liquidity = _normalize(liquidity)
    if liquidity < 0.5:
        impact = _penalty_impact(PENALTY_LIQUIDEZ_INSUFICIENTE["weight"])
        penalties.append(Penalty(
            reason=f"Liquidez insuficiente ({liquidity:.2f})",
            weight=PENALTY_LIQUIDEZ_INSUFICIENTE["weight"],
            source="market_liquidity",
        ))

    rvol = signal_data.get("rvol", 0)
    if 0 < rvol < 1.0:
        penalties.append(Penalty(
            reason=f"RVOL baixo ({rvol:.2f}x)",
            weight=PENALTY_RVOL_BAIXO["weight"],
            source="market_momentum",
        ))

    trend = (signal_data.get("trend", "") or "").lower()
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    direction = (signal_data.get("direction", "") or "").upper()
    is_long = direction in ("LONG", "BUY")
    trend_uptrend = trend in ("uptrend", "alta")
    trend_downtrend = trend in ("downtrend", "baixa")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir

    if is_long and trend_downtrend:
        impact = _penalty_impact(PENALTY_CONTRA_TENDENCIA["weight"])
        penalties.append(Penalty(
            reason=f"Contra tendência (LONG em {trend})",
            weight=PENALTY_CONTRA_TENDENCIA["weight"],
            source="market_trend",
        ))
    if not is_long and trend_uptrend:
        impact = _penalty_impact(PENALTY_CONTRA_TENDENCIA["weight"])
        penalties.append(Penalty(
            reason=f"Contra tendência (SHORT em {trend})",
            weight=PENALTY_CONTRA_TENDENCIA["weight"],
            source="market_trend",
        ))
    if is_long and kalman_down:
        penalties.append(Penalty(
            reason=f"Kalman contrário (LONG com Kalman DOWN)",
            weight=PENALTY_KALMAN_CONTRARIO["weight"],
            source="kalman",
        ))
    if not is_long and kalman_up:
        penalties.append(Penalty(
            reason=f"Kalman contrário (SHORT com Kalman UP)",
            weight=PENALTY_KALMAN_CONTRARIO["weight"],
            source="kalman",
        ))

    regime = (signal_data.get("regime", "") or "").lower()
    if regime in ("ranging", "lateral"):
        penalties.append(Penalty(
            reason="Mercado lateral",
            weight=PENALTY_MERCADO_LATERAL["weight"],
            source="market_regime",
        ))

    spread = signal_data.get("spread", 0)
    if spread > 0.0005:
        penalties.append(Penalty(
            reason=f"Spread elevado ({spread:.4f})",
            weight=PENALTY_SPREAD_ELEVADO["weight"],
            source="market_liquidity",
        ))

    consensus = signal_data.get("consensus_score", signal_data.get("consensus", 0))
    consensus = _normalize(consensus)
    if 0 < consensus < 0.6:
        penalties.append(Penalty(
            reason=f"Baixo consenso ({consensus:.2f})",
            weight=PENALTY_BAIXO_CONSENSO["weight"],
            source="consensus_engine",
        ))

    return penalties


def compute_confluence_score(signal_data: dict) -> float:
    """V19.1: Score de Confluencia Institucional (0-100).

    Mede concordancia entre Trend, Kalman, Estrutura, Momentum,
    Liquidez, Volume, Consenso, Fluxo.
    Quanto maior a confluencia, maior a confiabilidade.
    """
    trend = (signal_data.get("trend", "") or "").lower()
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    direction = (signal_data.get("direction", "") or "").upper()
    structure = _normalize(signal_data.get("structural_score", 0))
    momentum = _normalize(signal_data.get("momentum_score", 0))
    liquidity = _normalize(signal_data.get("liquidity_score", 0))
    consensus = _normalize(signal_data.get("consensus_score", signal_data.get("consensus", 0)))
    flow = _normalize(signal_data.get("flow_score", 0))
    rvol = signal_data.get("rvol", 0)

    is_long = direction in ("LONG", "BUY")
    trend_uptrend = trend in ("uptrend", "alta")
    trend_downtrend = trend in ("downtrend", "baixa")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir

    aligned = 0
    total = 8

    if (is_long and trend_uptrend) or (not is_long and trend_downtrend):
        aligned += 1
    if (is_long and kalman_up) or (not is_long and kalman_down):
        aligned += 1
    if structure >= 0.6:
        aligned += 1
    if momentum >= 0.5:
        aligned += 1
    if liquidity >= 0.6:
        aligned += 1
    if rvol >= 1.5:
        aligned += 1
    if consensus >= 0.65:
        aligned += 1
    if flow >= 0.3:
        aligned += 1

    return round(aligned / total * 100, 1)


def compute_risk_decomposition(signal_data: dict) -> dict:
    """V19.1: Decomposicao do risco em componentes.

    Retorna: risco_estrutural, risco_tendencia, risco_volatilidade,
    risco_liquidez, risco_estatistico, risco_total (0-100).
    """
    risk = _normalize(signal_data.get("risk_score", 0))
    structure = _normalize(signal_data.get("structural_score", 0))
    trend = (signal_data.get("trend", "") or "").lower()
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    direction = (signal_data.get("direction", "") or "").upper()
    atr = signal_data.get("atr_value", signal_data.get("atr", 0))
    entry = signal_data.get("entry_price", 0)
    liquidity = _normalize(signal_data.get("liquidity_score", 0))
    momentum = _normalize(signal_data.get("momentum_score", 0))
    consensus = _normalize(signal_data.get("consensus_score", signal_data.get("consensus", 0)))

    is_long = direction in ("LONG", "BUY")
    trend_uptrend = trend in ("uptrend", "alta")
    trend_downtrend = trend in ("downtrend", "baixa")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir

    risco_estrutural = round((1.0 - structure) * 100, 1)

    contra_tendencia = (is_long and trend_downtrend) or (not is_long and trend_uptrend)
    kalman_contra = (is_long and kalman_down) or (not is_long and kalman_up)
    risco_tendencia = round((0.5 if contra_tendencia else 0.0) + (0.5 if kalman_contra else 0.0), 1)

    atr_pct = (atr / entry * 100) if entry > 0 and atr > 0 else 2.0
    risco_volatilidade = round(min(atr_pct / 5.0 * 100, 100), 1)

    risco_liquidez = round((1.0 - liquidity) * 100, 1)

    risco_estatistico = round((1.0 - ((momentum + consensus) / 2.0)) * 100, 1)

    risco_total = round(min(
        risco_estrutural * 0.25 + risco_tendencia * 0.25 +
        risco_volatilidade * 0.20 + risco_liquidez * 0.15 +
        risco_estatistico * 0.15,
        100.0
    ), 1)

    return {
        "risco_estrutural": risco_estrutural,
        "risco_tendencia": risco_tendencia,
        "risco_volatilidade": risco_volatilidade,
        "risco_liquidez": risco_liquidez,
        "risco_estatistico": risco_estatistico,
        "risco_total": risco_total,
    }


def compute_main_reason(signal_data: dict) -> str:
    """V19.1: Gera resumo automatico do motivo principal de aprovacao.

    RFC V26.7: lia signal_data["patterns"] (uma lista que SignalDecision.to_dict()
    nunca preenche — o dict so tem "bos"/"choch"/"fvg" como contagens inteiras
    e "selected_order_block" como string). Isso fazia com que "BOS confirmado"/
    "CHoCH confirmado" nunca aparecessem em main_reason, mesmo com BOS/CHoCH
    reais detectados — e o Final Validation ("Mercado lateral + expectativa
    alta sem rompimento") depende exatamente desse texto para nao bloquear
    sinais com rompimento confirmado. Corrigido para ler os campos reais."""
    reasons = []
    if signal_data.get("bos", 0):
        reasons.append("BOS confirmado")
    if signal_data.get("choch", 0):
        reasons.append("CHoCH confirmado")
    if signal_data.get("selected_order_block"):
        reasons.append("Order Block detectado")
    if signal_data.get("fvg", 0):
        reasons.append("FVG identificado")

    trend = (signal_data.get("trend", "") or "").lower()
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    direction = (signal_data.get("direction", "") or "").upper()
    is_long = direction in ("LONG", "BUY")
    trend_uptrend = trend in ("uptrend", "alta")
    trend_downtrend = trend in ("downtrend", "baixa")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir

    if (is_long and trend_uptrend) or (not is_long and trend_downtrend):
        reasons.append("Tendência alinhada")
    if (is_long and kalman_up) or (not is_long and kalman_down):
        reasons.append("Kalman alinhado")

    rvol = signal_data.get("rvol", 0)
    if rvol >= 1.5:
        reasons.append("Volume institucional")
    elif rvol >= 1.0:
        reasons.append("Volume acima da média")

    if is_long and not trend_downtrend:
        reasons.append("Continuação institucional")
    elif not is_long and not trend_uptrend:
        reasons.append("Continuação institucional")

    if not reasons:
        return "Setup institucional aprovado"

    return " + ".join(reasons[:4])


def compute_overall_score(signal_data: dict) -> dict:
    """V19.1: indice geral com tier derivado do overall_score (nao do classification_label)."""
    quality = _normalize(signal_data.get("quality_score", signal_data.get("quality", 0)))
    confidence = _normalize(signal_data.get("confidence_score", signal_data.get("confidence", 0)))
    consensus = _normalize(signal_data.get("consensus_score", signal_data.get("consensus", 0)))
    structure = _normalize(signal_data.get("structural_score", 0))
    liquidity = _normalize(signal_data.get("liquidity_score", 0))
    momentum = _normalize(signal_data.get("momentum_score", 0))
    risk = _normalize(signal_data.get("risk_score", 0))
    trend = (signal_data.get("trend", "") or "").lower()
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    direction = (signal_data.get("direction", "") or "").upper()

    is_long = direction in ("LONG", "BUY")
    trend_uptrend = trend in ("uptrend", "alta")
    trend_downtrend = trend in ("downtrend", "baixa")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir

    trend_align = 1.0 if (is_long and trend_uptrend) or (not is_long and trend_downtrend) else (
        0.5 if trend in ("ranging", "lateral") else 0.3
    )
    kalman_align = 1.0 if (is_long and kalman_up) or (not is_long and kalman_down) else (
        0.5 if kalman_dir in ("NEUTRAL", "UNKNOWN", "") else 0.3
    )
    risk_inverted = 1.0 - risk

    components = {
        "quality": quality,
        "confidence": confidence,
        "consensus": consensus,
        "structure": structure,
        "liquidity": liquidity,
        "momentum": momentum,
        "trend_alignment": trend_align,
        "kalman_alignment": kalman_align,
        "risk_inverted": risk_inverted,
    }

    raw_score = sum(
        min(v, 1.0) * OVERALL_SCORE_WEIGHTS[k]
        for k, v in components.items()
    )
    overall = min(raw_score * 100.0, 100.0)

    label, tier = _derive_tier(overall)
    tier_emoji = _TIER_EMOJI.get(label, "⭐")

    scanner_label = (signal_data.get("classification_label") or "reprovado").lower()
    scanner_tier = scanner_label.upper()
    if scanner_tier != tier:
        log.warning(
            "Classificacao divergente: scanner %s vs overall_score %.1f -> %s",
            scanner_tier, overall, tier,
        )

    bar_filled = round(overall / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    return {
        "overall_score": round(overall, 1),
        "overall_bar": f"{bar}",
        "overall_tier": tier,
        "overall_tier_emoji": tier_emoji,
        "components": {k: round(v * 100, 1) for k, v in components.items()},
    }


def compute_probability(signal_data: dict) -> dict:
    """V18.3: probabilidade institucional com 10 fatores.

    Nao deriva apenas do score. Considera: Confianca, Consenso, Qualidade,
    Regime, Liquidez, Kalman, Estrutura, Fluxo, Convergencia, RVOL.
    Retorna: probability (0-100), level (Muito Baixa a Muito Alta).
    """
    confidence = _normalize(signal_data.get("confidence_score", signal_data.get("confidence", 0)))
    consensus = _normalize(signal_data.get("consensus_score", signal_data.get("consensus", 0)))
    quality = _normalize(signal_data.get("quality_score", signal_data.get("quality", 0)))
    liquidity = _normalize(signal_data.get("liquidity_score", 0))
    structure = _normalize(signal_data.get("structural_score", 0))
    flow = _normalize(signal_data.get("flow_score", 0))
    rvol = signal_data.get("rvol", 0)
    regime = (signal_data.get("regime", "") or "").lower()
    direction = (signal_data.get("direction", "") or "").upper()
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    trend = (signal_data.get("trend", "") or "").lower()

    is_long = direction in ("LONG", "BUY")
    trend_up = trend in ("uptrend", "alta")
    trend_down = trend in ("downtrend", "baixa")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir

    trend_align = 1.0 if (is_long and trend_up) or (not is_long and trend_down) else (
        0.5 if trend in ("ranging", "lateral") else 0.3
    )
    kalman_align = 1.0 if (is_long and kalman_up) or (not is_long and kalman_down) else (
        0.5 if kalman_dir in ("NEUTRAL", "UNKNOWN", "") else 0.3
    )

    rvol_norm = min(rvol / 2.0, 1.0) if rvol > 0 else 0.0
    lateral_penalty = 0.85 if regime in ("ranging", "lateral") else 1.0

    raw = (
        confidence * 0.15 +
        consensus * 0.14 +
        quality * 0.13 +
        trend_align * 0.12 +
        kalman_align * 0.11 +
        liquidity * 0.10 +
        structure * 0.09 +
        flow * 0.07 +
        rvol_norm * 0.05 +
        0.04  # convergencia base
    ) * lateral_penalty * 100.0

    prob = max(0.0, min(raw, 100.0))

    if prob >= 85:
        level = "Muito Alta"
    elif prob >= 70:
        level = "Alta"
    elif prob >= 55:
        level = "Moderada"
    elif prob >= 40:
        level = "Baixa"
    else:
        level = "Muito Baixa"

    return {"probability": round(prob, 1), "level": level}


def compute_coherence_audit(signal_data: dict) -> dict:
    """V18.3: auditoria de coerencia entre modulos.

    Retorna dict com status (OK/CONFLITO) para cada modulo e resultado final.
    """
    direction = (signal_data.get("direction", "") or "").upper()
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    trend = (signal_data.get("trend", "") or "").lower()
    regime = (signal_data.get("regime", "") or "").lower()
    flow = _normalize(signal_data.get("flow_score", 0))
    liquidity = _normalize(signal_data.get("liquidity_score", 0))
    structure = _normalize(signal_data.get("structural_score", 0))
    momentum = _normalize(signal_data.get("momentum_score", 0))
    consensus = _normalize(signal_data.get("consensus_score", signal_data.get("consensus", 0)))

    is_long = direction in ("LONG", "BUY")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir
    trend_up = trend in ("uptrend", "alta")
    trend_down = trend in ("downtrend", "baixa")

    checks = {}

    kalman_ok = (is_long and kalman_up) or (not is_long and kalman_down) or kalman_dir in ("NEUTRAL", "UNKNOWN", "")
    checks["kalman"] = "OK" if kalman_ok else "CONFLITO"

    trend_ok = (is_long and trend_up) or (not is_long and trend_down) or trend in ("ranging", "lateral", "")
    checks["regime"] = "OK" if trend_ok else "CONFLITO"

    checks["fluxo"] = "OK" if flow >= 0.3 else "BAIXO"
    checks["liquidez"] = "OK" if liquidity >= 0.6 else "BAIXA"
    checks["estrutura"] = "OK" if structure >= 0.4 else "FRACA"
    checks["momentum"] = "OK" if momentum >= 0.5 else "BAIXO"
    checks["consenso"] = "OK" if consensus >= 0.55 else "BAIXO"

    conflitos = [k for k, v in checks.items() if v != "OK"]
    gravidade = len(conflitos)

    if gravidade == 0:
        resultado = "COERENTE"
    elif gravidade <= 2:
        resultado = "PENALIZACAO"
    else:
        resultado = "REJEITAR"

    return {
        "modulos": checks,
        "conflitos": conflitos,
        "gravidade": gravidade,
        "resultado": resultado,
    }


def compute_institutional_coherence_score(signal_data: dict) -> dict:
    """V18.4: Institutional Coherence Score (0-100), independente do Overall Score.

    Mede apenas a consistencia entre todos os modulos.
    """
    direction = (signal_data.get("direction", "") or "").upper()
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    trend = (signal_data.get("trend", "") or "").lower()
    regime = (signal_data.get("regime", "") or "").lower()
    flow = _normalize(signal_data.get("flow_score", 0))
    liquidity = _normalize(signal_data.get("liquidity_score", 0))
    structure = _normalize(signal_data.get("structural_score", 0))
    momentum = _normalize(signal_data.get("momentum_score", 0))
    consensus = _normalize(signal_data.get("consensus_score", signal_data.get("consensus", 0)))
    quality = _normalize(signal_data.get("quality_score", signal_data.get("quality", 0)))
    confidence = _normalize(signal_data.get("confidence_score", signal_data.get("confidence", 0)))
    # BUG FIX: SignalDecision.to_dict() nao tem campo "patterns" (so
    # contadores bos/choch) — a checagem anterior sempre avaliava str([]),
    # zerando este componente para todo sinal. Ver
    # RFC_FIX_COHERENCE_SCORE_CAMPOS_AUSENTES.md
    has_bos = (signal_data.get("bos", 0) or 0) > 0
    has_choch = (signal_data.get("choch", 0) or 0) > 0

    is_long = direction in ("LONG", "BUY")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir
    # BUG FIX: MarketRegime usa "trending_up"/"trending_down" (ver
    # ENGINE/market/market_types.py), nunca "uptrend"/"downtrend" —
    # a comparacao exata nunca batia para nenhum regime de tendencia real.
    trend_up = "up" in trend or "alta" in trend
    trend_down = "down" in trend or "baixa" in trend

    kalman_align = 1.0 if (is_long and kalman_up) or (not is_long and kalman_down) else (
        0.5 if kalman_dir in ("NEUTRAL", "UNKNOWN", "") else 0.0
    )
    trend_align = 1.0 if (is_long and trend_up) or (not is_long and trend_down) else (
        0.5 if trend in ("ranging", "lateral") else 0.0
    )
    flow_ok = 1.0 if flow >= 0.3 else (0.5 if flow >= 0.15 else 0.0)
    liquidity_ok = 1.0 if liquidity >= 0.6 else (0.5 if liquidity >= 0.45 else 0.0)
    structure_ok = 1.0 if structure >= 0.6 else (0.5 if structure >= 0.4 else 0.0)
    momentum_ok = 1.0 if momentum >= 0.5 else (0.5 if momentum >= 0.3 else 0.0)
    consensus_ok = 1.0 if consensus >= CONSENSUS_MINIMUM_SCORE else (0.5 if consensus >= CONSENSUS_MINIMUM_SCORE - 0.15 else 0.0)
    quality_ok = 1.0 if quality >= QUALITY_GATE_MIN_SCORE else 0.0
    confidence_ok = 1.0 if confidence >= CONFIDENCE_GATE_MIN_SCORE else 0.0
    pattern_ok = 1.0 if has_bos or has_choch else 0.0

    raw_scores = {
        "kalman": kalman_align * 100,
        "estrutura": structure_ok * 100,
        "consenso": consensus_ok * 100,
        "fluxo": flow_ok * 100,
        "regime": trend_align * 100,
        "liquidez": liquidity_ok * 100,
        "momentum": momentum_ok * 100,
        "qualidade": quality_ok * 100,
        "confianca": confidence_ok * 100,
        "padrao": pattern_ok * 100,
    }

    total_weight = sum(VOTE_WEIGHTS.values())
    weighted_sum = sum(raw_scores[k] * VOTE_WEIGHTS[k] for k in raw_scores)
    coherence = weighted_sum / total_weight if total_weight > 0 else 0

    for label, (lo, hi) in COHERENCE_RANGES.items():
        if lo <= coherence <= hi:
            level = label
            break
    else:
        level = "Rejeitar"

    return {
        "coherence_score": round(coherence, 1),
        "coherence_level": level,
        "modules": raw_scores,
        "vote_weights": dict(VOTE_WEIGHTS),
        "weighted_sum": round(weighted_sum, 1),
        "total_weight": total_weight,
    }


def compute_weighted_vote(signal_data: dict) -> dict:
    """V18.4: Votacao Institucional Ponderada.

    Cada modulo vota SIM/NAO com peso institucional.
    Exige 70% do peso total para aprovar direcao.
    """
    direction = (signal_data.get("direction", "") or "").upper()
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    trend = (signal_data.get("trend", "") or "").lower()
    regime = (signal_data.get("regime", "") or "").lower()
    flow = _normalize(signal_data.get("flow_score", 0))
    liquidity = _normalize(signal_data.get("liquidity_score", 0))
    structure = _normalize(signal_data.get("structural_score", 0))
    momentum = _normalize(signal_data.get("momentum_score", 0))
    consensus = _normalize(signal_data.get("consensus_score", signal_data.get("consensus", 0)))
    quality = _normalize(signal_data.get("quality_score", signal_data.get("quality", 0)))
    confidence = _normalize(signal_data.get("confidence_score", signal_data.get("confidence", 0)))
    # BUG FIX: ver RFC_FIX_COHERENCE_SCORE_CAMPOS_AUSENTES.md — mesmo bug
    # de compute_institutional_coherence_score (campo "patterns" nao
    # existe em SignalDecision.to_dict(), e "uptrend"/"downtrend" nunca
    # batem com MarketRegime.TRENDING_UP/TRENDING_DOWN).
    has_bos = (signal_data.get("bos", 0) or 0) > 0
    has_choch = (signal_data.get("choch", 0) or 0) > 0

    is_long = direction in ("LONG", "BUY")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir
    trend_up = "up" in trend or "alta" in trend
    trend_down = "down" in trend or "baixa" in trend

    votes = {
        "kalman": (is_long and kalman_up) or (not is_long and kalman_down) or kalman_dir in ("NEUTRAL", "UNKNOWN", ""),
        "estrutura": structure >= 0.4,
        "consenso": consensus >= 0.5,
        "fluxo": flow >= 0.3,
        "regime": (is_long and trend_up) or (not is_long and trend_down) or trend in ("ranging", "lateral", ""),
        "liquidez": liquidity >= 0.6,
        "momentum": momentum >= 0.5,
        "qualidade": quality >= 0.55,
        "confianca": confidence >= 0.55,
        "padrao": has_bos or has_choch,
    }

    yes_weight = sum(VOTE_WEIGHTS[k] for k, v in votes.items() if v)
    total_weight = sum(VOTE_WEIGHTS.values())
    concordance = (yes_weight / total_weight * 100) if total_weight > 0 else 0

    return {
        "votes": votes,
        "yes_weight": round(yes_weight, 1),
        "total_weight": total_weight,
        "concordance_pct": round(concordance, 1),
        "approved": concordance >= VOTE_MIN_CONCORDANCE_PCT,
    }


def compute_coarse_penalty_details(signal_data: dict) -> list:
    """V18.4: rastreabilidade — cada penalizacao com gate, peso, impacto."""
    details = []
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    direction = (signal_data.get("direction", "") or "").upper()
    is_long = direction in ("LONG", "BUY")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir
    regime = (signal_data.get("regime", "") or "").lower()
    structure = _normalize(signal_data.get("structural_score", 0))
    flow = _normalize(signal_data.get("flow_score", 0))
    consensus = _normalize(signal_data.get("consensus_score", signal_data.get("consensus", 0)))
    liquidity = _normalize(signal_data.get("liquidity_score", 0))
    momentum = _normalize(signal_data.get("momentum_score", 0))

    if (is_long and kalman_down) or (not is_long and kalman_up):
        details.append({"gate": "Kalman", "peso_perdido": 18, "motivo": f"Kalman {kalman_dir} incompativel com {direction}"})
    if structure < 0.4:
        details.append({"gate": "Estrutura", "peso_perdido": 8, "motivo": f"Estrutura {structure:.2f}"})
    if regime in ("ranging", "lateral"):
        details.append({"gate": "Mercado Lateral", "peso_perdido": 5, "motivo": "Regime lateral"})
    if flow < 0.3:
        details.append({"gate": "Fluxo", "peso_perdido": 4, "motivo": f"Fluxo {flow:.2f}"})
    if consensus < 0.55:
        details.append({"gate": "Consenso", "peso_perdido": 2, "motivo": f"Consenso {consensus:.2f}"})
    if liquidity < 0.5:
        details.append({"gate": "Liquidez", "peso_perdido": 3, "motivo": f"Liquidez {liquidity:.2f}"})
    if momentum < 0.4:
        details.append({"gate": "Momentum", "peso_perdido": 2, "motivo": f"Momentum {momentum:.2f}"})

    return details


def compute_conviction_level(confidence_score: float, quality_score: float, consensus_score: float) -> str:
    avg = (confidence_score + quality_score + consensus_score) / 3.0
    if avg >= 0.85:
        return "Muito Alta"
    if avg >= 0.70:
        return "Alta"
    if avg >= 0.55:
        return "Moderada"
    return "Baixa"


def compute_expectancy_level(signal_data: dict) -> str:
    """V19.1: expectativa com 5 niveis e fatores adicionais.

    Niveis: Muito Baixa, Baixa, Moderada, Alta, Muito Alta.
    Fatores: Qualidade, Confianca, Consenso, Estrutura, Liquidez,
    Momentum, Risco, Tendencia, Kalman, ATR, Volatilidade, RVOL,
    Multi-Timeframe (se disponivel).
    """
    quality = _normalize(signal_data.get("quality_score", signal_data.get("quality", 0)))
    confidence = _normalize(signal_data.get("confidence_score", signal_data.get("confidence", 0)))
    consensus = _normalize(signal_data.get("consensus_score", signal_data.get("consensus", 0)))
    structure = _normalize(signal_data.get("structural_score", 0))
    liquidity = _normalize(signal_data.get("liquidity_score", 0))
    momentum = _normalize(signal_data.get("momentum_score", 0))
    risk = _normalize(signal_data.get("risk_score", 0))
    trend = (signal_data.get("trend", "") or "").lower()
    kalman_dir = (signal_data.get("kalman_direction", "") or "").upper()
    direction = (signal_data.get("direction", "") or "").upper()
    atr = signal_data.get("atr_value", signal_data.get("atr", 0))
    entry = signal_data.get("entry_price", 0)
    volatility = signal_data.get("volatility", signal_data.get("bb_width", 0))
    rvol = signal_data.get("rvol", 0)
    mtf_conflict = signal_data.get("mtf_conflict", False)

    is_long = direction in ("LONG", "BUY")
    trend_uptrend = trend in ("uptrend", "alta")
    trend_downtrend = trend in ("downtrend", "baixa")
    kalman_up = "UP" in kalman_dir or "ALT" in kalman_dir
    kalman_down = "DOWN" in kalman_dir or "BAIX" in kalman_dir

    trend_align = 1.0 if (is_long and trend_uptrend) or (not is_long and trend_downtrend) else (
        0.5 if trend in ("ranging", "lateral") else 0.3
    )
    kalman_align = 1.0 if (is_long and kalman_up) or (not is_long and kalman_down) else (
        0.5 if kalman_dir in ("NEUTRAL", "UNKNOWN", "") else 0.3
    )

    atr_pct = (atr / entry * 100) if entry > 0 and atr > 0 else 2.0
    atr_norm = max(0.0, 1.0 - min(atr_pct / 5.0, 1.0))

    vol_norm = max(0.0, 1.0 - min(volatility / 0.1, 1.0)) if volatility > 0 else 0.5

    rvol_norm = min(rvol / 2.0, 1.0) if rvol > 0 else 0.0

    risk_inverted = 1.0 - risk

    mtf_factor = 0.0 if mtf_conflict else 0.5

    components = {
        "quality": quality,
        "confidence": confidence,
        "consensus": consensus,
        "structure": structure,
        "liquidity": liquidity,
        "momentum": momentum,
        "trend_alignment": trend_align,
        "kalman_alignment": kalman_align,
        "risk_inverted": risk_inverted,
        "atr_normalized": atr_norm,
        "volatility_normalized": vol_norm,
        "rvol_normalized": rvol_norm,
        "mtf_factor": mtf_factor,
    }

    raw_score = sum(
        min(v, 1.0) * EXPECTANCY_WEIGHTS[k]
        for k, v in components.items()
    )

    if raw_score >= 0.80:
        return "Muito Alta"
    if raw_score >= 0.65:
        return "Alta"
    if raw_score >= 0.50:
        return "Moderada"
    if raw_score >= 0.35:
        return "Baixa"
    return "Muito Baixa"


def estimate_time_to_tp1(timeframe: str, trend_strength: float = 0.5) -> str:
    tf_hours = {
        "1m": 1 / 60, "5m": 5 / 60, "15m": 0.25, "30m": 0.5,
        "1h": 1, "2h": 2, "4h": 4, "8h": 8, "12h": 12,
        "1d": 24, "3d": 72, "1w": 168,
    }
    base_hours = tf_hours.get(timeframe, 4)
    adj_hours = base_hours * 3.0 * (1.5 - min(trend_strength, 1.0) * 0.5)
    adj_hours = max(adj_hours, base_hours * 0.5)

    if adj_hours < 1:
        return "30 min – 2 horas"
    if adj_hours < 4:
        return "1 – 4 horas"
    if adj_hours < 12:
        return "4 – 12 horas"
    if adj_hours < 24:
        return "8 – 24 horas"
    if adj_hours < 72:
        return "24 – 72 horas"
    return "3 – 7 dias"


class OperationalCalculator:
    """V19.0: calcula indicadores financeiros padronizados para exibicao."""

    def calculate(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        quantity: float,
        balance: float,
        leverage: float = 1.0,
    ) -> dict:
        position_value = round(quantity * entry_price, 2) if quantity > 0 else 0.0
        margin_used = round(position_value / leverage, 2) if leverage > 0 and position_value > 0 else 0.0

        lucro_liquido_usdt = 0.0
        perda_maxima_usdt = 0.0
        retorno_ativo_pct = 0.0
        retorno_margem_pct = 0.0
        retorno_patrimonio_pct = 0.0

        if entry_price > 0 and take_profit_1 > 0:
            retorno_ativo_pct = round(abs((take_profit_1 - entry_price) / entry_price) * 100.0, 2)
            lucro_liquido_usdt = round(quantity * abs(take_profit_1 - entry_price), 2)

        if entry_price > 0 and stop_loss > 0:
            perda_maxima_usdt = round(quantity * abs(entry_price - stop_loss), 2)

        # BUG FIX (RFC V20.2): "retorno sobre margem" deve ser o lucro
        # como % do capital/colateral comprometido (margin_used), nao
        # lucro/perda_maxima (que e o RR em %, uma metrica diferente).
        if margin_used > 0:
            retorno_margem_pct = round(lucro_liquido_usdt / margin_used * 100.0, 2)
        if balance > 0:
            retorno_patrimonio_pct = round(lucro_liquido_usdt / balance * 100.0, 2)

        if margin_used > 0:
            alavancagem_efetiva = round(position_value / margin_used, 2)
        else:
            alavancagem_efetiva = 0.0

        return {
            "preco_entrada": entry_price,
            "preco_tp": take_profit_1,
            "preco_stop": stop_loss,
            "retorno_ativo_pct": retorno_ativo_pct,
            "retorno_margem_pct": retorno_margem_pct,
            "retorno_patrimonio_pct": retorno_patrimonio_pct,
            "lucro_liquido_usdt": lucro_liquido_usdt,
            "perda_maxima_usdt": perda_maxima_usdt,
            "valor_nominal": position_value,
            "margem_utilizada_usdt": margin_used,
            "quantidade": quantity,
            "alavancagem_efetiva": alavancagem_efetiva,
        }
