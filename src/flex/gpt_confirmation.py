"""CONFIRMAÇÃO FINAL GPT — Filtro Institucional V2.0
Classificador inteligente, não bloqueador absoluto.
Hierarquia: Score > Tendência > Liquidez > Fluxo > Timing > RVOL > Velas Fortes
"""

import logging

logger = logging.getLogger(__name__)

# --- Auto-reject: apenas dados quebrados (nunca por qualidade marginal) ---
AUTO_REJECT = [
    ("kalman",       lambda r: r.get("kalman") in (None, "", "None"),            "Kalman ausente"),
    ("tendencia",    lambda r: r.get("trend") in ("", "—", None),                 "Tendência indefinida"),
    ("adx",          lambda r: (r.get("adx") or 0) < 15,                          "ADX < 15 (sem tendência)"),
    ("rvol",         lambda r: (r.get("rvol") or 0) < 0.50,                       "RVOL < 0.50 (volume ínfimo)"),
]

CLASSIFICACOES = [
    (9.0, "EXCELENTE",  "Operaria sem restrições"),
    (8.0, "MUITO BOM",  "Operaria normalmente"),
    (7.0, "BOM",        "Operaria com gerenciamento conservador"),
    (5.0, "MÉDIO",      "Aguardar confirmação adicional"),
    (0.0, "FRACO",      "Não enviar sinal"),
]


def _fluxo_a_favor(flow_data, direction):
    delta = flow_data.get("DELTA", 0)
    if direction == "long":
        return delta > 0
    elif direction == "short":
        return delta < 0
    return False


def _eh_mercado_lateral(adx, trend, atr_pct, smc_data):
    """Detecta mercado claramente lateral vs transição com confirmação."""
    if adx is None:
        return True
    if adx >= 22:
        return False
    if trend in ("NEUTRA", "LATERAL"):
        if smc_data and (smc_data.get("BOS") or smc_data.get("CHOCH")):
            return False
        return True
    return False


def _classificar_nota(nota):
    for threshold, nome, desc in CLASSIFICACOES:
        if nota >= threshold:
            return nome, desc
    return "FRACO", "Não enviar sinal"


def validar_confirmacao_gpt(result_data):
    """
    Validação inteligente: nota 0-10 com hierarquia.
    Bloqueia apenas dados quebrados ou mercado claramente lateral.
    """
    # --- 1. Auto-reject (dados quebrados) ---
    auto_reject = []
    for key, check, label in AUTO_REJECT:
        try:
            if check(result_data):
                auto_reject.append(label)
        except Exception as e:
            logger.debug("Auto-reject '%s' falhou: %s", key, e)
            auto_reject.append(label)

    if auto_reject:
        logger.info("GPT: REPROVADO (auto-reject: %s)", ", ".join(auto_reject))
        return {
            "aprovado": False, "nota": 0.0, "auto_reject": auto_reject,
            "motivos_aprovacao": [], "motivos_reprovacao": auto_reject,
            "classificacao": "FRACO", "descricao": "Reprovado automaticamente",
        }

    # --- 2. Extrair dados ---
    score = result_data.get("score", 0)
    trend = result_data.get("trend", "")
    adx = result_data.get("adx", 0)
    rvol = result_data.get("rvol", 0)
    timing = result_data.get("timing_index", 0)
    conviction = result_data.get("conviction_score", 0)
    velas = result_data.get("velas", 0)
    atr_pct = result_data.get("atr_pct", 0)
    flow_data = result_data.get("flow_data", {}) or {}
    smc_data = result_data.get("smc_data", {}) or {}
    fluxo_data = result_data.get("fluxo_data", {}) or {}
    fluxo_score = fluxo_data.get("fluxo_score", 0)
    direction = str(result_data.get("direction", "")).lower()

    motivos_aprovacao = []
    motivos_reprovacao = []
    nota = 6.0

    # --- 3. Verificar mercado lateral ---
    if _eh_mercado_lateral(adx, trend, atr_pct, smc_data):
        motivo = "Mercado claramente lateral (ADX baixo, tendência neutra)"
        motivos_reprovacao.append(motivo)
        logger.info("GPT: REPROVADO (%s)", motivo)
        return {
            "aprovado": False, "nota": 2.0, "auto_reject": [],
            "motivos_aprovacao": [], "motivos_reprovacao": [motivo],
            "classificacao": "FRACO", "descricao": motivo,
        }

    # --- 4. Exceção: Score >= 90 + Tendência + Liquidez ---
    score_alto = score >= 90
    tendencia_ok = trend in ("ALTA", "BAIXA")
    liquidez_ok = rvol >= 0.80 or flow_data.get("VOLUME_24H", 0) >= 1_000_000
    excecao = score_alto and tendencia_ok and liquidez_ok

    # --- 5. Penalidades e bônus por hierarquia ---

    # Score Institucional (peso #1)
    if score >= 95:
        nota += 1.5
        motivos_aprovacao.append(f"Score {score}/100 (excelente)")
    elif score >= 90:
        nota += 1.0
        motivos_aprovacao.append(f"Score {score}/100 (muito alto)")
    elif score >= 85:
        nota += 0.5
        motivos_aprovacao.append(f"Score {score}/100 (alto)")
    elif score >= 80:
        nota += 0.0
        motivos_aprovacao.append(f"Score {score}/100 (bom)")
    elif score >= 75:
        nota -= 0.5
        motivos_reprovacao.append("Score abaixo de 80")
    else:
        nota -= 1.5
        motivos_reprovacao.append("Score abaixo de 75")

    # Tendência (peso #2)
    if trend in ("ALTA", "BAIXA"):
        nota += 0.5
        motivos_aprovacao.append(f"Tendência definida ({trend})")
    elif trend == "TRANSIÇÃO":
        smc_transicao = smc_data.get("BOS") or smc_data.get("CHOCH")
        fluxo_transicao = _fluxo_a_favor(flow_data, direction)
        if smc_transicao and fluxo_transicao:
            motivos_aprovacao.append("Transição com confirmação institucional")
        else:
            nota -= 0.5
            motivos_reprovacao.append("Transição sem confirmação")

    # Liquidez/Volume (peso #3)
    vol_24h = flow_data.get("VOLUME_24H", 0)
    if vol_24h >= 10_000_000:
        nota += 0.3
        motivos_aprovacao.append("Alta liquidez 24h")
    elif vol_24h >= 3_000_000:
        nota += 0.1
    elif vol_24h < 1_000_000 and vol_24h > 0:
        nota -= 0.5
        motivos_reprovacao.append("Baixa liquidez 24h")

    # Fluxo (peso #4)
    if fluxo_score >= 75:
        nota += 0.5
        motivos_aprovacao.append(f"Fluxo forte ({fluxo_score})")
    elif fluxo_score >= 55:
        nota += 0.0
    else:
        if not excecao:
            nota -= 0.5
            motivos_reprovacao.append(f"Fluxo baixo ({fluxo_score})")

    fluxo_alinhado = _fluxo_a_favor(flow_data, direction)
    if fluxo_alinhado:
        nota += 0.3
        motivos_aprovacao.append("Fluxo alinhado à direção")
    elif not excecao:
        nota -= 0.3
        motivos_reprovacao.append("Fluxo contra a direção")

    # Timing (peso #5) — influencia classificação, não bloqueia
    if timing >= 75:
        nota += 0.5
        motivos_aprovacao.append(f"Timing favorável ({timing})")
    elif timing >= 55:
        nota += 0.0
    elif timing >= 45:
        if not excecao:
            nota -= 0.3
    else:
        if not excecao:
            nota -= 0.5
            motivos_reprovacao.append(f"Timing baixo ({timing})")

    # RVOL (peso #6)
    if rvol >= 1.5:
        nota += 0.4
        motivos_aprovacao.append(f"RVOL elevado ({rvol:.1f}x)")
    elif rvol >= 0.80:
        nota += 0.0
    else:
        if not excecao:
            nota -= 0.3
            motivos_reprovacao.append(f"RVOL baixo ({rvol:.1f}x)")

    # ADX
    if adx >= 30:
        nota += 0.3
    elif adx >= 22:
        nota += 0.0
    elif adx >= 18:
        if not excecao:
            nota -= 0.2

    # Velas Fortes (peso #7) — NUNCA bloqueia
    if velas >= 2:
        nota += 0.3
        motivos_aprovacao.append(f"{velas} velas fortes")
    elif velas >= 1:
        nota += 0.1
    else:
        nota -= 0.1

    # Convicção
    if conviction >= 75:
        nota += 0.3
        motivos_aprovacao.append(f"Convicção alta ({conviction})")
    elif conviction >= 55:
        nota += 0.0
    else:
        if not excecao:
            nota -= 0.3

    # Estrutura SMC (bônus)
    smc_ok = smc_data.get("BOS") or smc_data.get("CHOCH")
    if smc_ok:
        nota += 0.3
    if smc_data.get("FVG"):
        nota += 0.2
    if smc_data.get("LIQUIDITY_SWEEP"):
        nota += 0.2
    if smc_data.get("ORDER_BLOCK"):
        nota += 0.2

    # --- 6. Aplicar exceção ---
    if excecao:
        nota = max(nota, 8.0)
        motivos_aprovacao.append("EXCEÇÃO: Score ≥ 90 + Tendência + Liquidez")

    nota = min(max(round(nota, 1), 0), 10)
    classificacao, descricao = _classificar_nota(nota)
    aprovado = nota >= 5.0

    logger.info(
        "GPT: %s | Símbolo: %s | Score: %d | Nota: %.1f/10 | %s",
        "APROVADO" if aprovado else "REPROVADO",
        result_data.get("symbol", "?"), score, nota, classificacao
    )
    if motivos_reprovacao:
        logger.info("  Pontos fracos: %s", "; ".join(motivos_reprovacao[:3]))

    return {
        "aprovado": aprovado,
        "nota": nota,
        "auto_reject": [],
        "motivos_aprovacao": motivos_aprovacao,
        "motivos_reprovacao": motivos_reprovacao,
        "classificacao": classificacao,
        "descricao": descricao,
    }
