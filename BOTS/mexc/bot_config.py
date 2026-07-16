import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

from ENGINE.scanner.scanner_config import LEVERAGE_MAX_USER

load_dotenv()

@dataclass
class BotConfig:
    enabled: bool = True
    dry_run: bool = True
    sandbox: bool = True
    pairs: List[str] = field(default_factory=list)
    timeframes: List[str] = field(default_factory=lambda: ["1h", "4h", "1d"])
    max_positions: int = 2
    pyramiding: bool = False
    pyramiding_levels: int = 1
    position_size_pct: float = 0.02
    leverage: float = LEVERAGE_MAX_USER

    # Baseline v4.0 — Quality Gates Institucionais
    min_confidence: float = 0.85
    min_quality: float = 0.85
    min_structural_score: float = 0.80
    min_institutional_score: float = 0.85
    required_classification: str = "ouro"
    min_risk_reward: float = 2.0

    # Baseline v4.0 — Distância de Entrada
    max_entry_distance_recalc: float = 0.005   # >0.50% → recalcular
    max_entry_distance_cancel: float = 0.01    # >1.00% → CANCELAR

    max_spread_pct: float = 0.001
    max_slippage_pct: float = 0.005
    circuit_breaker_consecutive_losses: int = 3
    circuit_breaker_cooldown_minutes: int = 60
    max_daily_loss_pct: float = 0.05
    max_daily_drawdown_pct: float = 0.10
    daily_position_limit: int = 10
    emergency_stop_loss_pct: float = 0.15
    reentry_enabled: bool = True
    reentry_cooldown_minutes: int = 120
    trailing_stop_activation_pct: float = 0.02
    trailing_stop_distance_pct: float = 0.01
    break_even_activation_pct: float = 0.01
    partial_tp1_pct: float = 0.5
    notification_events: List[str] = field(default_factory=lambda: [
        "trade_opened", "tp1_hit", "tp2_hit", "stop_hit",
        "error", "reconnected", "circuit_breaker", "daily_report",
    ])
    mexc_api_key: str = os.getenv("MEXC_API_KEY", "")
    mexc_api_secret: str = os.getenv("MEXC_API_SECRET", "")
    mexc_websocket_url: str = os.getenv("MEXC_WEBSOCKET_URL", "wss://wbs.mexc.com/ws")
    mexc_rest_url: str = os.getenv("MEXC_REST_URL", "https://api.mexc.com")
    heartbeat_interval_seconds: int = 10
    reconnection_attempts: int = 5
    reconnection_delay_seconds: int = 2
    order_timeout_seconds: int = 30
    sync_interval_seconds: int = 60

    def __post_init__(self):
        if not self.dry_run:
            if not self.mexc_api_key:
                raise ValueError("MEXC_API_KEY nao configurada no .env")
            if not self.mexc_api_secret:
                raise ValueError("MEXC_API_SECRET nao configurada no .env")
