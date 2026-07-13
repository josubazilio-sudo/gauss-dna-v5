import unittest
import sys

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.events import Event, EventTypes, EventBus, Publisher, SubscriberGroup
from CORE.events.event_registry import EventRegistry


class TestEventCreation(unittest.TestCase):
    def test_event_creation_with_name_and_data(self):
        event = Event("test.event", {"key": "value"})
        self.assertEqual(event.type, "test.event")
        self.assertEqual(event.data, {"key": "value"})

    def test_event_default_data_is_dict(self):
        event = Event("test.event")
        self.assertEqual(event.data, {})

    def test_event_has_timestamp(self):
        event = Event("test.event")
        self.assertIsNotNone(event.timestamp)

    def test_event_repr(self):
        event = Event("test.event", {"a": 1})
        self.assertIsNotNone(str(event))


class TestEventTypes(unittest.TestCase):
    def test_engine_start_value(self):
        self.assertEqual(EventTypes.ENGINE_START, "engine.start")

    def test_engine_stop_value(self):
        self.assertEqual(EventTypes.ENGINE_STOP, "engine.stop")

    def test_system_boot_value(self):
        self.assertEqual(EventTypes.SYSTEM_BOOT, "system.boot")

    def test_system_shutdown_value(self):
        self.assertEqual(EventTypes.SYSTEM_SHUTDOWN, "system.shutdown")

    def test_config_changed_value(self):
        self.assertEqual(EventTypes.CONFIG_CHANGED, "config.changed")

    def test_recovery_attempted_value(self):
        self.assertEqual(EventTypes.RECOVERY_ATTEMPTED, "recovery.attempted")

    def test_notification_sent_value(self):
        self.assertEqual(EventTypes.NOTIFICATION_SENT, "notification.sent")


class TestEventBus(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def test_publish_subscribe_flow(self):
        received = []
        self.bus.subscribe("test.msg", lambda e: received.append(e))
        event = Event("test.msg", {"x": 1})
        self.bus.publish(event)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["x"], 1)

    def test_subscribe_multiple_callbacks(self):
        results = []
        self.bus.subscribe("test.multi", lambda e: results.append(1))
        self.bus.subscribe("test.multi", lambda e: results.append(2))
        self.bus.publish(Event("test.multi"))
        self.assertEqual(len(results), 2)

    def test_unsubscribe_removes_callback(self):
        received = []
        def handler(e):
            received.append(e)
        self.bus.subscribe("test.unsub", handler)
        self.bus.unsubscribe("test.unsub", handler)
        self.bus.publish(Event("test.unsub"))
        self.assertEqual(len(received), 0)

    def test_publish_no_subscribers_does_not_error(self):
        try:
            self.bus.publish(Event("no.subscribers"))
        except Exception:
            self.fail("publish with no subscribers raised")

    def test_subscriber_error_does_not_crash_bus(self):
        self.bus.subscribe("test.err", lambda e: (_ for _ in ()).throw(RuntimeError("fail")))
        try:
            self.bus.publish(Event("test.err"))
        except Exception:
            self.fail("subscriber exception crashed the bus")


class TestEventRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = EventRegistry()

    def test_register_event(self):
        self.registry.register("test.event", "A test event")
        self.assertTrue(self.registry.is_registered("test.event"))

    def test_is_registered_false_for_unknown(self):
        self.assertFalse(self.registry.is_registered("unknown"))

    def test_list_events_returns_copy(self):
        self.registry.register("a", "desc a")
        self.registry.register("b", "desc b")
        events = self.registry.list_events()
        self.assertIn("a", events)
        self.assertIn("b", events)

    def test_validate_delegates_to_is_registered(self):
        self.registry.register("x", "desc")
        self.assertTrue(self.registry.validate("x"))
        self.assertFalse(self.registry.validate("y"))


class TestPublisherAndSubscriberGroup(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.publisher = Publisher(self.bus)

    def test_publisher_system_started(self):
        received = []
        self.bus.subscribe("engine.start", lambda e: received.append(e))
        self.publisher.system_started()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["status"], "started")

    def test_publisher_system_stopped(self):
        received = []
        self.bus.subscribe("engine.stop", lambda e: received.append(e))
        self.publisher.system_stopped()
        self.assertEqual(len(received), 1)

    def test_publisher_scan_complete(self):
        received = []
        self.bus.subscribe("scan.complete", lambda e: received.append(e))
        self.publisher.scan_complete({"symbols": ["BTC"]})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["symbols"], ["BTC"])

    def test_publisher_signal_generated(self):
        received = []
        self.bus.subscribe("signal.generated", lambda e: received.append(e))
        self.publisher.signal_generated({"action": "buy"})
        self.assertEqual(len(received), 1)

    def test_subscriber_group_subscribes(self):
        group = SubscriberGroup(self.bus)
        received = []
        group.subscribe("test.group", lambda e: received.append(e))
        self.bus.publish(Event("test.group"))
        self.assertEqual(len(received), 1)

    def test_subscriber_group_unsubscribes(self):
        group = SubscriberGroup(self.bus)
        received = []
        def handler(e):
            received.append(e)
        group.subscribe("test.grp", handler)
        group.unsubscribe("test.grp", handler)
        self.bus.publish(Event("test.grp"))
        self.assertEqual(len(received), 0)


if __name__ == "__main__":
    unittest.main()
