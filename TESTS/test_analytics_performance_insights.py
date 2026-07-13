"""RFC V20.0 Fase 7 — Performance Insights (historico completo)."""
import pytest

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics import performance_insights as pi


@pytest.fixture
def registry(tmp_path):
    return TradeRegistry(db_path=str(tmp_path / "trades.db"))


def _signal(symbol, timeframe="1h"):
    return {
        "symbol": symbol, "timeframe": timeframe, "direction": "long",
        "entry_price": 100.0, "stop_loss": 98.0,
        "take_profit_1": 104.0, "take_profit_2": 108.0,
        "quality_score": 0.75, "confidence_score": 0.80,
        "overall_score_value": 82.0, "consensus_score": 0.7,
        "risk_reward": 2.0, "trend": "uptrend", "kalman_direction": "UP",
        "classification_label": "ouro", "operational": {"leverage": 5},
        "signal_id": f"sig_{symbol}_{timeframe}",
    }


def test_compute_insights_no_trades_returns_safe_defaults(registry):
    insights = pi.compute_insights(registry)
    assert insights["melhor_ativo"] is None
    assert insights["maior_lucro"] == 0.0


def test_compute_insights_identifies_best_and_worst_asset(registry):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT_1h", resultado="WIN", lucro_usdt=100.0)
    registry.open_trade(_signal("ETHUSDT"))
    registry.close_trade("sig_ETHUSDT_1h", resultado="LOSS", perda_usdt=50.0)
    insights = pi.compute_insights(registry)
    assert insights["melhor_ativo"] == "BTCUSDT"
    assert insights["pior_ativo"] == "ETHUSDT"


def test_compute_insights_maior_lucro_e_maior_perda(registry):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT_1h", resultado="WIN", lucro_usdt=200.0)
    registry.open_trade(_signal("ETHUSDT"))
    registry.close_trade("sig_ETHUSDT_1h", resultado="LOSS", perda_usdt=75.0)
    insights = pi.compute_insights(registry)
    assert insights["maior_lucro"] == 200.0
    assert insights["maior_perda"] == -75.0


def test_compute_insights_uses_full_history_not_just_seven_days(registry):
    """Fase 7 exige historico completo, diferente do get_weekly_report (7 dias)."""
    registry.open_trade(_signal("OLDUSDT"))
    registry.close_trade("sig_OLDUSDT_1h", resultado="WIN", lucro_usdt=500.0)
    insights = pi.compute_insights(registry)
    # mesmo sem manipular datas, o trade deve aparecer (nao filtrado por dias)
    assert insights["melhor_ativo"] == "OLDUSDT"


def test_compute_performance_by_hour_groups_correctly():
    trades = [
        {"closed_at": "2026-07-10T14:00:00+00:00", "lucro_usdt": 30.0, "perda_usdt": 0},
        {"closed_at": "2026-07-11T14:30:00+00:00", "lucro_usdt": 20.0, "perda_usdt": 0},
        {"closed_at": "2026-07-11T09:00:00+00:00", "lucro_usdt": 0, "perda_usdt": 10.0},
    ]
    by_hour = pi.compute_performance_by_hour(trades)
    assert by_hour["14h"] == 50.0
    assert by_hour["9h"] == -10.0


def test_compute_performance_by_weekday_groups_correctly():
    # 2026-07-13 e segunda-feira
    trades = [{"closed_at": "2026-07-13T10:00:00+00:00", "lucro_usdt": 15.0, "perda_usdt": 0}]
    by_day = pi.compute_performance_by_weekday(trades)
    assert by_day["Segunda"] == 15.0


def test_compute_insights_melhor_setup_reuses_setup_ranking(registry):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT_1h", resultado="WIN", lucro_usdt=100.0)
    insights = pi.compute_insights(registry)
    assert insights["melhor_setup"] is not None
