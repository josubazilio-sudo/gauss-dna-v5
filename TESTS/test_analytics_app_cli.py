"""RFC V20.0 Fase 8 — App CLI (camada de apresentacao, somente-leitura)."""
from ENGINE.analytics import app_cli


def test_render_menu_lists_all_six_items():
    menu = app_cli.render_menu()
    for label in ("Dashboard", "Scanner", "Operacoes", "Analytics", "Gestao", "Configuracoes"):
        assert label in menu


def test_render_dashboard_no_crash_with_empty_dict():
    text = app_cli.render_dashboard({})
    assert "DASHBOARD" in text


def test_render_dashboard_shows_key_fields():
    data = {"scanner_status": "RUNNING", "win_rate": 55.0, "operacoes_hoje": 3}
    text = app_cli.render_dashboard(data)
    assert "RUNNING" in text
    assert "55.0" in text
    assert "3" in text


def test_render_operacoes_empty_list():
    text = app_cli.render_operacoes([])
    assert "Nenhuma operacao" in text


def test_render_operacoes_respects_limit():
    trades = [{"data": "2026-07-12", "hora": "10:00", "ativo": f"A{i}USDT",
               "direcao": "LONG", "timeframe": "1h", "status": "CLOSED", "resultado": "WIN"}
              for i in range(20)]
    text = app_cli.render_operacoes(trades, limit=5)
    assert text.count("USDT") == 5


def test_render_analytics_no_crash_empty_dicts():
    text = app_cli.render_analytics({}, {})
    assert "ANALYTICS" in text


def test_render_gestao_shows_all_fields():
    result = {"quantidade": 10.0, "valor_posicao": 1000.0, "perda_maxima": 20.0,
              "lucro_esperado": 40.0, "rr": 2.0, "alavancagem_sugerida": 5}
    text = app_cli.render_gestao(result)
    assert "10.0" in text
    assert "5x" in text


def test_render_configuracoes_lists_all_keys():
    config = {"QUANTOS_MODE": "LIVE", "MAX_SCAN_PAIRS": 300}
    text = app_cli.render_configuracoes(config)
    assert "QUANTOS_MODE" in text
    assert "LIVE" in text


def test_app_cli_never_imports_decision_or_scanner_logic():
    """Fase 8 exige que o App nao execute logica operacional."""
    import inspect
    source = inspect.getsource(app_cli)
    assert "ENGINE.decision" not in source
    assert "ENGINE.scanner" not in source
    assert "TradeRegistry" not in source
