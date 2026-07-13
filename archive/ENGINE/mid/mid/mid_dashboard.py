import logging
import time
from typing import Dict, List, Optional

from .mid_config import (
    MID_ENABLED,
    MID_INTERVAL_SECONDS,
    MID_TELEGRAM_ENABLED,
)
from .mid_collector import MIDCollector
from .mid_analyzer import MIDAnalyzer
from .mid_alert import MIDAlertEngine
from .mid_history import MIDHistory
from .mid_formatter import MIDFormatter

log = logging.getLogger(__name__)


class MIDashboard:
    def __init__(self):
        self._enabled = MID_ENABLED
        self._collector = MIDCollector()
        self._analyzer = MIDAnalyzer()
        self._alert_engine = MIDAlertEngine()
        self._history = MIDHistory()
        self._formatter = MIDFormatter()
        self._last_send: float = 0
        self._prev_snapshot: Optional[Dict] = None
        self._last_report = None

    def record_api_call(self):
        self._collector.record_api_call()

    def reset_api_calls(self):
        self._collector.reset_api_calls()

    def process_cycle(self, report, symbols: List[str]) -> Optional[str]:
        if not self._enabled:
            return None

        snapshot = self._collector.collect(report, symbols)
        insights = self._analyzer.analyze(snapshot, self._history.get_recent(10))
        snapshot["analyzer"] = insights

        alerts = self._alert_engine.check(snapshot, self._prev_snapshot)
        snapshot["alerts"] = alerts

        self._history.save(snapshot)

        self._last_report = snapshot
        self._prev_snapshot = snapshot

        now = time.time()
        should_send = (now - self._last_send) >= MID_INTERVAL_SECONDS or alerts

        if MID_TELEGRAM_ENABLED and should_send:
            self._last_send = now
            return self._formatter.format_dashboard(snapshot, insights, alerts)

        return None

    def force_dashboard(self) -> Optional[str]:
        if not self._last_report:
            return None
        snapshot = self._last_report
        insights = self._analyzer.analyze(snapshot, self._history.get_recent(10))
        alerts = []
        return self._formatter.format_dashboard(snapshot, insights, alerts)
