"""RFC V26.8 — Conflito MTF deve considerar so decisoes aprovadas.

main.py chamava DecisionEngine.detect_mtf_conflict(all_decisions) — TODAS
as decisoes avaliadas no ciclo para o par, aprovadas OU rejeitadas. A
direcao de um timeframe rejeitado (por RVOL fraco, consenso baixo, etc.)
nao e uma leitura validada do mercado, mas era usada do mesmo jeito para
vetar um sinal ja aprovado por todos os gates — bloqueando por ruido, nao
por divergencia real. Confirmado em producao: 6 de 7 sinais aprovados
bloqueados por "Conflito MTF" apos os fixes anteriores (V26.6/V26.7).

Correcao: main.py agora passa approved_this_pair (so decisoes aprovadas
neste ciclo para o par) para detect_mtf_conflict(). O comportamento do
Hard Gate (divergencia real entre timeframes aprovados ainda bloqueia)
e preservado — so o ruido de rejeitados deixa de contar.
"""
import inspect

from ENGINE.decision.decision_engine import DecisionEngine
from ENGINE.decision.signal_decision import SignalDecision


def _sd(timeframe, direction, approved=True):
    return SignalDecision(symbol="TESTUSDT", timeframe=timeframe, direction=direction, approved=approved)


def test_no_conflict_when_only_one_timeframe_approved():
    """Caso comum: so 1 timeframe aprovado no ciclo — nada para conflitar."""
    approved_this_pair = [_sd("30m", "long")]
    result = DecisionEngine.detect_mtf_conflict(approved_this_pair)
    assert result.get("30m", False) is False


def test_conflict_when_two_approved_timeframes_disagree():
    """Duas leituras VALIDADAS (ambas aprovadas) discordando ainda bloqueia
    — o Hard Gate continua protegendo contra divergencia real."""
    approved_this_pair = [_sd("30m", "long"), _sd("4h", "short")]
    result = DecisionEngine.detect_mtf_conflict(approved_this_pair)
    assert result.get("30m", False) is True
    assert result.get("4h", False) is True


def test_no_conflict_when_two_approved_timeframes_agree():
    approved_this_pair = [_sd("30m", "long"), _sd("1h", "long")]
    result = DecisionEngine.detect_mtf_conflict(approved_this_pair)
    assert result.get("30m", False) is False
    assert result.get("1h", False) is False


def test_rejected_timeframe_direction_does_not_leak_into_conflict_check():
    """Reproduz o bug: um timeframe REJEITADO com direcao oposta nao deve
    mais influenciar o resultado — so o que esta em approved_this_pair
    (aprovados) importa."""
    all_decisions_including_rejected = [
        _sd("30m", "long", approved=True),
        _sd("4h", "short", approved=False),  # rejeitado por outro gate, direcao "ruido"
    ]
    approved_this_pair = [d for d in all_decisions_including_rejected if d.approved]

    result_old_behavior = DecisionEngine.detect_mtf_conflict(all_decisions_including_rejected)
    result_new_behavior = DecisionEngine.detect_mtf_conflict(approved_this_pair)

    assert result_old_behavior.get("30m", False) is True, "comportamento antigo: falso positivo"
    assert result_new_behavior.get("30m", False) is False, "comportamento novo: sem ruido de rejeitados"


def test_main_py_calls_detect_mtf_conflict_with_approved_this_pair():
    import main
    source = inspect.getsource(main)
    assert "DecisionEngine.detect_mtf_conflict(approved_this_pair)" in source
    assert "DecisionEngine.detect_mtf_conflict(all_decisions)" not in source
