from dataclasses import dataclass, field
from typing import List


@dataclass
class BotConfig:
    enabled: bool = True
    dry_run: bool = True
    sandbox: bool = True  # Adicionado campo faltante
    pairs: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    timeframes: List[str] = field(default_factory=lambda: ["1h", "4h", "1d"])
    max_positions: int = 2
    pyramiding: bool = False
    pyramiding_levels: int = 1
    position_size_pct: float = 0.02
    min_confidence: float = 0.60
    min_quality: float = 0.60
    required_classification: str = "prata"
    min_risk_reward: float = 2.0
    max_spread_pct: float = 0.001
    max_slippage_pct: float = 0.005
    circuit_breaker_consecutive_losses: int = 3
    circuit_breaker_cooldown_minutes: int = 60
    max_daily_loss_pct: float = 0.05
    max_daily_drawdown_pct: float = 0.10
    daily_position_limit: int = 10
    emergency_stop_loss_pct: float = 0.15
    reentry_enabled: bool = False
    reentry_cooldown_minutes: int = 120
    trailing_stop_activation_pct: float = 0.02
    trailing_stop_distance_pct: float = 0.01
    break_even_activation_pct: float = 0.01
    partial_tp1_pct: float = 0.5
    notification_events: List[str] = field(default_factory=lambda: [
        "trade_opened", "tp1_hit", "tp2_hit", "stop_hit",
        "error", "reconnected", "circuit_breaker", "daily_report",
    ])
    mexc_api_key: str = ""
    mexc_api_secret: str = ""
    mexc_websocket_url: str = "wss://wbs.mexc.com/ws"
    mexc_rest_url: str = "https://api.mexc.com"
    heartbeat_interval_seconds: int = 10
    reconnection_attempts: int = 5
    reconnection_delay_seconds: int = 2
    order_timeout_seconds: int = 30
    sync_interval_seconds: int = 60
