"""CONFIRMAÇÃO FINAL GPT — Filtro Institucional V1.0"""

import logging

logger = logging.getLogger(__name__)

# --- Auto-reject (bloqueio imediato) ---
AUTO_REJECT = [
    ("kalman",       lambda r: r.get("kalman") in (None, "", "None"),       "Kalman = None"),
    ("tendencia",    lambda r: r.get("trend") in ("", "—", "NEUTRA", "LATERAL", "TRANSIÇÃO"), "Tendência = —"),
    ("rvol",         lambda r: (r.get("rvol") or 0) < 0.90,                "RVOL < 0.90"),
    ("adx",          lambda r: (r.get("adx") or 0) < 20,                    "ADX < 20"),
    ("conviccao",    lambda r: (r.get("conviction_score") or 0) < 60,      "Convicção < 60"),
    ("timing",       lambda r: (r.get("timing_index") or 0) < 65,           "Timing < 65"),
    ("velas_fortes", lambda r: (r.get("velas") or 0) < 1,                  "Velas Fortes = 0"),
    ("fluxo_score",  lambda r: (r.get("fluxo_data") or {}).get("fluxo_score", 0) < 60, "Score Fluxo < 60"),
]

# --- Requisitos obrigatórios (para nota) ---
REQUISITOS = [
    ("score",       "Score Institucional >= 80",     lambda r: (r.get("score") or 0) >= 80),
    ("confianca",   "Confiança >= 80%",              lambda r: (r.get("confianca") or 0) >= 80),
    ("conviccao",   "Convicção >= 60",               lambda r: (r.get("conviction_score") or 0) >= 60),
    ("timing",      "Timing >= 65",                  lambda r: (r.get("timing_index") or 0) >= 65),
    ("tendencia",   "Tendência definida",            lambda r: r.get("trend") not in ("", "—", "NEUTRA", "LATERAL", "TRANSIÇÃO", None)),
    ("kalman",      "Kalman alinhado (LONG/SHORT)",  lambda r: r.get("kalman") in ("UP", "DOWN")),
    ("rvol",        "RVOL >= 0.90",                  lambda r: (r.get("rvol") or 0) >= 0.90),
    ("adx",         "ADX >= 25",                     lambda r: (r.get("adx") or 0) >= 25),
    ("fluxo",       "Fluxo institucional alinhado",  lambda r: _fluxo_a_favor(r.get("flow_data", {}), str(r.get("direction", "")).lower())),
    ("smc",         "Estrutura SMC (BOS/CHoCH)",     lambda r: r.get("smc_data", {}).get("BOS", False) or r.get("smc_data", {}).get("CHOCH", False)),
    ("fvg",         "FVG válido",                    lambda r: r.get("smc_data", {}).get("FVG", False) if r.get("smc_data") else False),
    ("liquidez",    "Liquidez capturada (Sweep)",    lambda r: r.get("smc_data", {}).get("LIQUIDITY_SWEEP", False) if r.get("smc_data") else False),
    ("vela",        "≥ 1 vela impulsiva",            lambda r: (r.get("velas") or 0) >= 1),
    ("rr",          "Risco:Retorno >= 2.0",          lambda r: (r.get("rr") or 0) >= 2.0),
    ("stop_atr",    "Stop dentro do ATR permitido",  lambda r: (r.get("stop_pct") or 0) <= (r.get("atr_pct") or 999) * 3),
]

CLASSIFICACOES = [
    (9.0, "EXCELENTE",  "Operaria sem restrições"),
    (8.5, "MUITO BOM",  "Operaria normalmente"),
    (8.0, "BOM",        "Operaria com gerenciamento conservador"),
    (7.0, "MÉDIO",      "Esperar confirmação adicional"),
    (0.0, "FRACO",      "Não enviar sinal"),
]


def _fluxo_a_favor(flow_data, direction):
    delta = flow_data.get("DELTA", 0)
    if direction == "long":
        return delta > 0
    elif direction == "short":
        return delta < 0
    return False


def _smc_confirmada(flow_data):
    return flow_data.get("BOS", False) or flow_data.get("CHOCH", False)


def _classificar_nota(nota):
    for threshold, nome, desc in CLASSIFICACOES:
        if nota >= threshold:
            return nome, desc
    return "FRACO", "Não enviar sinal"


def validar_confirmacao_gpt(result_data):
    """
    Validação final GPT antes de enviar o sinal.

    Args:
        result_data: dict com todos os dados do sinal

    Returns:
        dict com:
            aprovado: bool
            nota: float (0-10)
            auto_reject: list[str] — motivos de reprovação automática
            motivos_aprovacao: list[str]
            motivos_reprovacao: list[str]
            classificacao: str
            descricao: str
    """
    auto_reject = []
    for key, check, label in AUTO_REJECT:
        try:
            if check(result_data):
                auto_reject.append(label)
        except Exception as e:
            logger.debug("Auto-reject check '%s' falhou: %s", key, e)
            auto_reject.append(label)

    if auto_reject:
        logger.info("GPT Confirmation: REPROVADO (auto-reject: %s)", ", ".join(auto_reject))
        return {
            "aprovado": False,
            "nota": 0.0,
            "auto_reject": auto_reject,
            "motivos_aprovacao": [],
            "motivos_reprovacao": auto_reject,
            "classificacao": "FRACO",
            "descricao": "Reprovado automaticamente",
        }

    motivos_aprovacao = []
    motivos_reprovacao = []
    total = len(REQUISITOS)
    passou = 0

    for key, label, check in REQUISITOS:
        try:
            if check(result_data):
                motivos_aprovacao.append(label)
                passou += 1
            else:
                motivos_reprovacao.append(label)
        except Exception as e:
            logger.debug("Requisito '%s' falhou com erro: %s", key, e)
            motivos_reprovacao.append(label)

    nota = round((passou / total) * 10, 1)
    classificacao, descricao = _classificar_nota(nota)
    aprovado = nota >= 8.0

    logger.info(
        "GPT Confirmation: %s (nota %.1f/10, %d/%d requisitos)",
        "APROVADO" if aprovado else "REPROVADO",
        nota, passou, total
    )

    return {
        "aprovado": aprovado,
        "nota": nota,
        "auto_reject": [],
        "motivos_aprovacao": motivos_aprovacao,
        "motivos_reprovacao": motivos_reprovacao,
        "classificacao": classificacao,
        "descricao": descricao,
    }
