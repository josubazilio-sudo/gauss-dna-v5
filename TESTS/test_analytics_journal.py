"""RFC V20.0 Fase 5 — Diario Automatico (append-only, idempotente)."""
import json
import os

import pytest

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics import journal


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


def test_build_entry_includes_observacoes_for_win(registry):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT", resultado="WIN", lucro_usdt=40.0)
    trade = registry.get_closed_trades()[0]
    entry = journal.build_entry(trade)
    assert entry["resultado"] == "WIN"
    assert "lucro" in entry["observacoes"].lower()
    assert entry["lucro"] == 40.0


def test_append_new_entries_writes_jsonl(registry, tmp_path):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT", resultado="WIN", lucro_usdt=40.0)
    path = str(tmp_path / "journal.jsonl")
    entries = journal.append_new_entries(registry, path=path)
    assert len(entries) == 1
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert len(lines) == 1


def test_append_new_entries_is_idempotent_across_calls(registry, tmp_path):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT", resultado="WIN", lucro_usdt=40.0)
    path = str(tmp_path / "journal.jsonl")
    journal.append_new_entries(registry, path=path)
    second_call = journal.append_new_entries(registry, path=path)
    assert second_call == []  # nada novo, ja estava no diario
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f if l.strip()]
    assert len(lines) == 1  # nao duplicou


def test_append_new_entries_adds_only_new_trades(registry, tmp_path):
    registry.open_trade(_signal("BTCUSDT"))
    registry.close_trade("sig_BTCUSDT", resultado="WIN", lucro_usdt=40.0)
    path = str(tmp_path / "journal.jsonl")
    journal.append_new_entries(registry, path=path)

    registry.open_trade(_signal("ETHUSDT"))
    registry.close_trade("sig_ETHUSDT", resultado="LOSS", perda_usdt=15.0)
    new_entries = journal.append_new_entries(registry, path=path)
    assert len(new_entries) == 1
    assert new_entries[0]["ativo"] == "ETHUSDT"


def test_append_new_entries_empty_registry_no_crash(registry, tmp_path):
    path = str(tmp_path / "journal.jsonl")
    entries = journal.append_new_entries(registry, path=path)
    assert entries == []
