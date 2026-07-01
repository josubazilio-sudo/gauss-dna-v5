"""
V8 — Regime Institucional Inteligente.

Identifica o regime do mercado (Bull/Bear/Transicao/Lateral),
aplica score institucional dinamico (±15pts), ajusta confianca
por regime e detecta armadilhas/rompimentos.
"""

import logging
from config import ADX_BAIXO

logger = logging.getLogger(__name__)

REGIME_BULL = "BULL"
REGIME_BEAR = "BEAR"
REGIME_TRANSICAO = "TRANSICAO"
REGIME_LATERAL = "LATERAL"


def classify_regime(trend_data, momentum_data, flow_data):
    """
    Classifica o mercado em Bull, Bear, Transicao ou Lateral.

    Args:
        trend_data: dict com EMA_200, EMA_50, etc.
        momentum_data: dict com ADX, etc.
        flow_data: dict com FLUXO_TIPO, etc.

    Returns:
        (regime: str, detalhes: dict)
    """
    preco_ema200 = trend_data.get("PRECO_EMA200", 0)
    ema50 = trend_data.get("EMA_50", 0)
    ema200 = trend_data.get("EMA_200", 0)
    adx = momentum_data.get("ADX", 0)
    fluxo = flow_data.get("FLUXO_TIPO", "")
    kalman = trend_data.get("KALMAN_DIRECAO", "")

    detalhes = {}

    # Preco vs EMA200
    if preco_ema200 is not None and preco_ema200 > 0:
        detalhes["preco_acima_ema200"] = True
    else:
        detalhes["preco_acima_ema200"] = False

    # EMA50 vs EMA200
    if ema50 and ema200:
        detalhes["ema50_acima_ema200"] = ema50 > ema200
    else:
        detalhes["ema50_acima_ema200"] = False

    # ADX
    detalhes["adx_forte"] = adx >= ADX_BAIXO if adx else False

    # Fluxo
    detalhes["fluxo_comprador"] = fluxo in ("comprador", "leve_comprador")
    detalhes["fluxo_vendedor"] = fluxo in ("vendedor", "leve_vendedor")

    # Kalman
    detalhes["kalman_up"] = kalman == "UP"
    detalhes["kalman_down"] = kalman == "DOWN"

    # Ponderação Inteligente: ADX e Fluxo têm peso maior que EMA isolada
    bull_score = (
        (detalhes["preco_acima_ema200"] * 2) +
        (detalhes["ema50_acima_ema200"] * 2) +
        (detalhes["adx_forte"] * 3) +
        (detalhes["fluxo_comprador"] * 4) +
        (detalhes["kalman_up"] * 2)
    )

    bear_score = (
        (not detalhes["preco_acima_ema200"] * 2) +
        (not detalhes["ema50_acima_ema200"] * 2) +
        (detalhes["adx_forte"] * 3) +
        (detalhes["fluxo_vendedor"] * 4) +
        (detalhes["kalman_down"] * 2)
    )

    detalhes["bull_score"] = bull_score
    detalhes["bear_score"] = bear_score

    if bull_score >= 8:
        regime = REGIME_BULL
    elif bear_score >= 8:
        regime = REGIME_BEAR
    elif bull_score >= 5 or bear_score >= 5:
        regime = REGIME_TRANSICAO
    else:
        regime = REGIME_LATERAL

    detalhes["regime"] = regime
    return regime, detalhes


def calc_institutional_score(trend_data, flow_data, momentum_data, direcao):
    """
    Calcula o score institucional dinamico.
    Cada criterio: ±2 pontos, max ±15.

    Args:
        trend_data: dict com EMA_200, EMA_50, etc.
        flow_data: dict com FLUXO_TIPO, DELTA, etc.
        momentum_data: dict com ADX, etc.
        direcao: "long" ou "short"

    Returns:
        (pontos: int, detalhes: dict)
    """
    preco = trend_data.get("PRECO_EMA200", 0)
    ema50 = trend_data.get("EMA_50", 0)
    ema200 = trend_data.get("EMA_200", 0)
    adx = momentum_data.get("ADX", 0)
    fluxo = flow_data.get("FLUXO_TIPO", "")
    delta = flow_data.get("DELTA", 0)
    kalman = trend_data.get("KALMAN_DIRECAO", "")

    pontos = 0
    detalhes = {}

    # Preco vs EMA200
    if preco and ema200:
        if (direcao == "long" and preco > ema200) or (direcao == "short" and preco < ema200):
            pontos += 2
            detalhes["preco_ema200"] = 2
        else:
            pontos -= 2
            detalhes["preco_ema200"] = -2

    # EMA50 vs EMA200
    if ema50 and ema200:
        if (direcao == "long" and ema50 > ema200) or (direcao == "short" and ema50 < ema200):
            pontos += 2
            detalhes["ema50_ema200"] = 2
        else:
            pontos -= 2
            detalhes["ema50_ema200"] = -2

    # ADX
    if adx and adx >= ADX_BAIXO:
        pontos += 2
        detalhes["adx"] = 2
    else:
        pontos -= 2
        detalhes["adx"] = -2

    # Fluxo
    if (direcao == "long" and fluxo in ("comprador", "leve_comprador")) or \
       (direcao == "short" and fluxo in ("vendedor", "leve_vendedor")):
        pontos += 2
        detalhes["fluxo"] = 2
    else:
        pontos -= 2
        detalhes["fluxo"] = -2

    # Kalman
    if (direcao == "long" and kalman == "UP") or (direcao == "short" and kalman == "DOWN"):
        pontos += 2
        detalhes["kalman"] = 2
    elif kalman in ("",):
        detalhes["kalman"] = 0
    else:
        pontos -= 2
        detalhes["kalman"] = -2

    # Delta
    if (direcao == "long" and delta > 0) or (direcao == "short" and delta < 0):
        pontos += 2
        detalhes["delta"] = 2
    else:
        pontos -= 2
        detalhes["delta"] = -2

    # Distancia saudavel da EMA200 (entre 1% e 10%)
    if preco and ema200:
        dist = abs(preco - ema200) / ema200
        if 0.01 <= dist <= 0.10:
            pontos += 2
            detalhes["distancia"] = 2
        elif dist < 0.01:
            pontos -= 2
            detalhes["distancia"] = -2

    # Limitar a ±15
    pontos = max(-15, min(15, pontos))
    detalhes["institutional_score"] = pontos

    return pontos, detalhes


def calc_confidence_multiplier(regime, direcao):
    """
    Retorna multiplicador de confianca baseado no regime.
    """
    if regime == REGIME_BULL:
        return 1.08 if direcao == "long" else 0.92
    elif regime == REGIME_BEAR:
        return 1.08 if direcao == "short" else 0.92
    elif regime == REGIME_TRANSICAO:
        return 1.00
    else:
        return 0.95


def detect_traps(trend_data, flow_data, momentum_data):
    """
    Detecta armadilhas de mercado.
    Cada armadilha: -2 pontos, max -10.

    Returns:
        (penalidade: int, traps: list)
    """
    traps = []
    penalty = 0

    # Exaustao: VOL_ALTA + fluxo exaustao
    if flow_data.get("EXAUSTAO") and flow_data.get("VOLUME_CRESCENTE") is False:
        traps.append("exaustao")
        penalty += 2

    # Volume decrescente
    if flow_data.get("VOLUME_CRESCENTE") is False and flow_data.get("RVOL", 0) > 1.0:
        traps.append("volume_decrescente")
        penalty += 2

    # Divergencia: preco subindo mas delta caindo, ou vice-versa
    delta = flow_data.get("DELTA", 0)
    preco = flow_data.get("PRECO", 0)
    ema21 = trend_data.get("EMA_21", 0)
    if preco and ema21 and preco > ema21 and delta < 0:
        traps.append("divergencia_preco_delta")
        penalty += 2
    if preco and ema21 and preco < ema21 and delta > 0:
        traps.append("divergencia_preco_delta")
        penalty += 2

    penalty = min(penalty, 10)
    return penalty, traps


def check_breakout(trend_data, flow_data, momentum_data, preco, direcao):
    """
    Verifica rompimento institucional da EMA200.
    Confirmado: +4, falso: -4.

    Returns:
        (pontos: int, breakou: bool, falso: bool)
    """
    ema200 = trend_data.get("EMA_200", 0)
    if not ema200:
        return 0, False, False

    rvol = flow_data.get("RVOL", 0)
    adx = momentum_data.get("ADX", 0)
    fluxo = flow_data.get("FLUXO_TIPO", "")
    kalman = trend_data.get("KALMAN_DIRECAO", "")

    if direcao == "long":
        rompeu_acima = preco > ema200
        confirmado = (
            rompeu_acima
            and rvol >= 1.5
            and adx >= ADX_BAIXO
            and fluxo in ("comprador", "leve_comprador")
            and kalman in ("UP", "")
        )
        if confirmado:
            return 4, True, False
        if rompeu_acima and not confirmado:
            return -4, True, True
    else:
        rompeu_abaixo = preco < ema200
        confirmado = (
            rompeu_abaixo
            and rvol >= 1.5
            and adx >= ADX_BAIXO
            and fluxo in ("vendedor", "leve_vendedor")
            and kalman in ("DOWN", "")
        )
        if confirmado:
            return 4, True, False
        if rompeu_abaixo and not confirmado:
            return -4, True, True

    return 0, False, False


class RegimeWatchlist:
    """
    Watchlist inteligente: ativos com score >= BRONZE mas que
    falharam confirmacao. Reavaliados no proximo ciclo.
    """

    def __init__(self):
        self.entries = {}

    def add(self, symbol, score, direcao, motivo, preco, rsi):
        self.entries[symbol] = {
            "score": score,
            "direcao": direcao,
            "motivo": motivo,
            "preco": preco,
            "rsi": rsi,
            "ciclos_espera": 0,
        }

    def should_retry(self, symbol):
        entry = self.entries.get(symbol)
        if entry is None:
            return False
        entry["ciclos_espera"] += 1
        return entry["ciclos_espera"] <= 3

    def remove(self, symbol):
        self.entries.pop(symbol, None)

    def clear(self):
        self.entries.clear()

    def count(self):
        return len(self.entries)

    def top(self, n=5):
        return sorted(self.entries.items(), key=lambda x: x[1]["score"], reverse=True)[:n]
