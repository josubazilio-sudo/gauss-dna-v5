from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TradeDirection(Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(Enum):
    OPEN = "open"
    WIN = "win"
    LOSS = "loss"
    BREAK_EVEN = "break_even"


class ExitReason(Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT_1 = "take_profit_1"
    TAKE_PROFIT_2 = "take_profit_2"
    TRAILING_STOP = "trailing_stop"
    SIGNAL_CLOSED = "signal_closed"
    TIME_EXPIRY = "time_expiry"


@dataclass
class Trade:
    id: str
    pair: str
    direction: TradeDirection
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    quantity: float
    commission_paid: float
    funding_paid: float
    slippage_paid: float
    status: TradeStatus
    pnl: float
    pnl_percent: float
    holding_bars: int
    atr_at_entry: float
    setup: str
    regime: str
    r_multiple: float
    exit_reason: Optional[ExitReason]
    trailing_stop_activated: bool = False
    break_even_activated: bool = False
    pyramiding_index: int = 0


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    commission_pct: float = 0.001
    funding_rate: float = 0.0
    slippage_pct: float = 0.0005
    latency_bars: int = 0
    position_size_pct: float = 0.02
    max_positions: int = 1
    pyramiding: bool = False
    pyramiding_levels: int = 0
    trailing_stop_activation: float = 0.0
    trailing_stop_distance: float = 0.0
    break_even_activation: float = 0.0
    partial_tp1_pct: float = 0.5
    use_atr_stop: bool = True
    atr_stop_multiplier: float = 1.5
    atr_tp1_multiplier: float = 2.0
    atr_tp2_multiplier: float = 3.5
    max_bars_hold: int = 0


@dataclass
class BacktestResult:
    config: BacktestConfig = field(default_factory=BacktestConfig)
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    recovery_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    kelly_percentage: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_drawdown: float = 0.0
    ulcer_index: float = 0.0
    avg_r: float = 0.0
    total_r: float = 0.0
    avg_holding_bars: float = 0.0
    final_capital: float = 0.0
    total_commission: float = 0.0
    total_funding: float = 0.0
    total_slippage: float = 0.0
    profit_by_setup: Dict[str, float] = field(default_factory=dict)
    profit_by_regime: Dict[str, float] = field(default_factory=dict)
    profit_by_hour: Dict[str, float] = field(default_factory=dict)
    profit_by_day: Dict[str, float] = field(default_factory=dict)
    profit_by_pair: Dict[str, float] = field(default_factory=dict)
    profit_by_timeframe: Dict[str, float] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    walk_forward_score: float = 0.0
    monte_carlo_confidence: float = 0.0
    robustness_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "expectancy": self.expectancy,
            "net_profit": self.net_profit,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "recovery_factor": self.recovery_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "kelly_percentage": self.kelly_percentage,
            "max_drawdown_pct": self.max_drawdown_pct,
            "avg_drawdown": self.avg_drawdown,
            "ulcer_index": self.ulcer_index,
            "avg_r": self.avg_r,
            "total_r": self.total_r,
            "final_capital": self.final_capital,
            "walk_forward_score": self.walk_forward_score,
            "monte_carlo_confidence": self.monte_carlo_confidence,
            "robustness_score": self.robustness_score,
        }


@dataclass
class WalkForwardResult:
    in_sample_score: float = 0.0
    out_sample_score: float = 0.0
    wfa_score: float = 0.0
    parameter_stability: float = 0.0
    windows: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MonteCarloResult:
    mean_return: float = 0.0
    median_return: float = 0.0
    std_return: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    probability_positive: float = 0.0
    probability_profit_factor_gt_1: float = 0.0
    probability_max_dd_lt_10: float = 0.0
    confidence_score: float = 0.0
    simulations: int = 0


@dataclass
class RobustnessResult:
    robustness_score: float = 0.0
    parameter_sensitivity: Dict[str, float] = field(default_factory=dict)
    overfitting_score: float = 0.0
    underfitting_score: float = 0.0
    edge_decay_rate: float = 0.0


@dataclass
class OptimizationParam:
    name: str
    min_val: float
    max_val: float
    step: float


@dataclass
class OptimizationResult:
    best_params: Dict[str, float] = field(default_factory=dict)
    best_result: Optional[BacktestResult] = None
    total_runs: int = 0
    improvements: Dict[str, float] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    strategy_a: str = ""
    strategy_b: str = ""
    metric_deltas: Dict[str, float] = field(default_factory=dict)
    better_strategy: str = ""
    significance: float = 0.0


@dataclass
class AIRecommendation:
    category: str
    description: str
    evidence: str
    impact: str
    confidence: float
    priority: str
