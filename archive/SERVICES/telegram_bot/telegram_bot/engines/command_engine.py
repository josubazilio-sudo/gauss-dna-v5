import logging
from typing import Dict, Callable
from ...bot_engine import BotEngine

log = logging.getLogger(__name__)

class CommandEngine:
    def __init__(self, bot_engine: BotEngine):
        self._bot = bot_engine
        self._commands: Dict[str, Callable] = {
            "status": self._get_status,
            "saldo": self._get_saldo,
            "performance": self._get_performance,
        }

    def execute(self, cmd: str) -> str:
        handler = self._commands.get(cmd)
        if handler:
            return handler()
        return "Comando desconhecido."

    def _get_status(self) -> str:
        snap = self._bot.get_monitoring_snapshot()
        return f"QuantOS Status: {self._bot.status.value.upper()}\n" \
               f"Posições: {snap.positions}\n" \
               f"Latência: {snap.connection.latency_ms:.1f}ms"

    def _get_saldo(self) -> str:
        bal = self._bot.position_manager._exchange.get_balance()
        return f"Saldo Total: {bal.total:.2f} USDT\nDisponível: {bal.free:.2f} USDT"

    def _get_performance(self) -> str:
        stats = self._bot.risk_manager.get_daily_report()
        return f"Performance Diária:\n{stats}"
