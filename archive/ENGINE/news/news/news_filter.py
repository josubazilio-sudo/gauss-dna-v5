import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


MACRO_EVENTS = {
    "fomc": {
        "name": "FOMC (Federal Reserve)",
        "description": "Decisão de juros do Fed",
        "block_before_minutes": 120,
        "block_after_minutes": 60,
        "keywords": ["fomc", "fed", "federal reserve", "juros", "interest rate"],
    },
    "cpi": {
        "name": "CPI (Inflação EUA)",
        "description": "Índice de Preços ao Consumidor",
        "block_before_minutes": 60,
        "block_after_minutes": 30,
        "keywords": ["cpi", "inflação", "inflation", "ipca"],
    },
    "payroll": {
        "name": "Payroll (Empregos EUA)",
        "description": "Relatório de empregos não-agrícolas",
        "block_before_minutes": 60,
        "block_after_minutes": 30,
        "keywords": ["payroll", "empregos", "nonfarm", "unemployment"],
    },
    "fed_speech": {
        "name": "Discurso do Fed",
        "description": "Pronunciamento de membro do Fed",
        "block_before_minutes": 30,
        "block_after_minutes": 30,
        "keywords": ["fed speech", "powell", "fomc member"],
    },
    "btc_option_expiry": {
        "name": "Vencimento de Opções BTC",
        "description": "Vencimento de opções de Bitcoin",
        "block_before_minutes": 60,
        "block_after_minutes": 30,
        "keywords": ["bitcoin options", "btc expiry", "opções btc"],
    },
}


@dataclass
class NewsEventResult:
    blocking: bool
    event_name: str
    block_reason: str
    blocked_filters: List[str]


class NewsFilter:
    def __init__(self, enabled: bool = False):
        self._enabled = enabled
        self._events = MACRO_EVENTS.copy()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def check_block(
        self,
        now: Optional[datetime] = None,
        custom_events: Optional[List[str]] = None,
    ) -> NewsEventResult:
        if not self._enabled:
            return NewsEventResult(
                blocking=False, event_name="",
                block_reason="News filter disabled",
                blocked_filters=[],
            )
        return NewsEventResult(
            blocking=False, event_name="",
            block_reason="No events blocking (no real-time calendar)",
            blocked_filters=[],
        )

    def register_event(self, key: str, config: dict) -> None:
        self._events[key] = config
