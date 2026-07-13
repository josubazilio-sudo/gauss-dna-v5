"""Cache - armazenamento, políticas, invalidação, estatísticas e relatórios."""

from .cache_store import CacheStore, CacheEntry
from .cache_stats import CacheStats
from .cache_report import CacheReport
from .cache_policy import CachePolicy
from .cache_manager import CacheManager
from .cache_invalidator import CacheInvalidator

__all__ = [
    "CacheStore",
    "CacheEntry",
    "CacheStats",
    "CacheReport",
    "CachePolicy",
    "CacheManager",
    "CacheInvalidator",
]
