import pytest
from SERVICES.telegram.update_engine import UpdateEngine

def test_reversal_trigger():
    old = {"direction": "LONG"}
    new = {"direction": "SHORT"}
    assert UpdateEngine.get_update_type(old, new) == "🔄 REVERSÃO DE TENDÊNCIA"

def test_score_fortalecido():
    old = {"overall_score_value": 70.0}
    new = {"overall_score_value": 82.0}
    assert UpdateEngine.get_update_type(old, new) == "📈 SETUP FORTALECIDO"

def test_score_enfraquecido():
    old = {"overall_score_value": 80.0}
    new = {"overall_score_value": 68.0}
    assert UpdateEngine.get_update_type(old, new) == "📉 SETUP ENFRAQUECIDO"

def test_no_update_if_small_change():
    old = {"overall_score_value": 70.0}
    new = {"overall_score_value": 71.0}
    assert UpdateEngine.get_update_type(old, new) is None

def test_stop_adjusted():
    old = {"stop_loss": 100.0}
    new = {"stop_loss": 103.0}
    assert UpdateEngine.get_update_type(old, new) == "🛡 STOP AJUSTADO"
