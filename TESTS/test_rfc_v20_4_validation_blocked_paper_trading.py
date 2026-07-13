import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.decision.signal_decision import SignalDecision
from main import CycleSignalResult, _paper_trade_decisions, _should_record_paper_trade


def _decision(**overrides):
    defaults = dict(
        symbol="BTCUSDT",
        timeframe="1h",
        direction="LONG",
        approved=True,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit_1=110.0,
        risk_reward=2.0,
    )
    defaults.update(overrides)
    return SignalDecision(**defaults)


def test_validation_blocked_signal_is_not_recorded_in_paper_trading():
    sd = _decision()
    data = {"_validation_blocked": True}

    assert _should_record_paper_trade(sd, data) is False


def test_valid_approved_signal_remains_eligible_for_paper_trading():
    sd = _decision()
    data = {"_validation_blocked": False}

    assert _should_record_paper_trade(sd, data) is True


def test_invalid_prices_are_not_recorded_in_paper_trading():
    sd = _decision(entry_price=0.0)
    data = {"_validation_blocked": False}

    assert _should_record_paper_trade(sd, data) is False


def test_paper_trading_uses_only_cycle_best_signal():
    weak = _decision(timeframe="30m", quality=0.60, consensus=0.70, risk_reward=2.0)
    best = _decision(timeframe="1h", quality=0.80, consensus=0.80, risk_reward=2.5)
    cycle_result = CycleSignalResult(
        pair="BTCUSDT",
        all_decisions=[weak, best],
        approved_signals=[weak, best],
        best_signal=best,
        best_is_approved=True,
    )

    assert _paper_trade_decisions(cycle_result, {"_validation_blocked": False}) == [best]
