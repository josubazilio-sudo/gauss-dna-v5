"""RFC V20.0 Fase 1 — Banco de Operacoes (trade_storage.py).

Somente-leitura sobre TradeRegistry — nao registra nada novo, so exporta.
"""
import json
import os

import pytest

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics import trade_storage


@pytest.fixture
def registry(tmp_path):
    return TradeRegistry(db_path=str(tmp_path / "trades.db"))


def _open_signal(symbol="BTCUSDT", direction="long", entry=100.0, stop=98.0,
                  tp1=104.0, tp2=108.0, quality=0.75, confidence=0.80,
                  overall=82.0, setup_trend="uptrend", setup_kalman="UP"):
    return {
        "symbol": symbol, "timeframe": "1h", "direction": direction,
        "entry_price": entry, "stop_loss": stop,
        "take_profit_1": tp1, "take_profit_2": tp2,
        "quality_score": quality, "confidence_score": confidence,
        "overall_score_value": overall, "consensus_score": 0.7,
        "risk_reward": 2.0, "trend": setup_trend, "kalman_direction": setup_kalman,
        "classification_label": "ouro", "operational": {"leverage": 5},
        "signal_id": f"sig_{symbol}",
    }


def test_collect_trades_maps_open_trade_to_schema(registry):
    registry.open_trade(_open_signal())
    trades = trade_storage.collect_trades(registry)
    assert len(trades) == 1
    t = trades[0]
    expected_keys = {
        "id", "data", "hora", "ativo", "direcao", "timeframe", "entrada",
        "stop", "tp1", "tp2", "score", "confidence", "quality", "setup",
        "status", "resultado", "lucro", "prejuizo", "duracao_horas",
    }
    assert expected_keys.issubset(t.keys())
    assert t["ativo"] == "BTCUSDT"
    assert t["direcao"] == "LONG"
    assert t["status"] == "OPEN"
    assert t["resultado"] is None


def test_collect_trades_closed_trade_has_duration_and_result(registry):
    registry.open_trade(_open_signal())
    registry.close_trade("sig_BTCUSDT", resultado="WIN", exit_price=104.0,
                          lucro_usdt=50.0, retorno_pct=4.0)
    trades = trade_storage.collect_trades(registry)
    assert len(trades) == 1
    t = trades[0]
    assert t["status"] == "CLOSED"
    assert t["resultado"] == "WIN"
    assert t["lucro"] == 50.0
    # duracao pode ser 0.0 (aberto e fechado quase no mesmo instante no teste)
    assert t["duracao_horas"] is not None


def test_export_trades_json_writes_file(registry, tmp_path):
    registry.open_trade(_open_signal())
    out_path = str(tmp_path / "trades.json")
    result = trade_storage.export_trades_json(registry, path=out_path)
    assert os.path.exists(out_path)
    with open(out_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data == result
    assert len(data) == 1


def test_export_trades_json_empty_registry_no_crash(registry, tmp_path):
    out_path = str(tmp_path / "trades.json")
    result = trade_storage.export_trades_json(registry, path=out_path)
    assert result == []
    with open(out_path, encoding="utf-8") as f:
        assert json.load(f) == []


def test_collect_trades_includes_both_open_and_closed(registry):
    registry.open_trade(_open_signal(symbol="BTCUSDT"))
    registry.open_trade(_open_signal(symbol="ETHUSDT"))
    registry.close_trade("sig_ETHUSDT", resultado="LOSS", perda_usdt=20.0)
    trades = trade_storage.collect_trades(registry)
    assert len(trades) == 2
    statuses = {t["status"] for t in trades}
    assert statuses == {"OPEN", "CLOSED"}


def test_does_not_mutate_registry_rows():
    """Garante que _to_schema nao modifica o dict original do registry."""
    from ENGINE.analytics.trade_storage import _to_schema
    row = {"id": "abc", "opened_at": "2026-07-12T10:00:00+00:00", "asset": "BTCUSDT",
           "direction": "LONG", "resultado": None, "closed_at": None}
    original = dict(row)
    _to_schema(row)
    assert row == original
