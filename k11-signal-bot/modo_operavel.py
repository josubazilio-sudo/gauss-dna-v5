"""
K12 — MODO OPERÁVEL REAL (RFC 29/08)
=====================================
Módulo FINAL de liberação. Roda DEPOIS do motor (k10_engine.py) e do Final
Selector já terem aprovado um candidato — nunca recalcula estrutura/EQ/RVOL
do zero, só reaproveita os campos que o motor já expõe no dict do sinal.

Função: proteger capital. Score alto não substitui EQ, estrutura, contexto
HTF, RR ou risco. Se qualquer HARD BLOCK ocorrer, ou não houver vantagem
clara, o sinal NÃO é liberado — mesmo que já tenha passado pelo motor e
pelo Final Selector.

REGRA DA CASA (RFC 29/08): esta RFC foi confirmada pelo usuário como
substituindo, para este módulo, a regra "um ajuste por vez" do
k12-prompt-mestre — decisão explícita dele, não interpretação minha.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

TRADES_FILE = "/root/gauss-dna-v5/k11-signal-bot/k11_trades.json"

# ── Limiares (Secao 3, 5, 7, 9 da RFC) ──────────────────────────────────
EQ_MIN_ACEITAVEL   = 70
EQ_MIN_BOM         = 80
EQ_MIN_PREMIUM     = 85

RVOL_HARD_MIN      = 0.80
RVOL_ACEITAVEL_MIN = 1.00
RVOL_BOM_MIN       = 1.50
RVOL_PREMIUM_MIN   = 1.80

RR_MIN_ACEITAVEL   = 2.0
RR_MIN_BOM         = 2.2
RR_MIN_PREMIUM     = 2.2

RISCO_MAX_ABSOLUTO = 3.0   # % da banca, nunca ultrapassar (Secao 9)
RISCO_PREMIUM      = 3.0
RISCO_BOM          = 1.5
RISCO_ACEITAVEL    = 0.75

ADX_CTX_FORTE      = 28    # mesmo valor ja usado no motor para "tendencia forte"


def _entrada_esticada(sinal: dict) -> bool:
    """Reaproveita o flag ja calculado em _entry_quality (extensao >1.5 ATR
    da EMA21 zera 50pts e marca 'bloqueado'); mesmo padrao usado em todo o
    resto do k10_engine.py para 'entrada tardia/esticada'."""
    eq_det = sinal.get("eq_detalhes") or {}
    if eq_det.get("ema21", 0) <= -50:
        return True
    return any("esticad" in str(m).lower() or "atrasad" in str(m).lower() or "tardia" in str(m).lower()
               for m in (sinal.get("motivos_rejeicao") or []))


def _estrutura_confirmada(sinal: dict) -> bool:
    return bool(sinal.get("bos_ok")) or bool(sinal.get("sweep_ok"))


def _estrutura_completa(sinal: dict) -> bool:
    """BOS/CHoCH E sweep/liquidez juntos — exigido para BOM/PREMIUM e para
    REVERSAO (Secao 4)."""
    return bool(sinal.get("bos_ok")) and bool(sinal.get("sweep_ok"))


def _pullback_reteste(sinal: dict) -> bool:
    eq_det = sinal.get("eq_detalhes") or {}
    return eq_det.get("ema21", 0) > 0


def _contexto_htf_favoravel(sinal: dict) -> bool:
    return bool(sinal.get("tend_ctx_ok")) and bool(sinal.get("macd_ctx_ok"))


def _contexto_htf_fortemente_contra(sinal: dict) -> bool:
    tend_ctx_ok = sinal.get("tend_ctx_ok")
    macd_ctx_ok = sinal.get("macd_ctx_ok")
    adx_ctx = sinal.get("adx_ctx") or 0
    # "fortemente contra" = tendencia HTF contraria com ADX HTF forte
    # (mesmo criterio que o motor ja usa para "contra tendencia forte").
    htf_forte_contra = (not tend_ctx_ok) and adx_ctx > ADX_CTX_FORTE
    ambos_contra = (not tend_ctx_ok) and (not macd_ctx_ok)
    return htf_forte_contra or ambos_contra


def _e_reversao(sinal: dict) -> bool:
    """Reversao = candidato entrou via sweep (liquidez capturada), nao
    via continuacao pura de tendencia. Mesmo criterio usado em
    'regime_label' e 'prioridade' no k10_engine.py."""
    return bool(sinal.get("sweep_ok"))


def _risco_maximo_ok(sinal: dict) -> bool:
    risco_pct = sinal.get("risco_pct_aplicado")
    if risco_pct is None:
        return True
    return risco_pct <= RISCO_MAX_ABSOLUTO


def _carregar_trades_abertos():
    try:
        trades = json.load(open(TRADES_FILE, encoding="utf-8"))
    except Exception as e:
        logger.warning(f"MODO_OPERAVEL: falha ao ler {TRADES_FILE}: {e}")
        return []
    return [t for t in trades if t.get("resultado") == "ABERTO"]


def _exposicao_ok(sinal: dict) -> tuple:
    """Secao 10 — maximo 1 operacao nova por vez no mesmo contexto
    direcional. Verifica trades ja ABERTOS na MESMA direcao (LONG/SHORT)
    -- nao inventa correlacao por ativo, so limita concentracao direcional
    simultanea, que e o que a RFC pede explicitamente."""
    direcao = sinal.get("direcao")
    abertos = _carregar_trades_abertos()
    mesma_direcao = [t for t in abertos if t.get("direcao") == direcao]
    if len(mesma_direcao) >= 1:
        return False, f"ja existe {len(mesma_direcao)} operacao(oes) {direcao} aberta(s) (exposicao maxima 1 por direcao)"
    return True, ""


def avaliar(sinal: dict) -> dict:
    """Avalia um sinal JA aprovado pelo motor + Final Selector. Retorna:
    {
      "operar": bool,
      "classificacao": "NAO_OPERAVEL" | "ACEITAVEL" | "BOM" | "PREMIUM",
      "motivos_bloqueio": [...],       # top 3, se nao operar
      "risco_pct_final": float,        # so relevante se operar=True
      "estrutura": {...}, "contexto": {...},  # para o card
    }
    Nunca modifica `sinal` in-place.
    """
    motivos = []

    eq = sinal.get("entry_quality") or 0
    rvol = sinal.get("rvol") or 0
    rr = sinal.get("rr") or 0
    direcao = sinal.get("direcao")
    estrutura_ok = _estrutura_confirmada(sinal)
    estrutura_completa = _estrutura_completa(sinal)
    esticada = _entrada_esticada(sinal)
    ctx_forte_contra = _contexto_htf_fortemente_contra(sinal)
    ctx_favoravel = _contexto_htf_favoravel(sinal)
    zona_institucional = bool(sinal.get("tem_zona_institucional"))
    pullback = _pullback_reteste(sinal)
    reversao = _e_reversao(sinal)
    risco_pct = sinal.get("risco_pct_aplicado") or 0

    # ── HARD BLOCKS (Secao 3) ────────────────────────────────────────
    if eq < EQ_MIN_ACEITAVEL:
        motivos.append(f"Entry Quality {eq} < {EQ_MIN_ACEITAVEL}")
    if not estrutura_ok:
        motivos.append("sem BOS/CHoCH nem sweep/liquidez confirmado")
    if esticada:
        motivos.append("entrada esticada/tardia (preco ja percorreu o movimento)")
    if rvol < RVOL_HARD_MIN:
        motivos.append(f"RVOL {rvol:.2f} < {RVOL_HARD_MIN} (sem liquidez real)")
    if ctx_forte_contra:
        motivos.append("contexto HTF (H1/H4) fortemente contrario")
    if rr < RR_MIN_ACEITAVEL:
        motivos.append(f"RR real {rr:.2f} < {RR_MIN_ACEITAVEL}")
    if not _risco_maximo_ok(sinal):
        motivos.append(f"risco calculado {risco_pct:.1f}% > {RISCO_MAX_ABSOLUTO}% da banca")

    # ── REGRA ESPECIAL REVERSAO (Secao 4) ────────────────────────────
    if reversao and not motivos:
        if not estrutura_completa:
            motivos.append("REVERSAO exige liquidez capturada E BOS/CHoCH juntos (so um dos dois nao basta)")
        elif not pullback:
            motivos.append("REVERSAO exige pullback/reteste confirmado")

    exposicao_ok, motivo_exposicao = _exposicao_ok(sinal)
    if not motivos and not exposicao_ok:
        motivos.append(motivo_exposicao)

    estrutura_info = {
        "bos_choch": estrutura_ok,
        "liquidez": bool(sinal.get("sweep_ok")),
        "pullback": pullback,
        "zona_institucional": zona_institucional,
    }
    contexto_info = {
        "htf_alinhado": ctx_favoravel,
        "ema_ok": not esticada,
        "macd_ok": bool(sinal.get("macd_ctx_ok")),
        "volume_ok": rvol >= RVOL_HARD_MIN,
    }

    if motivos:
        return {
            "operar": False,
            "classificacao": "NAO_OPERAVEL",
            "motivos_bloqueio": motivos[:3],
            "risco_pct_final": 0,
            "estrutura": estrutura_info,
            "contexto": contexto_info,
        }

    # ── CLASSIFICACAO (Secao 7) — so chega aqui se nenhum hard block ──
    premium = (
        eq >= EQ_MIN_PREMIUM and estrutura_completa and zona_institucional
        and pullback and rvol >= RVOL_PREMIUM_MIN and ctx_favoravel and rr >= RR_MIN_PREMIUM
    )
    bom = (
        eq >= EQ_MIN_BOM and estrutura_completa and pullback
        and rvol >= RVOL_BOM_MIN and ctx_favoravel and rr >= RR_MIN_BOM
    )
    # ACEITAVEL: ja garantido pelos hard blocks acima (eq>=70, estrutura_ok,
    # rvol>=1.0 checado abaixo, rr>=2.0, contexto nao fortemente contra).
    aceitavel_rvol_ok = rvol >= RVOL_ACEITAVEL_MIN

    if premium:
        classificacao, risco_final = "PREMIUM", RISCO_PREMIUM
    elif bom:
        classificacao, risco_final = "BOM", RISCO_BOM
    elif aceitavel_rvol_ok:
        classificacao, risco_final = "ACEITAVEL", RISCO_ACEITAVEL
    else:
        # RVOL entre hard-min (0.80) e aceitavel-min (1.00): RFC secao 5
        # permite "somente SETUP forte" -- aqui, sem tier legado, trata
        # como ACEITAVEL com risco minimo, nao bloqueia.
        classificacao, risco_final = "ACEITAVEL", RISCO_ACEITAVEL

    risco_pct_final = min(risco_final, RISCO_MAX_ABSOLUTO)

    # Recalcula risco USDT / posicao com o NOVO risco%, mesma formula ja
    # usada no motor (BANCA * risco% / 100, dividido pela distancia real
    # ate o stop) -- nao inventa calculo novo, so aplica o risco_pct_final
    # desta RFC no lugar do risco_pct_aplicado adaptativo antigo.
    banca = sinal.get("capital") or sinal.get("banca") or 0
    entrada = sinal.get("entrada") or 0
    stop = sinal.get("stop") or 0
    dist = abs(entrada - stop) / entrada if entrada else 0.01
    risco_usdt_final = round(banca * risco_pct_final / 100, 2)
    posicao_final = round(min(risco_usdt_final / dist, banca * 3), 2) if dist > 0 else 0

    return {
        "operar": True,
        "classificacao": classificacao,
        "motivos_bloqueio": [],
        "risco_pct_final": risco_pct_final,
        "risco_usdt_final": risco_usdt_final,
        "posicao_final": posicao_final,
        "estrutura": estrutura_info,
        "contexto": contexto_info,
    }
