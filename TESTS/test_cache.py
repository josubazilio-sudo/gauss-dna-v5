import unittest
import sys
import time

sys.path.insert(0, 'C:\\Users\\josue\\QuantOS')

from CORE.cache import CacheStore, CacheEntry, CacheStats, CacheManager


class TestCacheStore(unittest.TestCase):
    def setUp(self):
        self.store = CacheStore()

    def test_set_and_get(self):
        self.store.set("key1", "value1", ttl=60)
        self.assertEqual(self.store.get("key1"), "value1")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get("missing"))

    def test_get_expired_returns_none(self):
        self.store.set("key2", "value2", ttl=0)
        time.sleep(0.01)
        self.assertIsNone(self.store.get("key2"))

    def test_delete_removes_entry(self):
        self.store.set("key3", "value3", ttl=60)
        self.store.delete("key3")
        self.assertIsNone(self.store.get("key3"))

    def test_clear_empties_store(self):
        self.store.set("a", 1, ttl=60)
        self.store.set("b", 2, ttl=60)
        self.store.clear()
        self.assertEqual(self.store.size(), 0)

    def test_size(self):
        self.store.set("x", 1, ttl=60)
        self.assertEqual(self.store.size(), 1)


class TestCacheEntry(unittest.TestCase):
    def test_is_expired_returns_true_for_zero_ttl(self):
        entry = CacheEntry("val", 0)
        time.sleep(0.01)
        self.assertTrue(entry.is_expired())

    def test_is_expired_returns_false_for_long_ttl(self):
        entry = CacheEntry("val", 3600)
        self.assertFalse(entry.is_expired())


class TestCacheStats(unittest.TestCase):
    def setUp(self):
        self.stats = CacheStats()

    def test_hit_increases_hits(self):
        self.stats.hit("k")
        self.stats.hit("k")
        stats = self.stats.get_stats()
        self.assertEqual(stats["hits"], 2)

    def test_miss_increases_misses(self):
        self.stats.miss("k")
        stats = self.stats.get_stats()
        self.assertEqual(stats["misses"], 1)

    def test_get_ratio_half(self):
        self.stats.hit("k")
        self.stats.miss("k")
        self.assertAlmostEqual(self.stats.get_ratio(), 0.5)

    def test_get_ratio_all_hits(self):
        self.stats.hit("a")
        self.stats.hit("b")
        self.assertEqual(self.stats.get_ratio(), 1.0)

    def test_get_ratio_zero_when_no_ops(self):
        self.assertEqual(self.stats.get_ratio(), 0.0)


class TestCacheManager(unittest.TestCase):
    def setUp(self):
        self.manager = CacheManager()

    def test_get_returns_none_for_missing(self):
        self.assertIsNone(self.manager.get("missing"))

    def test_set_and_get_flow(self):
        self.manager.set("mykey", "myvalue", ttl=300)
        self.assertEqual(self.manager.get("mykey"), "myvalue")

    def test_delete_works(self):
        self.manager.set("k", "v", ttl=60)
        self.manager.delete("k")
        self.assertIsNone(self.manager.get("k"))

    def test_clear_empties_all(self):
        self.manager.set("a", 1, ttl=60)
        self.manager.set("b", 2, ttl=60)
        self.manager.clear()
        self.assertIsNone(self.manager.get("a"))
        self.assertIsNone(self.manager.get("b"))


if __name__ == "__main__":
    unittest.main()
