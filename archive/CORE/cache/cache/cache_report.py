"""Relatórios de cache."""

import logging

from .cache_stats import CacheStats

log = logging.getLogger(__name__)


class CacheReport:
    def generate(self, stats: CacheStats) -> str:
        s = stats.get_stats()
        report = (
            f"=== Cache Report ===\n"
            f"  Hits: {s['hits']}\n"
            f"  Misses: {s['misses']}\n"
            f"  Hit Ratio: {stats.get_ratio():.2%}"
        )
        log.debug("Cache report generated")
        return report
