from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime

@dataclass
class StrategyMetric:
    win_rate: float
    profit_factor: float
    max_drawdown: float
    expectancy: float
    sharpe_ratio: float
    trades_count: int

@dataclass
class EvolutionProposal:
    proposal_id: str
    strategy_name: str
    old_params: Dict[str, Any]
    new_params: Dict[str, Any]
    metrics_delta: Dict[str, float]
    improvement_score: float
    evidence: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class MarketRegimeReport:
    regime: str
    feature_importance: Dict[str, float]
    optimal_timeframes: List[str]
    suggested_filters: List[str]
