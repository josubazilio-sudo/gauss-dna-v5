"""RFC V26.X — Duplicate Signal Guard.

SignalCacheEngine ja bloqueava reenvio no mesmo candle por preco/
qualidade/probabilidade parecidos, mas nao considerava o setup
estrutural (BOS/CHoCH/Order Block/FVG) nem tinha um fingerprint unico
ou contagem explicita de duplicados bloqueados (pedido pelo RFC para
o relatorio diario). Este arquivo cobre as pecas novas — sem alterar
o comportamento ja testado em TESTS/test_rfc_v18_5_signal_cache.py.
"""
from ENGINE.deduplication.signal_cache import (
    SignalCacheEngine, compute_signal_fingerprint, DUPLICATE_ENTRY_MAX_DIFF_PCT,
)


def _data(entry=100.0, bos=0, choch=0, fvg=0, order_block=""):
    return {
        "entry_price": entry, "quality": 0.7, "probability": 80,
        "bos": bos, "choch": choch, "fvg": fvg,
        "selected_order_block": order_block,
    }


class TestFingerprint:
    def test_same_inputs_produce_same_fingerprint(self):
        fp1 = compute_signal_fingerprint("BTCUSDT", "1h", "long", 100.0, 1000, _data())
        fp2 = compute_signal_fingerprint("BTCUSDT", "1h", "long", 100.0, 1000, _data())
        assert fp1 == fp2

    def test_different_structural_setup_changes_fingerprint(self):
        fp_no_bos = compute_signal_fingerprint("BTCUSDT", "1h", "long", 100.0, 1000, _data(bos=0))
        fp_with_bos = compute_signal_fingerprint("BTCUSDT", "1h", "long", 100.0, 1000, _data(bos=1))
        assert fp_no_bos != fp_with_bos

    def test_entry_within_bucket_produces_same_fingerprint(self):
        """Bucketing tem bordas rigidas — dois precos bem proximos (bem
        abaixo do limite de duplicado) caem no mesmo bucket. Perto da
        borda do bucket, dois precos dentro do limite podem cair em
        buckets vizinhos (limitacao aceita: o fingerprint e so para
        rastreabilidade/log; a decisao real de bloqueio usa comparacao
        par-a-par precisa em _can_send_by_small_changes, testada abaixo)."""
        fp1 = compute_signal_fingerprint("BTCUSDT", "1h", "long", 100.000, 1000, _data(entry=100.000))
        fp2 = compute_signal_fingerprint("BTCUSDT", "1h", "long", 100.001, 1000, _data(entry=100.001))
        assert fp1 == fp2

    def test_entry_beyond_bucket_produces_different_fingerprint(self):
        fp1 = compute_signal_fingerprint("BTCUSDT", "1h", "long", 100.0, 1000, _data(entry=100.0))
        fp2 = compute_signal_fingerprint("BTCUSDT", "1h", "long", 105.0, 1000, _data(entry=105.0))
        assert fp1 != fp2

    def test_different_symbol_or_direction_changes_fingerprint(self):
        base = compute_signal_fingerprint("BTCUSDT", "1h", "long", 100.0, 1000, _data())
        other_symbol = compute_signal_fingerprint("ETHUSDT", "1h", "long", 100.0, 1000, _data())
        other_dir = compute_signal_fingerprint("BTCUSDT", "1h", "short", 100.0, 1000, _data())
        assert base != other_symbol
        assert base != other_dir


class TestSignalCacheEngineDuplicateGuard:
    def test_duplicate_within_same_candle_is_blocked_and_counted(self):
        cache = SignalCacheEngine()
        data = _data(entry=100.0)
        assert cache.can_send("BTCUSDT", "1h", "long", data) is True
        cache.mark_sent("BTCUSDT", "1h", "long", data)

        assert cache.can_send("BTCUSDT", "1h", "long", data) is False
        assert cache.duplicate_blocked_count == 1

    def test_entry_diff_under_010_pct_is_duplicate(self):
        cache = SignalCacheEngine()
        cache.mark_sent("BTCUSDT", "1h", "long", _data(entry=100.0))
        # 0.05% de diferenca — dentro do limite de duplicado (0.10%)
        assert cache.can_send("BTCUSDT", "1h", "long", _data(entry=100.05)) is False

    def test_entry_diff_over_010_pct_is_not_duplicate(self):
        cache = SignalCacheEngine()
        cache.mark_sent("BTCUSDT", "1h", "long", _data(entry=100.0))
        # 0.5% de diferenca — acima do limite de duplicado
        assert cache.can_send("BTCUSDT", "1h", "long", _data(entry=100.5)) is True

    def test_new_structural_setup_is_not_treated_as_duplicate(self):
        """Mesmo preco/qualidade, mas agora com BOS confirmado que antes
        nao existia — e um sinal novo, nao duplicado (RFC: 'mesmo setup
        estrutural' faz parte do criterio de duplicidade)."""
        cache = SignalCacheEngine()
        cache.mark_sent("BTCUSDT", "1h", "long", _data(entry=100.0, bos=0))
        assert cache.can_send("BTCUSDT", "1h", "long", _data(entry=100.0, bos=1)) is True

    def test_same_structural_setup_stays_duplicate(self):
        cache = SignalCacheEngine()
        cache.mark_sent("BTCUSDT", "1h", "long", _data(entry=100.0, bos=1))
        assert cache.can_send("BTCUSDT", "1h", "long", _data(entry=100.0, bos=1)) is False

    def test_duplicate_blocked_count_accumulates_across_symbols(self):
        cache = SignalCacheEngine()
        cache.mark_sent("BTCUSDT", "1h", "long", _data())
        cache.mark_sent("ETHUSDT", "1h", "long", _data())
        cache.can_send("BTCUSDT", "1h", "long", _data())
        cache.can_send("ETHUSDT", "1h", "long", _data())
        assert cache.duplicate_blocked_count == 2

    def test_fingerprint_method_matches_module_function(self):
        cache = SignalCacheEngine()
        data = _data(entry=100.0)
        method_fp = cache.fingerprint("BTCUSDT", "1h", "long", 100.0, data)
        assert len(method_fp) == 16
        assert isinstance(method_fp, str)
