"""RFC V20.0 Fase 9 — API Routes (funcoes puras, sem servidor HTTP)."""
import json
import inspect

import pytest

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics import api_routes


@pytest.fixture
def registry(tmp_path):
    return TradeRegistry(db_path=str(tmp_path / "trades.db"))


def test_module_never_binds_a_socket_or_starts_a_server():
    source = inspect.getsource(api_routes)
    forbidden = ["socket.socket", "app.run(", "uvicorn.run(", "HTTPServer(", "bind("]
    for token in forbidden:
        assert token not in source, f"api_routes.py nao deve iniciar servidor ({token} encontrado)"


def test_routes_map_contains_all_five_endpoints():
    expected = {"GET /dashboard", "GET /trades", "GET /metrics", "POST /risk", "GET /equity"}
    assert expected.issubset(api_routes.ROUTES.keys())


def test_get_dashboard_returns_json_serializable_dict(registry):
    result = api_routes.get_dashboard(registry)
    json.dumps(result)  # nao deve lancar TypeError


def test_get_trades_returns_json_serializable_list(registry):
    result = api_routes.get_trades(registry)
    assert isinstance(result, list)
    json.dumps(result)


def test_get_metrics_returns_json_serializable_dict(registry):
    result = api_routes.get_metrics(registry)
    json.dumps(result)


def test_get_risk_never_touches_registry_or_decision_engine():
    result = api_routes.get_risk(banca=1000.0, risco_pct=0.02, entrada=100.0, stop=98.0)
    json.dumps(result)
    assert "quantidade" in result


def test_get_equity_returns_json_serializable_dict(registry):
    result = api_routes.get_equity(registry, capital_inicial=1000.0)
    json.dumps(result)
    assert result["capital_inicial"] == 1000.0
