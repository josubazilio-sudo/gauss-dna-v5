"""RFC V26.7 — Correcao de compute_main_reason(): deteccao de rompimento.

compute_main_reason() lia signal_data["patterns"] — uma chave que
SignalDecision.to_dict() nunca preenche (o dict real tem "bos"/"choch"/
"fvg" como contagens inteiras e "selected_order_block" como string).
Isso fazia "BOS confirmado"/"CHoCH confirmado" nunca aparecerem em
main_reason, mesmo com rompimento real detectado — e o Final Validation
("Mercado lateral + expectativa alta sem rompimento", main.py ~linha
1221-1225) usa exatamente esse texto para decidir se deixa passar um
sinal em mercado lateral. Resultado: todo sinal aprovado em mercado
lateral com expectativa alta era bloqueado, rompimento real ou nao.
"""
from ENGINE.common.operational import compute_main_reason


def _base_signal(**overrides):
    data = {
        "direction": "LONG", "trend": "uptrend", "kalman_direction": "UP",
        "rvol": 1.0, "bos": 0, "choch": 0, "fvg": 0,
        "selected_order_block": "",
    }
    data.update(overrides)
    return data


def test_bos_count_produces_bos_confirmado():
    reason = compute_main_reason(_base_signal(bos=2))
    assert "BOS confirmado" in reason


def test_choch_count_produces_choch_confirmado():
    reason = compute_main_reason(_base_signal(choch=1))
    assert "CHoCH confirmado" in reason


def test_selected_order_block_produces_order_block_detectado():
    reason = compute_main_reason(_base_signal(selected_order_block="OB_12345"))
    assert "Order Block detectado" in reason


def test_fvg_count_produces_fvg_identificado():
    reason = compute_main_reason(_base_signal(fvg=3))
    assert "FVG identificado" in reason


def test_zero_counts_never_claim_breakout():
    reason = compute_main_reason(_base_signal(bos=0, choch=0, fvg=0, selected_order_block=""))
    assert "BOS confirmado" not in reason
    assert "CHoCH confirmado" not in reason


def test_legacy_patterns_key_is_ignored_not_required():
    """O campo antigo (inexistente em producao) nao deve ser necessario
    nem usado — a funcao deve funcionar corretamente sem ele."""
    data = _base_signal(bos=1)
    assert "patterns" not in data
    reason = compute_main_reason(data)
    assert "BOS confirmado" in reason


def test_final_validation_breakout_text_contract():
    """Contrato exigido por main.py: has_breakout checa 'BOS' ou 'CHOCH'
    literalmente na string de main_reason (main.py ~linha 1223)."""
    reason_with_bos = compute_main_reason(_base_signal(bos=1))
    has_breakout = "BOS" in reason_with_bos or "CHOCH" in reason_with_bos
    assert has_breakout is True

    reason_without = compute_main_reason(_base_signal())
    has_breakout_none = "BOS" in reason_without or "CHOCH" in reason_without
    assert has_breakout_none is False
