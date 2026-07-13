import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from CORE.events.event_bus import EventBus
from CORE.events.events import EventTypes
from CORE.events.publishers import Publisher
from main import _publish_validation_blocked


def test_publisher_decision_rejected_emits_decision_rejected_event():
    bus = EventBus()
    publisher = Publisher(bus)
    received = []
    bus.subscribe(EventTypes.DECISION_REJECTED, lambda event: received.append(event))

    publisher.decision_rejected({"symbol": "BTCUSDT", "status": "REJECTED"})

    assert len(received) == 1
    assert received[0].data["symbol"] == "BTCUSDT"
    assert received[0].data["status"] == "REJECTED"


def test_validation_blocked_publishes_rejection_not_trade_closed():
    bus = EventBus()
    publisher = Publisher(bus)
    rejected = []
    closed = []
    bus.subscribe(EventTypes.DECISION_REJECTED, lambda event: rejected.append(event))
    bus.subscribe(EventTypes.TRADE_CLOSED, lambda event: closed.append(event))

    _publish_validation_blocked(
        publisher,
        {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "direction": "LONG",
            "signal_id": "sig-1",
        },
        "Coherence Score 55 < 60",
    )

    assert len(rejected) == 1
    assert rejected[0].data["pair"] == "BTCUSDT"
    assert rejected[0].data["reason"] == "VALIDATION BLOCKED: Coherence Score 55 < 60"
    assert closed == []
