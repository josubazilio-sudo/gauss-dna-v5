"""
K11 APEX v1 — Camada de avaliação independente (SHADOW MODE).

Não substitui k10_engine.py nem final_selector.py e não altera nenhum gate
de aprovação existente. Roda em paralelo, em cima dos candidatos que JÁ
passaram por todos os filtros duros do engine (SHORT bloqueado, BOS/CHoCH
obrigatório, EQ >= 75, MODO_10_10) — herda essas proteções automaticamente
por construção, sem precisar reimplementá-las.

Objetivo: achar o setup raro que combina estrutura + liquidez + timing +
confirmação HTF + volume, e sinalizar no máximo 1 por ciclo.

RFC "K11 APEX — Reconstrução Controlada" (2026-08-20).
"""

CFG = {
    "APEX_MIN_SCORE": 80,     # nota mínima 0-100 pra virar candidato APEX
    "APEX_RVOL_MIN":  1.5,    # requisito duro de volume (secao 8.5 da RFC)
}

PESOS = {
    "estrutura": 25,
    "liquidez":  20,
    "timing":    20,
    "htf":       15,
    "rvol":      10,
    "tendencia":  5,
    "momentum":   5,
}


def _score_estrutura(audit, confs):
    """BOS/CHoCH confirmado = nota cheia. Sem isso, so 'tendencia forte' da meia nota."""
    if audit.get("BOS/CHoCH") == "PASS":
        return PESOS["estrutura"], True
    if any("Tendência forte" in c for c in confs):
        return round(PESOS["estrutura"] * 0.6), False
    return 0, False


def _score_liquidez(audit, confs):
    """Sweep/captura de liquidez = nota cheia. OB ou FVG isolados = parcial."""
    if any("Liquidez capturada" in c for c in confs):
        return PESOS["liquidez"], True
    if audit.get("Order Block") == "PASS":
        return round(PESOS["liquidez"] * 0.7), False
    if audit.get("FVG") == "PASS":
        return round(PESOS["liquidez"] * 0.5), False
    return 0, False


def _score_timing(sinal):
    """
    Reaproveita o Entry Quality (EQ) já validado pelo engine — ele foi
    desenhado especificamente pra medir qualidade do PONTO de entrada
    (distancia EMA21, idade do BOS, timing do MACD). Nao reinventa a roda.
    """
    eq = sinal.get("entry_quality", 0)
    return round(eq / 100 * PESOS["timing"]), eq


def _score_htf(audit, confs):
    htf_ok  = audit.get("Trend H1/H4") == "PASS"
    macd_ok = audit.get("MACD") == "PASS"
    if htf_ok and macd_ok and any(("H1" in c or "H4" in c) for c in confs):
        return PESOS["htf"], True
    if htf_ok:
        return round(PESOS["htf"] * 0.5), False
    return 0, False


def _score_rvol(sinal):
    rvol = sinal.get("rvol", 0)
    if rvol >= 2.0: return PESOS["rvol"], rvol
    if rvol >= 1.5: return round(PESOS["rvol"] * 0.7), rvol
    if rvol >= 1.0: return round(PESOS["rvol"] * 0.3), rvol
    return 0, rvol


def _score_tendencia(confs):
    if any("EMAs 4 alinhadas" in c for c in confs):
        return PESOS["tendencia"]
    if any("EMAs 3 alinhadas" in c for c in confs):
        return round(PESOS["tendencia"] * 0.6)
    if any("EMA10/21 ok" in c for c in confs):
        return round(PESOS["tendencia"] * 0.2)
    return 0


def _score_momentum(audit):
    return PESOS["momentum"] if audit.get("MACD") == "PASS" else 0


def avaliar_apex(sinal: dict) -> dict:
    """
    Avalia UM sinal já aprovado pelo engine como candidato APEX.
    Não modifica `sinal`, não decide aprovação/reprovação do engine —
    é uma segunda lente, independente do Score antigo.
    """
    audit   = sinal.get("audit_10of10", {}) or {}
    confs   = sinal.get("confirmacoes_smc", []) or []
    regime  = sinal.get("regime", "")
    direcao = sinal.get("direcao", "")

    s_estrutura, estrutura_ok = _score_estrutura(audit, confs)
    s_liquidez,  liquidez_ok  = _score_liquidez(audit, confs)
    s_timing,    eq           = _score_timing(sinal)
    s_htf,       htf_ok       = _score_htf(audit, confs)
    s_rvol,      rvol_val     = _score_rvol(sinal)
    s_tendencia                = _score_tendencia(confs)
    s_momentum                 = _score_momentum(audit)

    apex_score = s_estrutura + s_liquidez + s_timing + s_htf + s_rvol + s_tendencia + s_momentum

    # Classificação — só 2 tipos possíveis, mutuamente exclusivos (secao 8 da RFC).
    # SHORT nunca chega aqui pois o engine ja bloqueia SHORT antes da aprovacao.
    eh_sweep   = any("Liquidez capturada" in c for c in confs)
    tend_forte = any("Tendência forte" in c for c in confs) or "Tendência Alta" in regime
    apex_tipo = None
    if direcao == "LONG":
        if eh_sweep and "Reversão" in regime:
            apex_tipo = "REVERSAL"
        elif tend_forte and "Tendência" in regime:
            apex_tipo = "TREND"

    # Requisitos duros — nenhum componente isolado (nem RVOL alto, nem score
    # alto) pode "comprar" a ausência de um ingrediente essencial (secao 10).
    requisitos = {
        "estrutura":     estrutura_ok,
        "rvol_minimo":   rvol_val >= CFG["APEX_RVOL_MIN"],
        "htf":           htf_ok,
        "tipo_definido": apex_tipo is not None,
    }
    todos_requisitos_ok = all(requisitos.values())
    is_apex = todos_requisitos_ok and apex_score >= CFG["APEX_MIN_SCORE"]

    checklist = {
        "Estrutura":       "✅" if estrutura_ok else "❌",
        "Liquidez":        "✅" if liquidez_ok else "❌",
        "Timing (EQ)":     f"{'✅' if eq >= 75 else '❌'} ({eq})",
        "HTF (H1/H4)":     "✅" if htf_ok else "❌",
        "RVOL":            f"{'✅' if rvol_val >= CFG['APEX_RVOL_MIN'] else '❌'} ({rvol_val:.2f})",
        "Tendência/EMA":   "✅" if s_tendencia >= PESOS["tendencia"] * 0.6 else "❌",
        "Momentum (MACD)": "✅" if s_momentum > 0 else "❌",
    }

    if not todos_requisitos_ok:
        faltando = [k for k, v in requisitos.items() if not v]
        motivo = f"Requisito(s) faltando: {', '.join(faltando)}"
    elif apex_score < CFG["APEX_MIN_SCORE"]:
        motivo = f"APEX_SCORE {apex_score} < {CFG['APEX_MIN_SCORE']}"
    else:
        motivo = "Aprovado"

    return {
        "is_apex":    is_apex,
        "apex_tipo":  apex_tipo,
        "apex_score": apex_score,
        "componentes": {
            "estrutura": s_estrutura, "liquidez": s_liquidez, "timing": s_timing,
            "htf": s_htf, "rvol": s_rvol, "tendencia": s_tendencia, "momentum": s_momentum,
        },
        "checklist": checklist,
        "motivo": motivo,
    }


def selecionar_apex(candidatos: list):
    """
    Avalia todos os candidatos aprovados pelo engine neste ciclo e retorna
    o MELHOR APEX (ou None se nenhum atingir a barra). Máximo 1 por ciclo
    (secao 19 da RFC) — desempate por timing, depois estrutura, depois RVOL.
    """
    avaliados = [(s, avaliar_apex(s)) for s in candidatos]
    apex_validos = [(s, info) for s, info in avaliados if info["is_apex"]]
    if not apex_validos:
        return None

    apex_validos.sort(key=lambda x: (
        x[1]["apex_score"],
        x[1]["componentes"]["timing"],
        x[1]["componentes"]["estrutura"],
        x[0].get("rvol", 0),
    ), reverse=True)

    melhor_sinal, melhor_info = apex_validos[0]
    return {"sinal": melhor_sinal, **melhor_info}
