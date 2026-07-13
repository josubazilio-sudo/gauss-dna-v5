"""RFC V20.0 Fase 6 — Curva da Banca."""
import json
import os

import pytest

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics import equity


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


def test_build_equity_curve_no_trades(registry):
    data = equity.build_equity_curve(registry, capital_inicial=1000.0)
    assert data["capital_inicial"] == 1000.0
    assert data["capital_atual"] == 1000.0
    assert data["rentabilidade_pct"] == 0.0
    assert data["curva_diaria"] == []


def test_build_equity_curve_computes_capital_atual_and_rentabilidade(registry):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT", resultado="WIN", lucro_usdt=100.0)
    data = equity.build_equity_curve(registry, capital_inicial=1000.0)
    assert data["capital_atual"] == 1100.0
    assert data["rentabilidade_pct"] == 10.0


def test_cumulative_curve_accumulates_over_periods():
    curve = equity._cumulative_curve({"2026-07-10": 30.0, "2026-07-11": -10.0})
    assert curve[0]["equity_acumulado"] == 30.0
    assert curve[1]["equity_acumulado"] == 20.0


def test_persist_equity_curve_writes_file(registry, tmp_path):
    path = str(tmp_path / "equity.json")
    result = equity.persist_equity_curve(registry, capital_inicial=500.0, path=path)
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == result


def test_build_equity_curve_zero_capital_inicial_no_crash(registry):
    data = equity.build_equity_curve(registry, capital_inicial=0.0)
    assert data["rentabilidade_pct"] == 0.0
