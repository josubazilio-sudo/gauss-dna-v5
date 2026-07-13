"""RFC V19.3 — Prioridade Dinamica do Scanner.

Calcula um PRIORITY_SCORE usado EXCLUSIVAMENTE para ordenar a fila de
varredura do scanner a cada ciclo. NAO altera Score Institucional,
Confidence, Quality, Hard Gates, Decision Engine ou gestao de risco.

Ver RFC_V19_3_PRIORIDADE_DINAMICA_SCANNER.md para a tabela de divergencias
em relacao ao prompt original (spread/liquidez real nao sao instrumentados
hoje no pipeline — usam proxy de volume; RVOL/ADX/ATR/momentum usam o
cache do ciclo anterior para nao exigir busca de candles antes da ordem
ser decidida, evitando aumento de chamadas de API).
"""
from typing import Dict, List, Optional

RVOL_HIGH_THRESHOLD = 2.0
ADX_HIGH_THRESHOLD = 25.0
ATR_PERCENT_HIGH_THRESHOLD = 3.0  # mesmo limiar de "ATR elevado" usado em operational.py
PRICE_CHANGE_THRESHOLD_PCT = 5.0
MOMENTUM_HIGH_THRESHOLD = 0.5
BREAKOUT_PROXIMITY_PCT = 0.5  # dentro de 0.5% da maxima/minima de 24h

BONUS_RVOL = 40
BONUS_VOLUME_ABOVE_AVG = 30
BONUS_PRICE_CHANGE = 25
BONUS_ATR_PERCENT = 20
BONUS_ADX = 20
BONUS_BREAKOUT = 15
BONUS_LIQUIDITY = 15
BONUS_MOMENTUM = 10
BONUS_RECENT_APPROVAL = 10
BONUS_VIP = 20

BLACKLIST_RVOL_FLOOR = 0.3
BLACKLIST_VOLUME_RATIO = 0.2  # abaixo de 20% da media do universo


def compute_universe_avg_volume(ticker_snapshot: Dict[str, Dict]) -> float:
    volumes = [v.get("quote_volume", 0.0) for v in ticker_snapshot.values() if v.get("quote_volume", 0.0) > 0]
    return sum(volumes) / len(volumes) if volumes else 0.0


def compute_priority_score(
    pair: str,
    ticker_snapshot: Dict[str, Dict],
    universe_avg_volume: float,
    cached_scores: Optional[Dict[str, Dict]] = None,
    vip_pairs: Optional[List[str]] = None,
    recently_approved_pairs: Optional[List[str]] = None,
) -> float:
    """Somente-leitura sobre ticker 24h (bulk, ja obtido) + cache do ciclo
    anterior — nao dispara nenhuma chamada de API nova por par."""
    score = 0.0
    ticker = ticker_snapshot.get(pair, {})
    cached = (cached_scores or {}).get(pair, {})

    if cached.get("rvol", 0.0) >= RVOL_HIGH_THRESHOLD:
        score += BONUS_RVOL

    volume = ticker.get("quote_volume", 0.0)
    if universe_avg_volume > 0 and volume > universe_avg_volume:
        score += BONUS_VOLUME_ABOVE_AVG

    if abs(ticker.get("price_change_percent", 0.0)) > PRICE_CHANGE_THRESHOLD_PCT:
        score += BONUS_PRICE_CHANGE

    if cached.get("atr_percent", 0.0) >= ATR_PERCENT_HIGH_THRESHOLD:
        score += BONUS_ATR_PERCENT

    if cached.get("adx", 0.0) >= ADX_HIGH_THRESHOLD:
        score += BONUS_ADX

    last_price = ticker.get("last_price", 0.0)
    high = ticker.get("high_price", 0.0)
    low = ticker.get("low_price", 0.0)
    if high > 0 and last_price >= high * (1 - BREAKOUT_PROXIMITY_PCT / 100):
        score += BONUS_BREAKOUT
    elif low > 0 and last_price <= low * (1 + BREAKOUT_PROXIMITY_PCT / 100):
        score += BONUS_BREAKOUT

    # Liquidez: sem medicao real de spread/profundidade hoje — usa volume
    # 24h (1.5x a media do universo) como proxy documentado.
    if universe_avg_volume > 0 and volume >= universe_avg_volume * 1.5:
        score += BONUS_LIQUIDITY

    if cached.get("momentum_score", 0.0) >= MOMENTUM_HIGH_THRESHOLD:
        score += BONUS_MOMENTUM

    if recently_approved_pairs and pair in recently_approved_pairs:
        score += BONUS_RECENT_APPROVAL

    if vip_pairs and pair in vip_pairs:
        score += BONUS_VIP

    return score


def is_blacklisted(
    pair: str,
    ticker_snapshot: Dict[str, Dict],
    universe_avg_volume: float,
    cached_scores: Optional[Dict[str, Dict]] = None,
) -> bool:
    ticker = ticker_snapshot.get(pair, {})
    cached = (cached_scores or {}).get(pair, {})
    rvol = cached.get("rvol")
    if rvol is not None and rvol < BLACKLIST_RVOL_FLOOR:
        return True
    volume = ticker.get("quote_volume")
    if universe_avg_volume > 0 and volume is not None and volume < universe_avg_volume * BLACKLIST_VOLUME_RATIO:
        return True
    return False


def reorder_pairs_by_priority(
    pairs: List[str],
    ticker_snapshot: Dict[str, Dict],
    cached_scores: Optional[Dict[str, Dict]] = None,
    vip_pairs: Optional[List[str]] = None,
    recently_approved_pairs: Optional[List[str]] = None,
) -> List[str]:
    """Retorna uma NOVA lista (copia) reordenada por PRIORITY_SCORE
    decrescente, com pares blacklistados temporariamente empurrados para o
    final da fila. Nunca remove um par da lista original — so reordena.
    Se ticker_snapshot estiver vazio (ex.: falha de rede), devolve a lista
    original inalterada (fallback seguro para a ordem atual)."""
    if not ticker_snapshot:
        return list(pairs)

    avg_volume = compute_universe_avg_volume(ticker_snapshot)

    def sort_key(pair):
        blacklisted = is_blacklisted(pair, ticker_snapshot, avg_volume, cached_scores)
        priority = compute_priority_score(
            pair, ticker_snapshot, avg_volume, cached_scores, vip_pairs, recently_approved_pairs,
        )
        return (1 if blacklisted else 0, -priority)

    return sorted(pairs, key=sort_key)
