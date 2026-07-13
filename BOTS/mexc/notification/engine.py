import logging
from typing import Dict, List, Optional

from CORE.events.event_bus import EventBus
from CORE.events.events import Event
from ..bot_config import BotConfig
from ..bot_types import BotEvent, DailyStats, Order, Position

log = logging.getLogger(__name__)


class NotificationEngine:
    def __init__(self, config: BotConfig, event_bus: EventBus):
        self._config = config
        self._bus = event_bus

    def notify_trade_opened(self, position: Position) -> None:
        msg = f"[NOVA OPERACAO] {position.side.value.upper()} {position.pair} @ {position.entry_price:.2f} (SL: {position.stop_loss:.2f}, TP1: {position.take_profit_1:.2f}, TP2: {position.take_profit_2:.2f})"
        self._send_notification(BotEvent.TRADE_OPENED, msg, {"position_id": position.id, "pair": position.pair})

    def notify_tp1_hit(self, position: Position, price: float) -> None:
        msg = f"[TP1] {position.pair} @ {price:.2f}. Parcial executada!"
        self._send_notification(BotEvent.TP1_HIT, msg, {"position_id": position.id, "pair": position.pair, "price": price})

    def notify_tp2_hit(self, position: Position, price: float) -> None:
        msg = f"[TP2 - ALVO FINAL] {position.pair} @ {price:.2f}. Operacao encerrada com lucro!"
        self._send_notification(BotEvent.TP2_HIT, msg, {"position_id": position.id, "pair": position.pair, "price": price})

    def notify_stop_hit(self, position: Position, price: float) -> None:
        msg = f"[STOP LOSS] {position.pair} @ {price:.2f}. Operacao encerrada."
        self._send_notification(BotEvent.STOP_HIT, msg, {"position_id": position.id, "pair": position.pair, "price": price})

    def notify_break_even(self, position: Position) -> None:
        msg = f"[BREAK EVEN] Stop movido para entrada ({position.entry_price:.2f}) em {position.pair}"
        self._send_notification(BotEvent.BREAK_EVEN, msg, {"position_id": position.id, "pair": position.pair})

    def notify_error(self, error: str) -> None:
        msg = f"[ERRO] {error}"
        self._send_notification(BotEvent.ERROR, msg, {"error": error})

    def notify_reconnection(self, success: bool) -> None:
        status = "OK" if success else "FALHOU"
        msg = f"[RECONEXAO] {status}"
        self._send_notification(BotEvent.RECONNECTED, msg, {"success": success})

    def notify_regime_change(self, pair: str, old_regime: str, new_regime: str) -> None:
        msg = f"[REGIME] {pair}: {old_regime.upper()} -> {new_regime.upper()}"
        self._send_notification(BotEvent.REGIME_CHANGE, msg, {"pair": pair, "old_regime": old_regime, "new_regime": new_regime})

    def notify_circuit_breaker(self, active: bool, reason: str) -> None:
        status = "ATIVADO" if active else "DESATIVADO"
        msg = f"[CIRCUIT BREAKER] {status}: {reason}"
        self._send_notification(BotEvent.CIRCUIT_BREAKER, msg, {"active": active, "reason": reason})

    def notify_daily_report(self, stats: DailyStats) -> None:
        msg = (
            f"[RELATORIO DIARIO] - {stats.date}\n"
            f"Trades: {stats.total_trades} | V: {stats.winning_trades} | D: {stats.losing_trades}\n"
            f"Acerto: {stats.winning_trades / max(stats.total_trades, 1):.1%}\n"
            f"P&L: {stats.net_pnl:+.2f} USDT | DD: {stats.max_drawdown:.2%}"
        )
        self._send_notification(BotEvent.DAILY_REPORT, msg, {"stats": stats.__dict__})

    def _send_notification(self, event_type: str, message: str, payload: dict) -> None:
        log.info("NotificationEngine [%s]: %s", event_type, message)
        evt_data = {"message": message, **payload}
        event = Event(type=event_type, data=evt_data)
        self._bus.publish(event)
