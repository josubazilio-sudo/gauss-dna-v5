# -*- coding: utf-8 -*-
import logging
import time
import os
import threading
from typing import Optional

from .watchdog import Watchdog
from ENGINE.scanner.scanner_config import MAX_SCAN_PAIRS

log = logging.getLogger(__name__)

# app._last_heartbeat so e atualizado uma vez por ciclo, no INICIO do
# _scan_loop (main.py) — nao durante o ciclo. Um threshold fixo de 120s
# presumia ciclos pequenos (poucos pares); com QUANTOS_MAX_SCAN_PAIRS=500
# reais contra a MEXC um ciclo legitimo leva ~20-30min (rate-gate do
# MexcDataProvider + processamento sequencial de decisao por par), entao
# o check disparava falso-positivo repetidamente a cada ~90s durante todo
# o ciclo (comprovado em producao: 7+ "reiniciando scanner..." num unico
# ciclo de 500 pares ainda em andamento). O threshold agora escala com o
# tamanho do universo configurado, com piso de 120s (preserva o
# comportamento para scans pequenos/debug).
_SECONDS_PER_PAIR_BUDGET = 5
_DEFAULT_SCAN_STALL_THRESHOLD = (
    max(120, MAX_SCAN_PAIRS * _SECONDS_PER_PAIR_BUDGET)
    if MAX_SCAN_PAIRS is not None
    else 3600
)


class WatchdogIntegration:
    def __init__(self, app=None):
        self._app = app
        self._wd = Watchdog()
        self._last_heartbeat: float = time.time()
        self._last_scan_count: int = 0
        self._scan_stall_threshold: int = _DEFAULT_SCAN_STALL_THRESHOLD

    def setup(self):
        app = self._app
        if not app:
            return

        self._wd.register("scanner", self._check_scanner, lambda: self._restart("scanner"))
        self._wd.register("telegram", self._check_telegram, lambda: self._restart("telegram"))
        self._wd.register("publisher", self._check_publisher, lambda: self._restart("publisher"))
        self._wd.register("discovery", self._check_discovery, lambda: self._restart("discovery"))

        self._wd.set_alert_callback(self._telegram_alert)
        self._wd.start()

    def stop(self):
        self._wd.stop()

    def report_healthy(self, module: str):
        self._wd.report_healthy(module)
        self._last_heartbeat = time.time()

    def _check_scanner(self) -> bool:
        app = self._app
        if not app:
            return False
        now = time.time()
        elapsed = now - getattr(app, "_last_heartbeat", now)
        if elapsed > self._scan_stall_threshold:
            log.warning("Watchdog: scanner parado ha %.0fs", elapsed)
            return False
        return True

    def _check_telegram(self) -> bool:
        return True

    def _check_publisher(self) -> bool:
        app = self._app
        if not app:
            return False
        return hasattr(app, "_publisher") and hasattr(app, "_bus")

    def _check_discovery(self) -> bool:
        app = self._app
        if not app:
            return False
        symbols = getattr(app, "_symbols", [])
        return len(symbols) > 0

    def _restart(self, module: str):
        app = self._app
        if not app:
            return
        log.info("Watchdog: reiniciando modulo %s...", module)
        if module == "scanner":
            from ENGINE.scanner.scanner_engine import ScannerEngine
            app._scanner = ScannerEngine()
        elif module == "telegram":
            from SERVICES.telegram.telegram_service import TelegramService
            if hasattr(app, "_bus"):
                app._telegram = TelegramService(app._bus)
        elif module == "discovery":
            symbols = app._discover_symbols()
            app._symbols = symbols
            log.info("Watchdog: rediscovery completed, %d symbols", len(symbols))

    def _telegram_alert(self, message: str):
        app = self._app
        if not app:
            return
        tg = getattr(app, "_telegram", None)
        if tg:
            try:
                # TelegramService nao possui send_alert() (nunca possuiu \u2014
                # essa chamada sempre lancava AttributeError, silenciosamente
                # engolido pelo except abaixo, entao nenhum alerta de
                # watchdog jamais chegou ao Telegram). O metodo real e
                # send_diagnostic(message: str).
                tg.send_diagnostic(f"\u26a0\ufe0f *WATCHDOG*: {message}")

            except Exception as e:
                log.error("Watchdog: erro ao enviar alerta Telegram: %s", e)
