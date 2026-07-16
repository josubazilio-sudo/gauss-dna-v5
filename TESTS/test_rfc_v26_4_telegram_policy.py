"""RFC V26.4 — Politica de envio para o Telegram (somente mensagens uteis).

Cobre exclusivamente should_send_telegram() — decisao pura sobre dois
relatorios (atual vs anterior), sem tocar em Telegram real, Scanner ou
Decision Engine.
"""
from SERVICES.telegram.telegram_policy import should_send_telegram


def _report(health="Saudavel", bugs=None, growth=None, bottlenecks=None, pending=None):
    return {
        "scanner_health": health,
        "potential_bugs": bugs or [],
        "gate_greatest_growth": growth,
        "potential_bottlenecks": bottlenecks or [],
        "pending_validations": pending or [],
    }


def test_first_report_of_session_always_sends():
    deve_enviar, motivo = should_send_telegram(_report(), None)
    assert deve_enviar is True
    assert "primeiro" in motivo.lower()


def test_no_change_cancels_send():
    prev = _report(health="Saudavel")
    curr = _report(health="Saudavel")
    deve_enviar, motivo = should_send_telegram(curr, prev)
    assert deve_enviar is False
    assert "sem mudanca" in motivo.lower()


def test_health_change_triggers_send():
    prev = _report(health="Saudavel")
    curr = _report(health="Critico")
    deve_enviar, motivo = should_send_telegram(curr, prev)
    assert deve_enviar is True
    assert "saude" in motivo.lower()


def test_new_bug_triggers_send():
    prev = _report(bugs=[])
    curr = _report(bugs=[{"gate": "Consensus", "delta_pp": 30.0}])
    deve_enviar, motivo = should_send_telegram(curr, prev)
    assert deve_enviar is True
    assert "bug" in motivo.lower()


def test_same_bug_repeated_does_not_trigger_send():
    bug = {"gate": "Consensus", "delta_pp": 30.0}
    prev = _report(bugs=[bug])
    curr = _report(bugs=[bug])
    deve_enviar, _ = should_send_telegram(curr, prev)
    assert deve_enviar is False


def test_abnormal_gate_growth_triggers_send():
    prev = _report(growth=None)
    curr = _report(growth={"gate": "Exaustao", "status": "anormal", "delta_pp": 28.0})
    deve_enviar, motivo = should_send_telegram(curr, prev)
    assert deve_enviar is True
    assert "Exaustao" in motivo


def test_new_bottleneck_triggers_send():
    prev = _report(bottlenecks=[{"gate": "RVOL", "pct": 40.0}])
    curr = _report(bottlenecks=[{"gate": "RVOL", "pct": 40.0}, {"gate": "ADX", "pct": 30.0}])
    deve_enviar, motivo = should_send_telegram(curr, prev)
    assert deve_enviar is True
    assert "gargalo" in motivo.lower()


def test_new_pending_validation_triggers_send():
    prev = _report(pending=[])
    curr = _report(pending=[{"param": "RVOL_MIN", "version": "V27"}])
    deve_enviar, motivo = should_send_telegram(curr, prev)
    assert deve_enviar is True
    assert "validacao" in motivo.lower()
