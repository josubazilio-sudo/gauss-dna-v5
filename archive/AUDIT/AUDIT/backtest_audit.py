import logging
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from ENGINE.market.market_types import (
    Candle, TechnicalIndicators, MarketContext, MarketRegime,
    TrendDirection,
)
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.scanner.scanner_types import SignalClassification
from .institutional_audit import InstitutionalAudit
from .data_loader import BinanceDataLoader

log = logging.getLogger(__name__)

BACKTEST_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
BACKTEST_TIMEFRAMES = ["15m", "1h", "4h"]
BACKTEST_MONTHS = 24
BASE_PRICES = {
    "BTCUSDT": 65000.0, "ETHUSDT": 3500.0, "SOLUSDT": 145.0,
    "BNBUSDT": 580.0, "XRPUSDT": 0.55,
}
VOLATILITIES = {
    "BTCUSDT": 0.015, "ETHUSDT": 0.018, "SOLUSDT": 0.025,
    "BNBUSDT": 0.020, "XRPUSDT": 0.030,
}


@dataclass
class TradeRecord:
    pair: str
    timeframe: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    entry_time: datetime
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    result: str = ""
    profit_loss_pct: float = 0.0
    mae_pct: float = 0.0
    mfe_pct: float = 0.0
    score: float = 0.0
    quality: float = 0.0
    classification: str = ""
    regime: str = ""
    rr: float = 0.0
    duration_h: float = 0.0
    setup: str = ""
    structural_score: float = 0.0
    confidence: float = 0.0
    rvol_value: float = 0.0
    adx: float = 0.0
    pattern_types: List[str] = field(default_factory=list)


@dataclass
class BacktestResult:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    avg_rr: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    avg_trade_duration_h: float = 0.0
    by_asset: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_timeframe: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_classification: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_regime: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_direction: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_setup: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    monthly_pnl: Dict[str, float] = field(default_factory=dict)
    weekly_pnl: Dict[str, float] = field(default_factory=dict)
    trades: List[TradeRecord] = field(default_factory=list)
    loss_causes: Dict[str, int] = field(default_factory=dict)
    win_causes: Dict[str, int] = field(default_factory=dict)
    pnl_distribution: List[float] = field(default_factory=list)
    feature_ranking: List[Dict[str, Any]] = field(default_factory=list)
    walk_forward_results: Dict[str, Any] = field(default_factory=dict)


def _make_market_context(pair: str, candles: List[Candle]) -> MarketContext:
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.volume for c in candles]
    avg_price = sum(closes) / len(closes) if closes else 0
    atr_val = _compute_atr(highs, lows, closes)

    ind = TechnicalIndicators(
        atr=atr_val,
        atr_percent=atr_val / avg_price if avg_price > 0 else 0.01,
        adx=25.0,
        rsi=50.0,
        rvol=1.0,
        volume=sum(volumes) / len(volumes) if volumes else 1000,
        avg_volume=sum(volumes) / len(volumes) if volumes else 1000,
        bb_width=0.05,
        ema_50=_ema(closes, 50),
        ema_200=_ema(closes, 200),
        ema_alignment=1.0,
    )

    return MarketContext(
        pair=pair,
        timestamp=datetime.now(timezone.utc),
        price=avg_price,
        indicators=ind,
        trend=TrendDirection.NEUTRAL,
        trend_strength=0.5,
        regime=MarketRegime.RANGING,
        regime_confidence=0.5,
        market_score=0.5,
        trend_score=0.5,
        momentum_score=0.5,
        liquidity_score=0.8,
        risk_score=0.5,
        confidence_score=0.5,
        institutional_score=0.5,
    )


def _compute_atr(highs: List[float], lows: List[float], closes: List[float],
                 period: int = 14) -> float:
    if len(closes) < period + 1:
        return (max(highs) - min(lows)) / len(highs) if highs else 0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return sum(trs[-period:]) / period if trs else 0


def _ema(values: List[float], period: int) -> float:
    if len(values) < period:
        return sum(values) / len(values) if values else 0
    k = 2 / (period + 1)
    ema_val = sum(values[:period]) / period
    for v in values[period:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val


class BacktestAudit:
    def __init__(self, use_real_data: bool = True):
        self._scanner = ScannerEngine()
        self._audit = InstitutionalAudit()
        self._use_real_data = use_real_data
        self._data_loader = BinanceDataLoader() if use_real_data else None

    def run(self, assets: Optional[List[str]] = None,
            timeframes: Optional[List[str]] = None,
            months: int = BACKTEST_MONTHS) -> BacktestResult:
        targets = assets or BACKTEST_ASSETS
        tfs = timeframes or BACKTEST_TIMEFRAMES
        result = BacktestResult()

        candle_cache: Dict[str, Dict[str, List[Candle]]] = {}
        data_source = "reais (Binance)" if self._use_real_data else "sintéticos"

        if self._use_real_data and self._data_loader:
            log.info("Downloading real data from Binance (%d months)...", months)
            candle_cache = self._data_loader.download_all(targets, tfs, months)
            for pair in targets:
                for tf in tfs:
                    if candle_cache.get(pair, {}).get(tf):
                        issues = BinanceDataLoader.validate_integrity(candle_cache[pair][tf])
                        if issues:
                            log.warning("Data integrity issues for %s %s: %d", pair, tf, len(issues))
                            for iss in issues[:5]:
                                log.warning("  %s", iss)
        else:
            for pair in targets:
                candle_cache[pair] = {}
                base_price = BASE_PRICES.get(pair, 100.0)
                vol = VOLATILITIES.get(pair, 0.02)
                for tf in tfs:
                    candle_cache[pair][tf] = self._generate_historical(
                        base_price, vol, months, tf
                    )

        equity = 10000.0
        peak = 10000.0
        equity_curve = [equity]
        closed_trades: List[TradeRecord] = []

        for pair in targets:
            for tf in tfs:
                all_candles = candle_cache[pair][tf]
                if len(all_candles) < 200:
                    log.warning("Skipping %s %s: only %d candles", pair, tf, len(all_candles))
                    continue

                step = max(1, len(all_candles) // 100)
                for scan_i in range(0, len(all_candles) - 200, step):
                    window_end = scan_i + 200
                    window = all_candles[scan_i:window_end]
                    if len(window) < 100:
                        continue

                    try:
                        ctx = _make_market_context(pair, window)
                        candles_dict = {tf: window}
                        report = self._scanner.scan(pair, candles_dict, ctx)
                    except Exception as e:
                        log.debug("Backtest scan error %s %s: %s", pair, tf, e)
                        continue

                    for sig in report.signals:
                        fwd_start = window_end
                        fwd_end = min(fwd_start + 96, len(all_candles))
                        forward_window = all_candles[fwd_start:fwd_end]
                        if len(forward_window) < 5:
                            continue

                        pattern_types = [p.type.value if hasattr(p.type, 'value') else str(p.type) for p in sig.patterns]

                        trade = TradeRecord(
                            pair=pair, timeframe=tf,
                            direction=sig.direction.value,
                            entry_price=sig.entry_price,
                            stop_loss=sig.stop_loss,
                            take_profit_1=sig.take_profit_1,
                            take_profit_2=sig.take_profit_2,
                            entry_time=sig.timestamp,
                            score=sig.scores.quality_score,
                            quality=sig.quality,
                            classification=sig.classification.value,
                            regime=sig.regime,
                            rr=sig.risk_reward,
                            setup=sig.setup,
                            structural_score=sig.scores.structural_score,
                            confidence=sig.scores.confidence_score,
                            rvol_value=sig.rvol if hasattr(sig, 'rvol') else 0,
                            adx=sig.adx if hasattr(sig, 'adx') else 0,
                            pattern_types=pattern_types,
                        )

                        sim_result, mae, mfe = self._simulate_trade(trade, forward_window)
                        trade.result = sim_result
                        trade.exit_time = datetime.now(timezone.utc)
                        trade.profit_loss_pct = self._calc_pnl(trade)
                        trade.mae_pct = mae
                        trade.mfe_pct = mfe
                        trade.duration_h = 96 * self._tf_hours(tf)
                        closed_trades.append(trade)

                        pnl_pct = trade.profit_loss_pct
                        equity += equity * pnl_pct * 0.02
                        if equity > peak:
                            peak = equity
                        equity_curve.append(equity)

        result.total_trades = len(closed_trades)
        result.trades = closed_trades
        result.equity_curve = equity_curve
        result.pnl_distribution = [t.profit_loss_pct for t in closed_trades]

        self._compute_metrics(result, equity_curve, closed_trades)
        self._compute_by_asset(result, closed_trades)
        self._compute_by_timeframe(result, closed_trades)
        self._compute_by_classification(result, closed_trades)
        self._compute_by_regime(result, closed_trades)
        self._compute_by_direction(result, closed_trades)
        self._compute_by_setup(result, closed_trades)
        self._compute_curves(result, equity_curve)
        self._compute_loss_win_causes(result, closed_trades)
        self._compute_feature_ranking(result, closed_trades)

        split = max(1, len(closed_trades) // 2)
        in_sample = closed_trades[:split]
        out_sample = closed_trades[split:]
        if in_sample and out_sample:
            result.walk_forward_results = self._run_walk_forward_analysis(
                in_sample, out_sample
            )

        log.info(
            "BacktestAudit: %d trades, WR=%.1f%%, PF=%.2f, DD=%.1f%%, Sharpe=%.2f (%s)",
            result.total_trades, result.win_rate * 100, result.profit_factor,
            result.max_drawdown * 100, result.sharpe_ratio, data_source,
        )
        return result

    def _generate_historical(self, base_price: float, vol: float,
                              months: int, tf: str) -> List[Candle]:
        candles_per_day = int(24 * 60 / self._tf_minutes(tf))
        total = candles_per_day * 30 * months
        candles = []
        price = base_price
        trend = 0.0
        base_ts = datetime.now(timezone.utc) - timedelta(days=30 * months)

        for i in range(total):
            trend += random.gauss(0, vol * 0.1)
            trend = max(min(trend, vol * 5), -vol * 5)
            phase = math.sin(i * 0.02) * vol * 0.5
            r = random.gauss(trend + phase, vol * 0.6)
            price *= 1.0 + r
            price = max(base_price * 0.3, min(base_price * 3.0, price))
            o = price * (1 + random.uniform(-vol * 0.3, vol * 0.3))
            h = max(o, price) * (1 + random.uniform(0, vol * 0.3))
            lv = min(o, price) * (1 - random.uniform(0, vol * 0.3))
            v = max(100, random.gauss(1000, 300) * (1 + abs(r) * 10))
            ts = base_ts + timedelta(minutes=i * self._tf_minutes(tf))
            candles.append(Candle(open=round(o, 2), high=round(h, 2),
                                  low=round(lv, 2), close=round(price, 2),
                                  volume=round(v, 2), timestamp=ts))
        return candles

    def _simulate_trade(self, trade: TradeRecord,
                         forward_window: List[Candle]) -> Tuple[str, float, float]:
        direction = trade.direction
        entry = trade.entry_price
        sl = trade.stop_loss
        tp1 = trade.take_profit_1
        tp2 = trade.take_profit_2
        mae = 0.0
        mfe = 0.0

        for candle in forward_window:
            high, low = candle.high, candle.low
            if direction == "long":
                mae = max(mae, (entry - low) / entry)
                mfe = max(mfe, (high - entry) / entry)
                if low <= sl:
                    return "loss", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
                if high >= tp2:
                    return "win", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
                if high >= tp1:
                    pass
            else:
                mae = max(mae, (high - entry) / entry)
                mfe = max(mfe, (entry - low) / entry)
                if high >= sl:
                    return "loss", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
                if low <= tp2:
                    return "win", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
                if low <= tp1:
                    pass
        return "loss", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)

    def _calc_pnl(self, trade: TradeRecord) -> float:
        if trade.result == "win":
            if trade.direction == "long":
                return (trade.take_profit_2 - trade.entry_price) / trade.entry_price
            else:
                return (trade.entry_price - trade.take_profit_2) / trade.entry_price
        elif trade.result == "loss":
            if trade.direction == "long":
                return (trade.stop_loss - trade.entry_price) / trade.entry_price
            else:
                return (trade.entry_price - trade.stop_loss) / trade.entry_price
        return 0.0

    def _compute_metrics(self, result: BacktestResult, equity_curve: List[float],
                          trades: List[TradeRecord]) -> None:
        if not trades:
            return
        winners = [t for t in trades if t.result == "win"]
        losers = [t for t in trades if t.result == "loss"]
        result.winning_trades = len(winners)
        result.losing_trades = len(losers)
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0.0

        gross_profit = sum(abs(self._calc_pnl(t)) * 10000 * 0.02 for t in winners)
        gross_loss = sum(abs(self._calc_pnl(t)) * 10000 * 0.02 for t in losers)
        result.gross_profit = gross_profit
        result.gross_loss = gross_loss
        result.net_pnl = gross_profit - gross_loss
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0

        avg_win = gross_profit / len(winners) if winners else 0
        avg_loss = gross_loss / len(losers) if losers else 0
        result.expectancy = (result.win_rate * avg_win - (1 - result.win_rate) * avg_loss) / 10000 if avg_loss > 0 else 0
        result.avg_rr = sum(t.rr for t in trades) / len(trades)
        result.avg_trade_duration_h = sum(t.duration_h for t in trades) / len(trades)

        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i - 1] > 0:
                returns.append((equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1])
        if len(returns) > 1:
            avg_ret = sum(returns) / len(returns)
            std_ret = (sum((r - avg_ret) ** 2 for r in returns) / len(returns)) ** 0.5
            result.sharpe_ratio = avg_ret / std_ret * (252 ** 0.5) if std_ret > 0 else 0
            neg_returns = [r for r in returns if r < 0]
            if neg_returns:
                neg_std = (sum(r ** 2 for r in neg_returns) / len(neg_returns)) ** 0.5
                result.sortino_ratio = avg_ret / neg_std * (252 ** 0.5) if neg_std > 0 else 0

        peak = max(equity_curve) if equity_curve else 10000
        trough = peak
        max_dd = 0.0
        for e in equity_curve:
            if e > peak:
                peak = e
                trough = peak
            if e < trough:
                trough = e
                dd = (peak - trough) / peak
                if dd > max_dd:
                    max_dd = dd
        result.max_drawdown = max_dd

        if result.max_drawdown > 0 and result.sharpe_ratio != 0:
            result.calmar_ratio = result.sharpe_ratio / result.max_drawdown if result.max_drawdown > 0 else 0

    def _compute_by_asset(self, result: BacktestResult, trades: List[TradeRecord]) -> None:
        groups = defaultdict(list)
        for t in trades:
            groups[t.pair].append(t)
        for asset, ts in groups.items():
            wins = sum(1 for t in ts if t.result == "win")
            total = len(ts)
            gross_p = sum(self._calc_pnl(t) for t in ts if t.result == "win")
            gross_l = sum(abs(self._calc_pnl(t)) for t in ts if t.result == "loss")
            result.by_asset[asset] = {
                "trades": total, "wins": wins,
                "win_rate": wins / total if total > 0 else 0,
                "avg_rr": sum(t.rr for t in ts) / total if total > 0 else 0,
                "profit_factor": gross_p / gross_l if gross_l > 0 else 999.0,
                "net_pnl": gross_p - gross_l,
            }

    def _compute_by_timeframe(self, result: BacktestResult, trades: List[TradeRecord]) -> None:
        groups = defaultdict(list)
        for t in trades:
            groups[t.timeframe].append(t)
        for tf, ts in groups.items():
            wins = sum(1 for t in ts if t.result == "win")
            total = len(ts)
            gross_p = sum(self._calc_pnl(t) for t in ts if t.result == "win")
            gross_l = sum(abs(self._calc_pnl(t)) for t in ts if t.result == "loss")
            result.by_timeframe[tf] = {
                "trades": total, "wins": wins,
                "win_rate": wins / total if total > 0 else 0,
                "profit_factor": gross_p / gross_l if gross_l > 0 else 999.0,
            }

    def _compute_by_classification(self, result: BacktestResult, trades: List[TradeRecord]) -> None:
        groups = defaultdict(list)
        for t in trades:
            groups[t.classification].append(t)
        for cl, ts in groups.items():
            wins = sum(1 for t in ts if t.result == "win")
            total = len(ts)
            gross_p = sum(self._calc_pnl(t) for t in ts if t.result == "win")
            gross_l = sum(abs(self._calc_pnl(t)) for t in ts if t.result == "loss")
            result.by_classification[cl] = {
                "trades": total, "wins": wins,
                "win_rate": wins / total if total > 0 else 0,
                "profit_factor": gross_p / gross_l if gross_l > 0 else 999.0,
            }

    def _compute_by_regime(self, result: BacktestResult, trades: List[TradeRecord]) -> None:
        groups = defaultdict(list)
        for t in trades:
            groups[t.regime].append(t)
        for rg, ts in groups.items():
            wins = sum(1 for t in ts if t.result == "win")
            total = len(ts)
            gross_p = sum(self._calc_pnl(t) for t in ts if t.result == "win")
            gross_l = sum(abs(self._calc_pnl(t)) for t in ts if t.result == "loss")
            result.by_regime[rg] = {
                "trades": total, "wins": wins,
                "win_rate": wins / total if total > 0 else 0,
                "profit_factor": gross_p / gross_l if gross_l > 0 else 999.0,
            }

    def _compute_by_direction(self, result: BacktestResult, trades: List[TradeRecord]) -> None:
        groups = defaultdict(list)
        for t in trades:
            groups[t.direction].append(t)
        for dr, ts in groups.items():
            wins = sum(1 for t in ts if t.result == "win")
            total = len(ts)
            result.by_direction[dr] = {
                "trades": total, "wins": wins,
                "win_rate": wins / total if total > 0 else 0,
                "avg_rr": sum(t.rr for t in ts) / total if total > 0 else 0,
            }

    def _compute_by_setup(self, result: BacktestResult, trades: List[TradeRecord]) -> None:
        groups = defaultdict(list)
        for t in trades:
            groups[t.setup].append(t)
        for st, ts in groups.items():
            wins = sum(1 for t in ts if t.result == "win")
            total = len(ts)
            result.by_setup[st] = {
                "trades": total, "wins": wins,
                "win_rate": wins / total if total > 0 else 0,
            }

    def _compute_curves(self, result: BacktestResult, equity_curve: List[float]) -> None:
        if not equity_curve:
            return
        result.drawdown_curve = []
        peak = equity_curve[0]
        for e in equity_curve:
            if e > peak:
                peak = e
            dd = (peak - e) / peak if peak > 0 else 0
            result.drawdown_curve.append(dd)

        month_map: Dict[str, float] = {}
        week_map: Dict[str, float] = {}
        for t in result.trades:
            if not t.exit_time:
                continue
            month_key = t.exit_time.strftime("%Y-%m")
            week_key = t.exit_time.strftime("%Y-W%W")
            pnl = t.profit_loss_pct * 10000 * 0.02
            month_map[month_key] = month_map.get(month_key, 0) + pnl
            week_map[week_key] = week_map.get(week_key, 0) + pnl
        result.monthly_pnl = dict(sorted(month_map.items()))
        result.weekly_pnl = dict(sorted(week_map.items()))

    def _compute_loss_win_causes(self, result: BacktestResult, trades: List[TradeRecord]) -> None:
        for t in trades:
            for prefix, key in [("regime", t.regime), ("class", t.classification)]:
                k = f"{prefix}={key}"
                if t.result == "loss":
                    result.loss_causes[k] = result.loss_causes.get(k, 0) + 1
                elif t.result == "win":
                    result.win_causes[k] = result.win_causes.get(k, 0) + 1

    def _compute_feature_ranking(self, result: BacktestResult, trades: List[TradeRecord]) -> None:
        ranking = []

        def wr_for_condition(ts: List[TradeRecord], pred) -> Tuple[int, int, float]:
            matched = [t for t in ts if pred(t)]
            wins = sum(1 for t in matched if t.result == "win")
            total = len(matched)
            wr = wins / total if total > 0 else 0
            return wins, total, wr

        features = [
            ("Direção LONG", lambda t: t.direction == "long"),
            ("Direção SHORT", lambda t: t.direction == "short"),
        ]
        for name, pred in features:
            wins, total, wr = wr_for_condition(trades, pred)
            ranking.append({"feature": name, "wins": wins, "total": total, "win_rate": wr})

        regime_types = set(t.regime for t in trades if t.regime)
        for rg in sorted(regime_types):
            wins, total, wr = wr_for_condition(trades, lambda t, r=rg: t.regime == r)
            ranking.append({"feature": f"Regime: {rg}", "wins": wins, "total": total, "win_rate": wr})

        for cl in ["ouro_supremo", "ouro", "prata", "bronze", "reprovado"]:
            wins, total, wr = wr_for_condition(trades, lambda t, c=cl: t.classification == c)
            if total > 0:
                ranking.append({"feature": f"Class: {cl}", "wins": wins, "total": total, "win_rate": wr})

        for tf_name in sorted(set(t.timeframe for t in trades)):
            wins, total, wr = wr_for_condition(trades, lambda t, tf=tf_name: t.timeframe == tf)
            ranking.append({"feature": f"TF: {tf_name}", "wins": wins, "total": total, "win_rate": wr})

        ranking.sort(key=lambda x: x["win_rate"], reverse=True)
        result.feature_ranking = ranking

    def _run_walk_forward(self, trades: List[TradeRecord]) -> List[TradeRecord]:
        if len(trades) < 20:
            return []
        split = int(len(trades) * 0.5)
        return trades[split:]

    def _run_walk_forward_analysis(self, in_sample: List[TradeRecord],
                                    out_sample: List[TradeRecord]) -> Dict[str, Any]:
        def compute_stats(ts):
            if not ts:
                return {}
            wins = sum(1 for t in ts if t.result == "win")
            total = len(ts)
            wr = wins / total if total > 0 else 0
            gross_p = sum(abs(t.profit_loss_pct) for t in ts if t.result == "win")
            gross_l = sum(abs(t.profit_loss_pct) for t in ts if t.result == "loss")
            pf = gross_p / gross_l if gross_l > 0 else 999.0
            avg_rr = sum(t.rr for t in ts) / total if total > 0 else 0
            return {"trades": total, "win_rate": round(wr, 4), "profit_factor": round(pf, 2), "avg_rr": round(avg_rr, 2)}

        in_stats = compute_stats(in_sample)
        out_stats = compute_stats(out_sample)

        robust = 0.0
        if in_stats and out_stats:
            wr_ratio = out_stats.get("win_rate", 0) / in_stats.get("win_rate", 1) if in_stats.get("win_rate", 0) > 0 else 0
            pf_ratio = out_stats.get("profit_factor", 0) / in_stats.get("profit_factor", 1) if in_stats.get("profit_factor", 0) > 0 else 0
            robust = round((wr_ratio + pf_ratio) / 2, 4)

        return {
            "in_sample": in_stats,
            "out_sample": out_stats,
            "robustness_score": robust,
            "decay": round(1 - robust, 4) if robust > 0 else 1.0,
        }

    @staticmethod
    def _tf_minutes(tf: str) -> int:
        return {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}.get(tf, 60)

    @staticmethod
    def _tf_hours(tf: str) -> float:
        return {"5m": 5 / 60, "15m": 0.25, "1h": 1.0, "4h": 4.0, "1d": 24.0}.get(tf, 1.0)
