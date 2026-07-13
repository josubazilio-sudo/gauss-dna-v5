import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable

from .backtest_types import (
    Trade, TradeDirection, BacktestConfig, BacktestResult,
    WalkForwardResult, MonteCarloResult, RobustnessResult,
    OptimizationParam, OptimizationResult, ComparisonResult,
    AIRecommendation,
)
from .backtest_config import DEFAULT_INITIAL_CAPITAL
from .trade_simulator import simulate_trade, close_trade
from .position_manager import PositionManager
from .risk_manager import RiskManager
from .statistics_engine import compute_statistics
from .walk_forward import walk_forward
from .monte_carlo import MonteCarloEngine
from .robustness import RobustnessEngine
from .optimizer import ParameterOptimizer
from .comparator import compare_strategies, compare_versions
from .recommendation import generate_recommendations
from .report import generate_report

log = logging.getLogger(__name__)


class BacktestEngine:
    def __init__(self, config: Optional[BacktestConfig] = None):
        self._config = config or BacktestConfig()
        self._position_mgr = PositionManager(self._config)
        self._risk_mgr = RiskManager(self._config)
        self._monte_carlo = MonteCarloEngine()
        self._robustness = RobustnessEngine()
        self._last_result: Optional[BacktestResult] = None

    def run(self, trades: List[Trade]) -> BacktestResult:
        if not trades:
            return BacktestResult(config=self._config)

        capital = self._config.initial_capital
        equity_curve = [capital]

        for trade in trades:
            capital += trade.pnl
            equity_curve.append(capital)

        result = compute_statistics(trades, equity_curve, self._config.initial_capital, capital)
        result.config = self._config
        result.trades = trades

        wf = walk_forward(trades, equity_curve, self._config.initial_capital, capital)
        result.walk_forward_score = wf.wfa_score

        mc = self._monte_carlo.simulate(trades, self._config.initial_capital)
        result.monte_carlo_confidence = mc.confidence_score

        rob = self._robustness.evaluate(trades)
        result.robustness_score = rob.robustness_score

        self._last_result = result
        return result

    def run_from_signals(
        self,
        pair: str,
        candles: List[Dict],
        get_signal_fn: Callable[[int, List[Dict]], Optional[Dict]],
        config: Optional[BacktestConfig] = None,
    ) -> BacktestResult:
        cfg = config or self._config
        self._position_mgr.reset()
        capital = cfg.initial_capital
        equity_curve = [capital]
        all_trades: List[Trade] = []

        for bar in range(20, len(candles)):
            signal = get_signal_fn(bar, candles)
            if signal and self._position_mgr.can_open():
                entry_candle = candles[bar]
                atr = signal.get("atr", entry_candle.get("atr", entry_candle["close"] * 0.01))
                trade = simulate_trade(
                    pair=pair,
                    direction=signal.get("direction", TradeDirection.LONG),
                    entry_time=datetime.fromtimestamp(entry_candle.get("timestamp", 0)),
                    entry_price=entry_candle["close"],
                    atr=atr,
                    setup=signal.get("setup", "unknown"),
                    regime=signal.get("regime", "unknown"),
                    config=cfg,
                )
                self._position_mgr.add_trade(trade)

            high = candles[bar]["high"]
            low = candles[bar]["low"]
            close = candles[bar]["close"]
            current_time = datetime.fromtimestamp(candles[bar].get("timestamp", 0))

            closed = self._position_mgr.update_positions(high, low, close, current_time)
            for t in closed:
                capital += t.pnl
                all_trades.append(t)

            equity_curve.append(capital)

        open_positions = self._position_mgr.open_positions()
        for t in open_positions:
            if len(candles) > 0:
                from .trade_simulator import close_trade
                from .backtest_types import ExitReason
                last = candles[-1]
                ct = close_trade(t, last["close"], datetime.fromtimestamp(last.get("timestamp", 0)),
                                 ExitReason.TIME_EXPIRY, cfg)
                capital += ct.pnl
                all_trades.append(ct)

        result = compute_statistics(all_trades, equity_curve, cfg.initial_capital, capital)
        result.config = cfg
        result.trades = all_trades

        wf = walk_forward(all_trades, equity_curve, cfg.initial_capital, capital)
        result.walk_forward_score = wf.wfa_score

        mc = self._monte_carlo.simulate(all_trades, cfg.initial_capital)
        result.monte_carlo_confidence = mc.confidence_score

        rob = self._robustness.evaluate(all_trades)
        result.robustness_score = rob.robustness_score

        self._last_result = result
        return result

    def analyze(self, result: BacktestResult) -> Dict:
        wf = walk_forward(result.trades, result.equity_curve,
                          result.config.initial_capital, result.final_capital)
        mc = self._monte_carlo.simulate(result.trades, result.config.initial_capital)
        rob = self._robustness.evaluate(result.trades)
        recs = generate_recommendations(result)
        return {
            "result": result,
            "walk_forward": wf,
            "monte_carlo": mc,
            "robustness": rob,
            "recommendations": recs,
        }

    def last_result(self) -> Optional[BacktestResult]:
        return self._last_result

    @property
    def position_manager(self) -> PositionManager:
        return self._position_mgr

    @property
    def risk_manager(self) -> RiskManager:
        return self._risk_mgr

    def create_optimizer(self) -> ParameterOptimizer:
        return ParameterOptimizer(lambda **p: self.run_from_signals(
            "", [], lambda b, c: p, BacktestConfig(**p)))
