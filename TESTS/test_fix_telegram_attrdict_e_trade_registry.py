"""Bug fixes revelados apos o fix do Coherence Score (RFC_FIX_COHERENCE_
SCORE_CAMPOS_AUSENTES.md) permitir que sinais reais cheguem mais longe
no pipeline:

1. telegram_formatter.py: _AttrDict (SERVICES/telegram/signal_compat.py)
   embrulha dicts aninhados automaticamente, quebrando isinstance(x, dict)
   para probability/coherence_score/weighted_vote/risk_decomposition/
   coherence_audit/overall_score.
2. trade_registry.py: open_trade() chamava OperationalCalculator.calculate()
   com assinatura errada quando "operational" nao vinha pre-calculado.
"""
import pytest

from SERVICES.telegram.signal_compat import wrap_signal, _AttrDict
from SERVICES.telegram.telegram_formatter import _unwrap, _get
from ENGINE.common.trade_registry import TradeRegistry


def _raw_signal_dict():
    return {
        "symbol": "CHZUSDT", "pair": "CHZUSDT", "timeframe": "1h",
        "direction": "short", "entry_price": 0.017, "stop_loss": 0.0172,
        "take_profit_1": 0.0166, "take_profit_2": 0.0164,
        "quality": 0.73, "confidence": 0.80, "consensus": 0.75,
        "risk_reward": 2.0,
        "probability": {"probability": 82.0, "level": "Alta"},
        "coherence_score": {"coherence_score": 85.3, "coherence_level": "Muito Alta"},
        "weighted_vote": {"concordance_pct": 91.2, "approved": True},
        "risk_decomposition": {"risco_total": 34.5},
        "coherence_audit": {"modulos": {"kalman": "OK"}},
        "overall_score": {"overall_score": 78.0, "overall_bar": "", "overall_tier": "OURO", "overall_tier_emoji": ""},
    }


def test_wrap_signal_double_wraps_nested_dicts_reproducing_the_bug():
    """Confirma o comportamento do _AttrDict que causava o bug original:
    ler um campo dict aninhado devolve outro _AttrDict, nao um dict puro."""
    wrapped = wrap_signal(_raw_signal_dict())
    prob = wrapped.probability
    assert isinstance(prob, _AttrDict)
    assert not isinstance(prob, dict)  # eis o bug: isinstance(prob, dict) e sempre False


def test_unwrap_recovers_plain_dict_from_attrdict():
    wrapped = wrap_signal(_raw_signal_dict())
    prob = _unwrap(wrapped.probability)
    assert isinstance(prob, dict)
    assert prob["probability"] == 82.0


def test_unwrap_is_noop_for_plain_dict():
    plain = {"a": 1}
    assert _unwrap(plain) is plain


def test_unwrap_is_noop_for_non_dict_values():
    assert _unwrap(42) == 42
    assert _unwrap("x") == "x"


def test_get_after_unwrap_reads_nested_value_correctly():
    wrapped = wrap_signal(_raw_signal_dict())
    prob = _unwrap(wrapped.probability)
    assert float(_get(prob, "probability", 0)) == 82.0


def test_all_nested_dict_fields_survive_unwrap_roundtrip():
    wrapped = wrap_signal(_raw_signal_dict())
    for field in ("probability", "coherence_score", "weighted_vote",
                  "risk_decomposition", "coherence_audit", "overall_score"):
        value = _unwrap(getattr(wrapped, field))
        assert isinstance(value, dict), f"{field} deveria ser dict apos _unwrap"


@pytest.fixture
def registry(tmp_path):
    return TradeRegistry(db_path=str(tmp_path / "trades.db"))


def _signal_without_operational(quantity=100.0, balance=1000.0, leverage=5):
    return {
        "symbol": "CHZUSDT", "timeframe": "1h", "direction": "short",
        "entry_price": 0.017, "stop_loss": 0.0172, "take_profit_1": 0.0166,
        "take_profit_2": 0.0164, "quality_score": 0.73, "confidence_score": 0.80,
        "consensus_score": 0.75, "risk_reward": 2.0,
        "trend": "trending_down", "kalman_direction": "DOWN",
        "classification_label": "ouro", "signal_id": "sig_CHZUSDT",
        "quantity": quantity, "balance": balance, "leverage": leverage,
        # sem "operational" -> forca o fallback que estava quebrado
    }


def test_open_trade_without_precomputed_operational_does_not_raise(registry):
    trade_id = registry.open_trade(_signal_without_operational())
    assert trade_id


def test_open_trade_fallback_computes_real_position_value(registry):
    trade_id = registry.open_trade(_signal_without_operational(quantity=100.0))
    trade = registry.get_trade_by_signal_id("sig_CHZUSDT")
    assert trade is not None
    assert trade["position_value"] == pytest.approx(100.0 * 0.017, rel=1e-3)


def test_open_trade_fallback_zero_quantity_no_crash(registry):
    trade_id = registry.open_trade(_signal_without_operational(quantity=0.0, balance=0.0))
    assert trade_id
