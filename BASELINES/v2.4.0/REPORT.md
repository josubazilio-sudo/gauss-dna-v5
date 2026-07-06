=========================================================
  BACKTEST INTELLIGENCE ENGINE — BASELINE v2.4.0
=========================================================
  Date: 2026-07-05 11:01:53
  Status: ? ALL TESTS PASSING

  Tests: 551 total (51 Backtest + 500 existing)
  Files: 16 in ENGINE/backtest/
  Coverage: types, config, trade_simulator, position_manager,
            risk_manager, statistics_engine, monte_carlo,
            walk_forward, robustness, strategy_runner, portfolio,
            optimizer, comparator, recommendation, report, engine

  Key Metrics:
    - Win Rate target: 60%
    - Profit Factor target: 2.5
    - Max Drawdown limit: 10%

  Auto-corrections applied:
    1. recommendation.py:65 — typo robutness_score ? robustness_score
    2. PositionManager tests — switched to make_open_trade() with
       proper TradeStatus.OPEN and all required dataclass fields
    3. Pyramiding test — corrected logic (3 levels = max 3,
       not 4)

=========================================================
