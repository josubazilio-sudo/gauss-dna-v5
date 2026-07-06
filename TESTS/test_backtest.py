import unittest
import sys
import math
import random
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.backtest.backtest_types import (
    Trade, TradeDirection, TradeStatus, ExitReason,
    BacktestConfig, BacktestResult, WalkForwardResult,
    MonteCarloResult, RobustnessResult, OptimizationParam,
    OptimizationResult, AIRecommendation,
)
from ENGINE.backtest.trade_simulator import simulate_trade, close_trade
from ENGINE.backtest.position_manager import PositionManager
from ENGINE.backtest.risk_manager import RiskManager
from ENGINE.backtest.statistics_engine import compute_statistics
from ENGINE.backtest.walk_forward import walk_forward
from ENGINE.backtest.monte_carlo import MonteCarloEngine
from ENGINE.backtest.robustness import RobustnessEngine
from ENGINE.backtest.optimizer import ParameterOptimizer
from ENGINE.backtest.comparator import compare_strategies, compare_versions
from ENGINE.backtest.recommendation import generate_recommendations
from ENGINE.backtest.report import generate_report
from ENGINE.backtest.portfolio import PortfolioSimulator
from ENGINE.backtest.backtest_engine import BacktestEngine

random.seed(42)


def make_trade(pnl: float = 10.0, direction: TradeDirection = TradeDirection.LONG,
               r_multiple: float = 1.0, setup: str = "bos",
               regime: str = "trending_up") -> Trade:
    status = TradeStatus.WIN if pnl > 0 else (TradeStatus.LOSS if pnl < 0 else TradeStatus.BREAK_EVEN)
    return Trade(
        id=f"t{random.randint(0, 99999)}",
        pair="BTCUSDT",
        direction=direction,
        entry_time=datetime.now(timezone.utc),
        exit_time=datetime.now(timezone.utc),
        entry_price=100.0,
        exit_price=100.0 + pnl / 1.0 if direction == TradeDirection.LONG else 100.0 - pnl / 1.0,
        stop_loss=99.0 if direction == TradeDirection.LONG else 101.0,
        take_profit_1=102.0,
        take_profit_2=104.0,
        quantity=abs(pnl) / 2 if pnl != 0 else 1.0,
        commission_paid=0.1,
        funding_paid=0.0,
        slippage_paid=0.05,
        status=TradeStatus.WIN if pnl > 0 else (TradeStatus.LOSS if pnl < 0 else TradeStatus.BREAK_EVEN),
        pnl=pnl,
        pnl_percent=pnl / 100.0,
        holding_bars=random.randint(1, 48),
        atr_at_entry=1.5,
        setup=setup,
        regime=regime,
        r_multiple=r_multiple,
        exit_reason=ExitReason.TAKE_PROFIT_1 if pnl > 0 else ExitReason.STOP_LOSS,
    )


def make_open_trade(direction: TradeDirection = TradeDirection.LONG,
                    r_multiple: float = 1.0, setup: str = "bos",
                    regime: str = "trending_up") -> Trade:
    return Trade(
        id=f"t{random.randint(0, 99999)}",
        pair="BTCUSDT",
        direction=direction,
        entry_time=datetime.now(timezone.utc),
        exit_time=None,
        entry_price=100.0,
        exit_price=None,
        stop_loss=99.0 if direction == TradeDirection.LONG else 101.0,
        take_profit_1=102.0,
        take_profit_2=104.0,
        quantity=1.0,
        commission_paid=0.0,
        funding_paid=0.0,
        slippage_paid=0.0,
        status=TradeStatus.OPEN,
        pnl=0.0,
        pnl_percent=0.0,
        holding_bars=0,
        atr_at_entry=1.5,
        setup=setup,
        regime=regime,
        r_multiple=r_multiple,
        exit_reason=None,
    )


# ============================================================
# UNIT TESTS — TRADE SIMULATOR
# ============================================================

class TestTradeSimulator(unittest.TestCase):

    def test_simulate_long(self):
        cfg = BacktestConfig(initial_capital=10000, position_size_pct=0.02)
        trade = simulate_trade("BTCUSDT", TradeDirection.LONG, datetime.now(), 100.0, 1.5,
                                "bos", "trending_up", cfg)
        self.assertEqual(trade.direction, TradeDirection.LONG)
        self.assertEqual(trade.status, TradeStatus.OPEN)
        self.assertIsNone(trade.exit_time)
        self.assertGreater(trade.quantity, 0)
        self.assertLess(trade.stop_loss, 100.0)
        self.assertGreater(trade.take_profit_1, 100.0)

    def test_simulate_short(self):
        cfg = BacktestConfig(initial_capital=10000, position_size_pct=0.02)
        trade = simulate_trade("ETHUSDT", TradeDirection.SHORT, datetime.now(), 50.0, 1.0,
                                "fvg", "ranging", cfg)
        self.assertEqual(trade.direction, TradeDirection.SHORT)
        self.assertGreater(trade.stop_loss, 50.0)
        self.assertLess(trade.take_profit_1, 50.0)

    def test_close_trade_win(self):
        cfg = BacktestConfig()
        trade = simulate_trade("BTCUSDT", TradeDirection.LONG, datetime.now(), 100.0, 1.5,
                                "bos", "trending_up", cfg)
        closed = close_trade(trade, 103.0, datetime.now(), ExitReason.TAKE_PROFIT_1, cfg)
        self.assertEqual(closed.status, TradeStatus.WIN)
        self.assertGreater(closed.pnl, 0)
        self.assertIsNotNone(closed.exit_time)

    def test_close_trade_loss(self):
        cfg = BacktestConfig()
        trade = simulate_trade("BTCUSDT", TradeDirection.LONG, datetime.now(), 100.0, 1.5,
                                "bos", "trending_up", cfg)
        closed = close_trade(trade, 97.0, datetime.now(), ExitReason.STOP_LOSS, cfg)
        self.assertEqual(closed.status, TradeStatus.LOSS)
        self.assertLess(closed.pnl, 0)

    def test_close_trade_short(self):
        cfg = BacktestConfig()
        trade = simulate_trade("BTCUSDT", TradeDirection.SHORT, datetime.now(), 100.0, 1.5,
                                "bos", "trending_up", cfg)
        closed = close_trade(trade, 97.0, datetime.now(), ExitReason.TAKE_PROFIT_1, cfg)
        self.assertEqual(closed.status, TradeStatus.WIN)
        self.assertGreater(closed.pnl, 0)

    def test_simulate_override_levels(self):
        cfg = BacktestConfig()
        trade = simulate_trade("BTCUSDT", TradeDirection.LONG, datetime.now(), 100.0, 1.5,
                                "bos", "trending_up", cfg,
                                stop_loss_override=95.0, tp1_override=110.0)
        self.assertAlmostEqual(trade.stop_loss, 95.0)
        self.assertAlmostEqual(trade.take_profit_1, 110.0)


# ============================================================
# UNIT TESTS — POSITION MANAGER
# ============================================================

class TestPositionManager(unittest.TestCase):

    def setUp(self):
        cfg = BacktestConfig(max_positions=2)
        self.pm = PositionManager(cfg)

    def test_can_open_initial(self):
        self.assertTrue(self.pm.can_open())

    def test_can_open_maxed(self):
        cfg = BacktestConfig(max_positions=1)
        pm = PositionManager(cfg)
        pm.add_trade(make_open_trade())
        self.assertFalse(pm.can_open())

    def test_open_positions(self):
        self.pm.add_trade(make_open_trade())
        self.pm.add_trade(make_open_trade())
        self.assertEqual(len(self.pm.open_positions()), 2)

    def test_all_trades(self):
        self.pm.add_trade(make_open_trade())
        self.assertEqual(len(self.pm.all_trades()), 1)

    def test_reset(self):
        self.pm.add_trade(make_open_trade())
        self.pm.reset()
        self.assertEqual(len(self.pm.open_positions()), 0)

    def test_pyramiding(self):
        cfg = BacktestConfig(pyramiding=True, pyramiding_levels=3)
        pm = PositionManager(cfg)
        for _ in range(2):
            pm.add_trade(make_open_trade())
        self.assertTrue(pm.can_open())
        pm.add_trade(make_open_trade())
        self.assertFalse(pm.can_open())


# ============================================================
# UNIT TESTS — RISK MANAGER
# ============================================================

class TestRiskManager(unittest.TestCase):

    def test_position_size(self):
        cfg = BacktestConfig(position_size_pct=0.02)
        rm = RiskManager(cfg)
        size = rm.position_size(10000, 100.0, 1.5)
        self.assertGreater(size, 0)

    def test_kelly(self):
        rm = RiskManager(BacktestConfig())
        k = rm.kelly_criterion(0.6, 100, 50)
        self.assertGreater(k, 0)
        self.assertLess(k, 1)

    def test_kelly_no_avg_loss(self):
        rm = RiskManager(BacktestConfig())
        k = rm.kelly_criterion(0.5, 100, 0)
        self.assertEqual(k, 0)

    def test_max_drawdown_check_pass(self):
        rm = RiskManager(BacktestConfig())
        curve = [100, 105, 103, 108]
        self.assertTrue(rm.max_drawdown_check(curve, 0.10))

    def test_max_drawdown_check_fail(self):
        rm = RiskManager(BacktestConfig())
        curve = [100, 105, 80, 110]
        self.assertFalse(rm.max_drawdown_check(curve, 0.10))


# ============================================================
# UNIT TESTS — STATISTICS ENGINE
# ============================================================

class TestStatisticsEngine(unittest.TestCase):

    def test_empty_trades(self):
        result = compute_statistics([], [], 10000, 10000)
        self.assertEqual(result.total_trades, 0)

    def test_all_winners(self):
        trades = [make_trade(10), make_trade(20), make_trade(15)]
        result = compute_statistics(trades, [10000, 10010, 10030, 10045], 10000, 10045)
        self.assertEqual(result.total_trades, 3)
        self.assertEqual(result.winning_trades, 3)
        self.assertAlmostEqual(result.win_rate, 1.0)

    def test_mixed_results(self):
        trades = [make_trade(10), make_trade(-5), make_trade(15), make_trade(-3), make_trade(8)]
        result = compute_statistics(trades, [], 10000, 10025)
        self.assertEqual(result.total_trades, 5)
        self.assertEqual(result.winning_trades, 3)
        self.assertAlmostEqual(result.win_rate, 0.6)
        self.assertGreater(result.profit_factor, 1.0)

    def test_profit_factor_zero_loss(self):
        trades = [make_trade(10), make_trade(20)]
        result = compute_statistics(trades, [], 10000, 10030)
        self.assertGreater(result.profit_factor, 0)

    def test_sharpe_ratio(self):
        trades = [make_trade(10) for _ in range(20)]
        result = compute_statistics(trades, [10000 + i * 10 for i in range(21)], 10000, 10200)
        self.assertIsInstance(result.sharpe_ratio, float)

    def test_profit_by_setup(self):
        t1 = make_trade(10, setup="bos")
        t2 = make_trade(5, setup="fvg")
        t3 = make_trade(-3, setup="bos")
        result = compute_statistics([t1, t2, t3], [], 10000, 10012)
        self.assertIn("bos", result.profit_by_setup)
        self.assertIn("fvg", result.profit_by_setup)


# ============================================================
# UNIT TESTS — WALK FORWARD
# ============================================================

class TestWalkForward(unittest.TestCase):

    def test_walk_forward_short_data(self):
        trades = [make_trade(10) for _ in range(5)]
        result = walk_forward(trades, [], 10000, 10050, 5)
        self.assertIsInstance(result, WalkForwardResult)

    def test_walk_forward_sufficient(self):
        trades = [make_trade(random.uniform(-20, 30)) for _ in range(100)]
        result = walk_forward(trades, [], 10000, 11000, 5)
        self.assertGreaterEqual(result.wfa_score, 0)
        self.assertLessEqual(result.wfa_score, 1)


# ============================================================
# UNIT TESTS — MONTE CARLO
# ============================================================

class TestMonteCarlo(unittest.TestCase):

    def test_monte_carlo_empty(self):
        mc = MonteCarloEngine(100)
        result = mc.simulate([], 10000)
        self.assertIsInstance(result, MonteCarloResult)

    def test_monte_carlo_positive(self):
        trades = [make_trade(10) for _ in range(50)]
        mc = MonteCarloEngine(200)
        result = mc.simulate(trades, 10000)
        self.assertGreater(result.probability_positive, 0.5)
        self.assertGreater(result.simulations, 0)

    def test_monte_carlo_fields(self):
        trades = [make_trade(random.uniform(-10, 20)) for _ in range(30)]
        mc = MonteCarloEngine(100)
        result = mc.simulate(trades, 10000)
        self.assertIsNotNone(result.mean_return)
        self.assertIsNotNone(result.var_95)
        self.assertIsNotNone(result.var_99)


# ============================================================
# UNIT TESTS — ROBUSTNESS
# ============================================================

class TestRobustness(unittest.TestCase):

    def test_robustness_empty(self):
        rob = RobustnessEngine()
        result = rob.evaluate([])
        self.assertIsInstance(result, RobustnessResult)

    def test_robustness_consistent(self):
        trades = [make_trade(10) for _ in range(50)]
        rob = RobustnessEngine()
        result = rob.evaluate(trades)
        self.assertGreaterEqual(result.robustness_score, 0)

    def test_robustness_fields(self):
        trades = [make_trade(random.uniform(-5, 15)) for _ in range(40)]
        rob = RobustnessEngine()
        result = rob.evaluate(trades)
        self.assertIsNotNone(result.overfitting_score)
        self.assertIsNotNone(result.edge_decay_rate)


# ============================================================
# UNIT TESTS — OPTIMIZER
# ============================================================

class TestOptimizer(unittest.TestCase):

    def test_grid_search(self):
        def objective(a=1, b=2):
            return BacktestResult(win_rate=0.5 + a * 0.01 + b * 0.005)
        opt = ParameterOptimizer(objective)
        params = [OptimizationParam("a", 1, 3, 1), OptimizationParam("b", 1, 3, 1)]
        result = opt.grid_search(params)
        self.assertGreater(result.total_runs, 0)
        self.assertIn("a", result.best_params)

    def test_random_search(self):
        def objective(x=1):
            return BacktestResult(win_rate=0.5 + x * 0.01)
        opt = ParameterOptimizer(objective)
        params = [OptimizationParam("x", 1, 10, 1)]
        result = opt.random_search(params, 10)
        self.assertGreater(result.total_runs, 0)


# ============================================================
# UNIT TESTS — COMPARATOR
# ============================================================

class TestComparator(unittest.TestCase):

    def test_compare_strategies(self):
        a = BacktestResult(win_rate=0.6, profit_factor=2.5, net_profit=1000,
                           max_drawdown_pct=0.05, sharpe_ratio=1.5, expectancy=20)
        b = BacktestResult(win_rate=0.5, profit_factor=1.5, net_profit=500,
                           max_drawdown_pct=0.10, sharpe_ratio=0.8, expectancy=5)
        result = compare_strategies({"A": a, "B": b})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].better_strategy, "A")

    def test_compare_versions(self):
        a = BacktestResult(win_rate=0.6, profit_factor=2.0, net_profit=800,
                           max_drawdown_pct=0.08, sharpe_ratio=1.2, expectancy=15)
        b = BacktestResult(win_rate=0.55, profit_factor=1.8, net_profit=600,
                           max_drawdown_pct=0.12, sharpe_ratio=1.0, expectancy=10)
        result = compare_versions("v1", "v2", a, b)
        self.assertEqual(result.strategy_a, "v1")
        self.assertEqual(result.strategy_b, "v2")
        self.assertIn("win_rate", result.metric_deltas)


# ============================================================
# UNIT TESTS — RECOMMENDATION ENGINE
# ============================================================

class TestRecommendation(unittest.TestCase):

    def test_recommendations_low_win_rate(self):
        result = BacktestResult(win_rate=0.3, profit_factor=3.0, max_drawdown_pct=0.05,
                                expectancy=10, sharpe_ratio=1.5)
        recs = generate_recommendations(result)
        win_rate_recs = [r for r in recs if r.category == "win_rate"]
        self.assertGreater(len(win_rate_recs), 0)

    def test_recommendations_high_drawdown(self):
        result = BacktestResult(win_rate=0.6, profit_factor=3.0, max_drawdown_pct=0.20,
                                expectancy=10, sharpe_ratio=1.5)
        recs = generate_recommendations(result)
        dd_recs = [r for r in recs if r.category == "drawdown"]
        self.assertGreater(len(dd_recs), 0)

    def test_recommendations_negative_expectancy(self):
        result = BacktestResult(win_rate=0.5, profit_factor=0.8, max_drawdown_pct=0.08,
                                expectancy=-5, sharpe_ratio=0.5)
        recs = generate_recommendations(result)
        exp_recs = [r for r in recs if r.category == "expectancy"]
        self.assertGreater(len(exp_recs), 0)

    def test_recommendations_all_good(self):
        result = BacktestResult(win_rate=0.65, profit_factor=3.5, max_drawdown_pct=0.05,
                                expectancy=25, sharpe_ratio=2.0)
        recs = generate_recommendations(result)
        critical = [r for r in recs if r.priority == "critical"]
        self.assertEqual(len(critical), 0)


# ============================================================
# UNIT TESTS — PORTFOLIO
# ============================================================

class TestPortfolio(unittest.TestCase):

    def test_portfolio_empty(self):
        ps = PortfolioSimulator(BacktestConfig())
        result = ps.portfolio_result()
        self.assertEqual(result.total_trades, 0)

    def test_portfolio_combines(self):
        ps = PortfolioSimulator(BacktestConfig())
        r1 = BacktestResult(total_trades=5, trades=[make_trade(10) for _ in range(5)],
                            config=BacktestConfig(initial_capital=10000))
        r2 = BacktestResult(total_trades=3, trades=[make_trade(15) for _ in range(3)],
                            config=BacktestConfig(initial_capital=10000))
        ps.add_result("BTC", r1)
        ps.add_result("ETH", r2)
        combined = ps.portfolio_result()
        self.assertEqual(combined.total_trades, 8)


# ============================================================
# INTEGRATION TESTS — BACKTEST ENGINE
# ============================================================

class TestBacktestEngine(unittest.TestCase):

    def test_engine_run_empty(self):
        engine = BacktestEngine()
        result = engine.run([])
        self.assertEqual(result.total_trades, 0)

    def test_engine_run_trades(self):
        engine = BacktestEngine(BacktestConfig(initial_capital=10000))
        trades = [make_trade(10), make_trade(-5), make_trade(15)]
        result = engine.run(trades)
        self.assertEqual(result.total_trades, 3)
        self.assertAlmostEqual(result.net_profit, 20, delta=1)
        self.assertGreater(result.final_capital, 10000)

    def test_engine_analyze(self):
        engine = BacktestEngine()
        trades = [make_trade(random.uniform(-10, 20)) for _ in range(30)]
        result = engine.run(trades)
        analysis = engine.analyze(result)
        self.assertIn("result", analysis)
        self.assertIn("walk_forward", analysis)
        self.assertIn("monte_carlo", analysis)
        self.assertIn("robustness", analysis)
        self.assertIn("recommendations", analysis)

    def test_engine_last_result(self):
        engine = BacktestEngine()
        self.assertIsNone(engine.last_result())
        trades = [make_trade(10)]
        engine.run(trades)
        self.assertIsNotNone(engine.last_result())

    def test_engine_risk_manager(self):
        engine = BacktestEngine()
        self.assertIsInstance(engine.risk_manager, RiskManager)

    def test_engine_position_manager(self):
        engine = BacktestEngine()
        self.assertIsInstance(engine.position_manager, PositionManager)


# ============================================================
# INTEGRATION TESTS — REPORT GENERATION
# ============================================================

class TestReport(unittest.TestCase):

    def test_report_basic(self):
        result = BacktestResult(
            total_trades=10, winning_trades=6, losing_trades=4,
            win_rate=0.6, profit_factor=2.5, expectancy=15,
            net_profit=500, gross_profit=800, gross_loss=300,
            max_drawdown_pct=0.05, avg_drawdown=0.02,
            sharpe_ratio=1.5, sortino_ratio=2.0, calmar_ratio=3.0,
            kelly_percentage=0.2, recovery_factor=5.0,
            ulcer_index=0.03, avg_r=1.5, total_r=15,
            final_capital=10500, avg_holding_bars=24,
            total_commission=10, total_funding=0, total_slippage=5,
        )
        report = generate_report(result)
        self.assertIn("BACKTEST INTELLIGENCE REPORT", report)
        self.assertIn("Win Rate", report)
        self.assertIn("Sharpe Ratio", report)

    def test_report_with_advanced(self):
        result = BacktestResult(total_trades=20, win_rate=0.6, profit_factor=2.0,
                                expectancy=10, net_profit=500, max_drawdown_pct=0.05,
                                sharpe_ratio=1.5, profit_by_setup={"bos": 200, "fvg": 100},
                                profit_by_hour={"8": 50, "14": 80})
        wf = WalkForwardResult(wfa_score=0.75, in_sample_score=0.6, out_sample_score=0.45,
                                parameter_stability=0.8)
        mc = MonteCarloResult(mean_return=100, median_return=80, std_return=50,
                               var_95=-30, var_99=-80, probability_positive=0.85,
                               probability_profit_factor_gt_1=0.9,
                               probability_max_dd_lt_10=0.8, confidence_score=0.7,
                               simulations=500)
        rob = RobustnessResult(robustness_score=0.7, overfitting_score=0.2,
                                underfitting_score=0.1, edge_decay_rate=0.1)
        recs = [AIRecommendation("test", "Test", "evidence", "impact", 0.8, "critical")]
        report = generate_report(result, wf, mc, rob, recs)
        self.assertIn("WALK FORWARD", report)
        self.assertIn("MONTE CARLO", report)
        self.assertIn("ROBUSTNESS", report)
        self.assertIn("CRITICAL RECOMMENDATIONS", report)


# ============================================================
# PERFORMANCE TEST
# ============================================================

class TestBacktestPerformance(unittest.TestCase):

    def test_engine_100_trades(self):
        engine = BacktestEngine()
        trades = [make_trade(random.uniform(-10, 20)) for _ in range(100)]
        start = time.time()
        engine.run(trades)
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.5, f"100 trades took {elapsed:.3f}s")


# ============================================================
# STRESS TEST
# ============================================================

class TestBacktestStress(unittest.TestCase):

    def test_1000_trades(self):
        engine = BacktestEngine()
        trades = [make_trade(random.uniform(-20, 30)) for _ in range(1000)]
        start = time.time()
        result = engine.run(trades)
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0, f"1000 trades took {elapsed:.2f}s")
        self.assertEqual(result.total_trades, 1000)


if __name__ == "__main__":
    unittest.main()
