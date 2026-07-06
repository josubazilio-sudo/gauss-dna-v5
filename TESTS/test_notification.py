import unittest
import sys

sys.path.insert(0, 'C:\\Users\\josue\\QuantOS')

from CORE.notification import (
    NotificationRegistry, NotificationDispatcher,
    NotificationQueue, NotificationManager, NotificationChannel,
)


class TestNotificationRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = NotificationRegistry()

    def test_register_adds_entry(self):
        self.registry.register("email", "Test Notification")
        all_n = self.registry.list_all()
        self.assertEqual(len(all_n), 1)
        self.assertEqual(all_n[0]["channel"], "email")
        self.assertEqual(all_n[0]["title"], "Test Notification")

    def test_list_all_returns_copy(self):
        self.registry.register("sms", "Alert")
        self.registry.register("email", "Report")
        self.assertEqual(len(self.registry.list_all()), 2)

    def test_clear_removes_all(self):
        self.registry.register("push", "Hello")
        self.registry.clear()
        self.assertEqual(len(self.registry.list_all()), 0)


class TestNotificationDispatcher(unittest.TestCase):
    def setUp(self):
        self.dispatcher = NotificationDispatcher()

    def test_dispatch_with_handler(self):
        results = []
        def handler(title, msg):
            results.append((title, msg))
        self.dispatcher.register_channel("console", handler)
        self.dispatcher.dispatch("console", "Hello", "World")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], ("Hello", "World"))

    def test_dispatch_without_handler_does_not_error(self):
        try:
            self.dispatcher.dispatch("unknown", "x", "y")
        except Exception:
            self.fail("dispatch on unknown channel raised")

    def test_unregister_channel(self):
        def h(t, m):
            pass
        self.dispatcher.register_channel("ch", h)
        self.dispatcher.unregister_channel("ch")
        try:
            self.dispatcher.dispatch("ch", "t", "m")
        except Exception:
            self.fail("dispatch after unregister raised")


class TestNotificationQueue(unittest.TestCase):
    def setUp(self):
        self.queue = NotificationQueue()

    def test_enqueue_adds_item(self):
        self.queue.enqueue("sms", "Alert", "body")
        self.assertEqual(self.queue.size(), 1)

    def test_dequeue_all_returns_all(self):
        self.queue.enqueue("a", "t1", "m1")
        self.queue.enqueue("b", "t2", "m2")
        items = self.queue.dequeue_all()
        self.assertEqual(len(items), 2)
        self.assertEqual(self.queue.size(), 0)

    def test_dequeue_all_empty_returns_empty(self):
        items = self.queue.dequeue_all()
        self.assertEqual(items, [])


class TestNotificationManager(unittest.TestCase):
    def setUp(self):
        self.manager = NotificationManager()

    def test_send_flow(self):
        results = []
        self.manager.register_channel("log", lambda title, msg: results.append((title, msg)))
        self.manager.send("log", "Test", "Hello from test")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "Test")

    def test_send_registers_notification(self):
        self.manager.send("console", "Event", "detail")
        all_n = self.manager._registry.list_all()
        self.assertEqual(len(all_n), 1)
        self.assertEqual(all_n[0]["title"], "Event")

    def test_get_report(self):
        report = self.manager.get_report()
        self.assertIn("Notification Report", report)


class TestNotificationChannel(unittest.TestCase):
    def test_constructor(self):
        ch = NotificationChannel("test", enabled=True)
        self.assertEqual(ch.name, "test")
        self.assertTrue(ch.enabled)

    def test_send_disabled_channel(self):
        ch = NotificationChannel("disabled", enabled=False)
        try:
            ch.send("title", "msg")
        except Exception:
            self.fail("send on disabled channel raised")

    def test_enable_disable(self):
        ch = NotificationChannel("x")
        ch.disable()
        self.assertFalse(ch.enabled)
        ch.enable()
        self.assertTrue(ch.enabled)


if __name__ == "__main__":
    unittest.main()
