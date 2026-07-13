"""RFC V20.0 Fase 2 — Engine de Estatisticas.

Nao recalcula Win Rate/Profit Factor/Drawdown ja existentes em
TradeRegistry — testa apenas o que este modulo adiciona.
"""
import json
import os

import pytest

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics import statistics as stats


@pytest.fixture
def registry(tmp_path):
    return TradeRegistry(db_path=str(tmp_path / "trades.db"))


def _signal(symbol, direction="long"):
    return {
        "symbol": symbol, "timeframe": "1h", "direction": direction,
        "entry_price": 100.0, "stop_loss": 98.0,
        "take_profit_1": 104.0, "take_profit_2": 108.0,
        "quality_score": 0.75, "confidence_score": 0.80,
        "overall_score_value": 82.0, "consensus_score": 0.7,
        "risk_reward": 2.0, "trend": "uptrend", "kalman_direction": "UP",
        "classification_label": "ouro", "operational": {"leverage": 5},
        "signal_id": f"sig_{symbol}",
    }


def test_compute_metrics_no_trades_returns_safe_defaults(registry):
    metrics = stats.compute_metrics(registry)
    assert metrics["status"] == "no_trades"
    assert metrics["max_win_streak"] == 0
    assert metrics["win_rate_por_ativo"] == {}


def test_compute_metrics_reuses_base_statistics_fields(registry):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT", resultado="WIN", lucro_usdt=50.0, retorno_pct=4.0)
    metrics = stats.compute_metrics(registry)
    # campos que ja vem de TradeRegistry.get_statistics() (nao recalculados aqui)
    for field in ("win_rate", "profit_factor", "drawdown", "expectancy", "payoff"):
        assert field in metrics


def test_compute_profit_by_period_groups_by_day():
    trades = [
        {"closed_at": "2026-07-10T10:00:00+00:00", "lucro_usdt": 30.0, "perda_usdt": 0},
        {"closed_at": "2026-07-10T15:00:00+00:00", "lucro_usdt": 0, "perda_usdt": 10.0},
        {"closed_at": "2026-07-11T09:00:00+00:00", "lucro_usdt": 20.0, "perda_usdt": 0},
    ]
    daily = stats.compute_profit_by_period(trades, "day")
    assert daily["2026-07-10"] == 20.0
    assert daily["2026-07-11"] == 20.0


def test_compute_profit_by_period_ignores_open_trades():
    trades = [{"closed_at": None, "lucro_usdt": 999.0, "perda_usdt": 0}]
    assert stats.compute_profit_by_period(trades, "day") == {}


def test_compute_streaks_tracks_max_consecutive_wins_and_losses():
    trades = [
        {"resultado": "WIN", "closed_at": "2026-07-10T01:00:00"},
        {"resultado": "WIN", "closed_at": "2026-07-10T02:00:00"},
        {"resultado": "WIN", "closed_at": "2026-07-10T03:00:00"},
        {"resultado": "LOSS", "closed_at": "2026-07-10T04:00:00"},
        {"resultado": "LOSS", "closed_at": "2026-07-10T05:00:00"},
        {"resultado": "WIN", "closed_at": "2026-07-10T06:00:00"},
    ]
    streaks = stats.compute_streaks(trades)
    assert streaks["max_win_streak"] == 3
    assert streaks["max_loss_streak"] == 2


def test_compute_streaks_ignores_breakeven():
    trades = [
        {"resultado": "WIN", "closed_at": "2026-07-10T01:00:00"},
        {"resultado": "BREAKEVEN", "closed_at": "2026-07-10T02:00:00"},
        {"resultado": "WIN", "closed_at": "2026-07-10T03:00:00"},
    ]
    streaks = stats.compute_streaks(trades)
    assert streaks["max_win_streak"] == 2  # BREAKEVEN e filtrado, nao quebra a sequencia artificialmente


def test_compute_avg_duration_hours():
    trades = [
        {"opened_at": "2026-07-10T10:00:00+00:00", "closed_at": "2026-07-10T12:00:00+00:00"},
        {"opened_at": "2026-07-10T10:00:00+00:00", "closed_at": "2026-07-10T14:00:00+00:00"},
    ]
    assert stats.compute_avg_duration_hours(trades) == 3.0


def test_compute_avg_duration_hours_no_closed_trades_returns_none():
    assert stats.compute_avg_duration_hours([{"opened_at": "x", "closed_at": None}]) is None


def test_compute_win_rate_by_asset():
    trades = [
        {"asset": "BTCUSDT", "resultado": "WIN"},
        {"asset": "BTCUSDT", "resultado": "LOSS"},
        {"asset": "ETHUSDT", "resultado": "WIN"},
    ]
    result = stats.compute_win_rate_by_asset(trades)
    assert result["BTCUSDT"]["win_rate"] == 50.0
    assert result["ETHUSDT"]["win_rate"] == 100.0


def test_persist_metrics_writes_json_file(registry, tmp_path):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT", resultado="WIN", lucro_usdt=50.0)
    out_path = str(tmp_path / "metrics.json")
    result = stats.persist_metrics(registry, path=out_path)
    assert os.path.exists(out_path)
    with open(out_path, encoding="utf-8") as f:
        assert json.load(f) == result
