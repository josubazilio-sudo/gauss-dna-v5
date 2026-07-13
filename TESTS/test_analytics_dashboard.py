"""RFC V20.0 Fase 3 — Dashboard (funcao pura de consolidacao)."""
import pytest

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics import dashboard


@pytest.fixture
def registry(tmp_path):
    return TradeRegistry(db_path=str(tmp_path / "trades.db"))


def _signal(symbol):
    return {
        "symbol": symbol, "timeframe": "1h", "direction": "long",
        "entry_price": 100.0, "stop_loss": 98.0,
        "take_profit_1": 104.0, "take_profit_2": 108.0,
        "quality_score": 0.75, "confidence_score": 0.80,
        "overall_score_value": 82.0, "consensus_score": 0.7,
        "risk_reward": 2.0, "trend": "uptrend", "kalman_direction": "UP",
        "classification_label": "ouro", "operational": {"leverage": 5},
        "signal_id": f"sig_{symbol}",
    }


def test_build_dashboard_empty_registry_no_crash(registry):
    d = dashboard.build_dashboard(registry)
    assert d["operacoes_hoje"] == 0
    assert d["win_rate"] is None or isinstance(d["win_rate"], (int, float))


def test_build_dashboard_uses_scanner_health_param(registry):
    health = {"loop_status": "RUNNING", "next_cycle_in_s": 42}
    d = dashboard.build_dashboard(registry, scanner_health=health)
    assert d["scanner_status"] == "RUNNING"
    assert d["proximo_ciclo_em_s"] == 42


def test_build_dashboard_uses_market_health_param(registry):
    d = dashboard.build_dashboard(registry, market_health={"classificacao": "Excelente"})
    assert d["mercado"] == "Excelente"


def test_build_dashboard_counts_wins_and_losses_today(registry):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT", resultado="WIN", lucro_usdt=30.0)
    d = dashboard.build_dashboard(registry)
    assert d["operacoes_hoje"] == 1
    assert d["wins_hoje"] == 1
    assert d["lucro_hoje"] == 30.0


def test_build_dashboard_never_recomputes_win_rate_differently_from_statistics(registry):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT", resultado="WIN", lucro_usdt=30.0)
    from ENGINE.analytics import statistics as stats
    expected = stats.compute_metrics(registry)["win_rate"]
    d = dashboard.build_dashboard(registry)
    assert d["win_rate"] == expected


def test_build_dashboard_passes_banca_through(registry):
    d = dashboard.build_dashboard(registry, banca=500.0)
    assert d["banca"] == 500.0


def test_build_dashboard_insights_melhor_horario(registry):
    d = dashboard.build_dashboard(registry, insights={"melhor_horario": "14h"})
    assert d["melhor_horario"] == "14h"
