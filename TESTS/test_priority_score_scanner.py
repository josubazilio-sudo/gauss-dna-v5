"""RFC V19.3 — Prioridade Dinamica do Scanner.

PRIORITY_SCORE afeta APENAS a ordem de varredura. Nenhum destes testes
toca Decision Engine, gates, thresholds ou scoring real.
"""
from ENGINE.scanner import priority_score as ps


def _ticker(volume=1000.0, change_pct=0.0, high=100.0, low=90.0, last=95.0):
    return {
        "quote_volume": volume,
        "price_change_percent": change_pct,
        "high_price": high,
        "low_price": low,
        "last_price": last,
    }


def test_compute_universe_avg_volume_ignores_zero_entries():
    snapshot = {"AUSDT": _ticker(volume=100), "BUSDT": _ticker(volume=0), "CUSDT": _ticker(volume=300)}
    avg = ps.compute_universe_avg_volume(snapshot)
    assert avg == 200.0


def test_compute_universe_avg_volume_empty_snapshot():
    assert ps.compute_universe_avg_volume({}) == 0.0


def test_rvol_bonus_from_cache_not_from_ticker():
    snapshot = {"BTCUSDT": _ticker()}
    cached = {"BTCUSDT": {"rvol": 2.5}}
    score = ps.compute_priority_score("BTCUSDT", snapshot, 1000.0, cached_scores=cached)
    assert score >= ps.BONUS_RVOL


def test_no_cache_means_no_rvol_bonus_first_cycle():
    snapshot = {"BTCUSDT": _ticker()}
    score = ps.compute_priority_score("BTCUSDT", snapshot, 1000.0, cached_scores=None)
    assert score < ps.BONUS_RVOL  # sem historico, sem bonus de RVOL


def test_volume_above_average_bonus():
    snapshot = {"BTCUSDT": _ticker(volume=5000.0)}
    score = ps.compute_priority_score("BTCUSDT", snapshot, universe_avg_volume=1000.0)
    assert score >= ps.BONUS_VOLUME_ABOVE_AVG


def test_price_change_bonus_applies_to_both_directions():
    snapshot_up = {"AUSDT": _ticker(change_pct=8.0)}
    snapshot_down = {"BUSDT": _ticker(change_pct=-8.0)}
    score_up = ps.compute_priority_score("AUSDT", snapshot_up, 0.0)
    score_down = ps.compute_priority_score("BUSDT", snapshot_down, 0.0)
    assert score_up >= ps.BONUS_PRICE_CHANGE
    assert score_down >= ps.BONUS_PRICE_CHANGE


def test_breakout_bonus_near_24h_high():
    snapshot = {"AUSDT": _ticker(high=100.0, low=90.0, last=99.8)}
    score = ps.compute_priority_score("AUSDT", snapshot, 0.0)
    assert score >= ps.BONUS_BREAKOUT


def test_vip_bonus_applied():
    snapshot = {"BTCUSDT": _ticker()}
    score_vip = ps.compute_priority_score("BTCUSDT", snapshot, 0.0, vip_pairs=["BTCUSDT"])
    score_no_vip = ps.compute_priority_score("BTCUSDT", snapshot, 0.0, vip_pairs=["ETHUSDT"])
    assert score_vip - score_no_vip == ps.BONUS_VIP


def test_recent_approval_bonus_applied():
    snapshot = {"BTCUSDT": _ticker()}
    score_recent = ps.compute_priority_score("BTCUSDT", snapshot, 0.0, recently_approved_pairs=["BTCUSDT"])
    score_none = ps.compute_priority_score("BTCUSDT", snapshot, 0.0, recently_approved_pairs=[])
    assert score_recent - score_none == ps.BONUS_RECENT_APPROVAL


def test_priority_score_never_affects_decision_fields():
    """Garante que compute_priority_score nao aceita nem retorna nenhum
    campo de Decision Engine (quality/confidence/consensus/gates)."""
    import inspect
    sig = inspect.signature(ps.compute_priority_score)
    forbidden = {"quality", "confidence", "consensus", "hard_gate", "threshold"}
    assert not (forbidden & set(sig.parameters.keys()))


def test_is_blacklisted_low_rvol():
    cached = {"DEADUSDT": {"rvol": 0.1}}
    assert ps.is_blacklisted("DEADUSDT", {}, 1000.0, cached) is True


def test_is_blacklisted_low_volume_ratio():
    snapshot = {"DEADUSDT": _ticker(volume=50.0)}
    assert ps.is_blacklisted("DEADUSDT", snapshot, universe_avg_volume=1000.0) is True


def test_is_blacklisted_false_for_healthy_pair():
    snapshot = {"BTCUSDT": _ticker(volume=2000.0)}
    cached = {"BTCUSDT": {"rvol": 1.5}}
    assert ps.is_blacklisted("BTCUSDT", snapshot, 1000.0, cached) is False


def test_reorder_pairs_by_priority_puts_high_priority_first():
    pairs = ["AUSDT", "BUSDT", "CUSDT"]
    snapshot = {
        "AUSDT": _ticker(volume=100.0),
        "BUSDT": _ticker(volume=100.0),
        "CUSDT": _ticker(volume=100.0),
    }
    cached = {"CUSDT": {"rvol": 3.0}}  # CUSDT deve ir para o topo
    ordered = ps.reorder_pairs_by_priority(pairs, snapshot, cached_scores=cached)
    assert ordered[0] == "CUSDT"
    assert set(ordered) == set(pairs)  # nenhum par e perdido ou duplicado


def test_reorder_pairs_by_priority_pushes_blacklisted_to_end():
    pairs = ["GOODUSDT", "DEADUSDT"]
    snapshot = {
        "GOODUSDT": _ticker(volume=1000.0),
        "DEADUSDT": _ticker(volume=1000.0),
    }
    cached = {"DEADUSDT": {"rvol": 0.05}}
    ordered = ps.reorder_pairs_by_priority(pairs, snapshot, cached_scores=cached)
    assert ordered[-1] == "DEADUSDT"


def test_reorder_pairs_by_priority_fallback_on_empty_ticker():
    pairs = ["ZUSDT", "AUSDT", "MUSDT"]
    ordered = ps.reorder_pairs_by_priority(pairs, ticker_snapshot={})
    assert ordered == pairs  # fallback seguro: ordem original preservada


def test_reorder_pairs_by_priority_never_drops_or_duplicates_pairs():
    pairs = [f"PAIR{i}USDT" for i in range(50)]
    snapshot = {p: _ticker(volume=float(i)) for i, p in enumerate(pairs)}
    ordered = ps.reorder_pairs_by_priority(pairs, snapshot)
    assert sorted(ordered) == sorted(pairs)
    assert len(ordered) == len(pairs)
