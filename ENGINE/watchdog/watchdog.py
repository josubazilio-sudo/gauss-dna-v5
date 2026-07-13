# -*- coding: utf-8 -*-
import logging
import time
import threading
import traceback
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

MAX_RESTART_ATTEMPTS = 3
COOLDOWN_SECONDS = 60


@dataclass
class WatchdogEntry:
    name: str
    check_fn: Callable[[], bool]
    restart_fn: Optional[Callable[[], None]] = None
    attempts: int = 0
    last_error: str = ""
    last_ok: float = 0.0
    cooldown_until: float = 0.0
    enabled: bool = True


class Watchdog:
    def __init__(self):
        self._entries: Dict[str, WatchdogEntry] = {}
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._alert_callback: Optional[Callable[[str], None]] = None

    def set_alert_callback(self, callback: Callable[[str], None]):
        self._alert_callback = callback

    def register(self, name: str, check_fn: Callable[[], bool],
                 restart_fn: Optional[Callable[[], None]] = None):
        self._entries[name] = WatchdogEntry(name=name, check_fn=check_fn, restart_fn=restart_fn)

    def unregister(self, name: str):
        self._entries.pop(name, None)

    def report_healthy(self, name: str):
        entry = self._entries.get(name)
        if entry:
            entry.last_ok = time.time()
            entry.attempts = 0
            entry.last_error = ""

    def report_error(self, name: str, error: str):
        entry = self._entries.get(name)
        if not entry:
            return
        entry.last_error = error
        entry.attempts += 1
        log.warning("Watchdog: %s reported error (attempt %d/%d): %s",
                    name, entry.attempts, MAX_RESTART_ATTEMPTS, error)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info("Watchdog: iniciado")

    def stop(self):
        self._running = False
        log.info("Watchdog: parado")

    def _loop(self):
        while self._running:
            now = time.time()
            for entry in list(self._entries.values()):
                if not entry.enabled:
                    continue
                if now < entry.cooldown_until:
                    continue
                try:
                    ok = entry.check_fn()
                except Exception as e:
                    ok = False
                    entry.last_error = str(e)
                    log.error("Watchdog: check %s falhou com excecao: %s", entry.name, e)

                if ok:
                    entry.last_ok = now
                    entry.attempts = 0
                else:
                    entry.attempts += 1
                    log.warning("Watchdog: %s NAO RESPONDE (tentativa %d/%d)",
                                entry.name, entry.attempts, MAX_RESTART_ATTEMPTS)

                    if entry.attempts >= MAX_RESTART_ATTEMPTS and entry.restart_fn:
                        try:
                            log.info("Watchdog: reiniciando %s...", entry.name)
                            entry.restart_fn()
                            entry.attempts = 0
                            entry.last_error = ""
                            entry.cooldown_until = time.time() + COOLDOWN_SECONDS
                            self._alert(f"Watchdog: {entry.name} reiniciado apos {MAX_RESTART_ATTEMPTS} falhas")
                        except Exception as e:
                            err = f"Falha ao reiniciar {entry.name}: {e}"
                            log.error("Watchdog: %s", err)
                            entry.last_error = err
                            self._alert(f"Watchdog: ERRO ao reiniciar {entry.name}")

            time.sleep(15)

    def _alert(self, message: str):
        log.warning("Watchdog ALERTA: %s", message)
        if self._alert_callback:
            try:
                self._alert_callback(message)
            except Exception as e:
                log.error("Watchdog: erro ao enviar alerta: %s", e)
