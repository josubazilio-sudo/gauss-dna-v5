from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class BotStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    RECOVERING = "recovering"


class TimeInForce(Enum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


class ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


class SignalApproval(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass
class Order:
    id: str
    exchange_id: str
    pair: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float
    stop_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_amount: float = 0.0
    average_fill_price: float = 0.0
    commission: float = 0.0
    time_in_force: TimeInForce = TimeInForce.GTC
    signal_id: Optional[str] = None
    reduce_only: bool = False
    post_only: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    error: Optional[str] = None

    def is_fully_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    def is_open(self) -> bool:
        return self.status in (OrderStatus.OPEN, OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED)


@dataclass
class Position:
    id: str
    pair: str
    side: OrderSide
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    liquidation_price: float = 0.0
    margin: float = 0.0
    leverage: int = 1
    atr_at_entry: float = 0.0
    setup: str = ""
    regime: str = ""
    signal_id: str = ""
    trailing_stop_activated: bool = False
    break_even_activated: bool = False
    pyramiding_index: int = 0
    orders: List[Order] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    def pnl_percent(self) -> float:
        if self.entry_price == 0:
            return 0.0
        diff = self.current_price - self.entry_price
        if self.side == OrderSide.SELL:
            diff = -diff
        return (diff / self.entry_price) * 100.0


@dataclass
class Balance:
    total: float = 0.0
    free: float = 0.0
    used: float = 0.0
    unrealized_pnl: float = 0.0
    margin_ratio: float = 0.0


@dataclass
class DailyStats:
    date: str = ""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    max_drawdown: float = 0.0
    peak_balance: float = 0.0
    current_balance: float = 0.0


@dataclass
class ConnectionInfo:
    websocket: ConnectionStatus = ConnectionStatus.DISCONNECTED
    api: ConnectionStatus = ConnectionStatus.DISCONNECTED
    latency_ms: float = 0.0
    last_heartbeat: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class MonitoringSnapshot:
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    positions: int = 0
    orders: int = 0
    balance: Optional[Balance] = None
    connection: Optional[ConnectionInfo] = None
    daily_stats: Optional[DailyStats] = None
    circuit_breaker_active: bool = False
    consecutive_losses: int = 0
    daily_drawdown: float = 0.0


class BotEvent:
    TRADE_OPENED = "bot.trade_opened"
    TP1_HIT = "bot.tp1_hit"
    TP2_HIT = "bot.tp2_hit"
    STOP_HIT = "bot.stop_hit"
    BREAK_EVEN = "bot.break_even"
    ERROR = "bot.error"
    RECONNECTED = "bot.reconnected"
    REGIME_CHANGE = "bot.regime_change"
    CIRCUIT_BREAKER = "bot.circuit_breaker"
    DAILY_REPORT = "bot.daily_report"
    POSITION_UPDATED = "bot.position_updated"
    ORDER_UPDATED = "bot.order_updated"
