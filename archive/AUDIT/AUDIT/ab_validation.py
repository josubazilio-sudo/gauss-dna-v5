import logging
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from ENGINE.market.market_types import Candle, TechnicalIndicators, MarketContext, MarketRegime, TrendDirection
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.scanner.scanner_types import Signal
from ENGINE.decision.decision_engine import DecisionEngine
from ENGINE.decision_brain.decision_brain import DecisionBrain
from ENGINE.decision_brain.decision_brain_types import DecisionState
from AUDIT.data_loader import BinanceDataLoader

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
class ABTradeRecord:
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
    engine_version: str = ""
    decision_state: str = ""
    probabilidade: float = 0.0
    conviccao: float = 0.0
    risco: float = 0.0
    tese_score: float = 0.0
    contra_score: float = 0.0
    justificativa: str = ""
    signal_id: str = ""


@dataclass
class ABResult:
    engine_version: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    avg_rr: float = 0.0
    net_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    avg_trade_duration_h: float = 0.0
    trades: List[ABTradeRecord] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    by_setup: Dict = field(default_factory=dict)
    by_regime: Dict = field(default_factory=dict)
    by_timeframe: Dict = field(default_factory=dict)
    by_asset: Dict = field(default_factory=dict)
    by_classification: Dict = field(default_factory=dict)


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


def _compute_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return (max(highs) - min(lows)) / len(highs) if highs else 0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    return sum(trs[-period:]) / period if trs else 0


def _ema(values, period):
    if len(values) < period:
        return sum(values) / len(values) if values else 0
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def _tf_minutes(tf: str) -> int:
    return {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}.get(tf, 60)


def _tf_hours(tf: str) -> float:
    return {"5m": 5/60, "15m": 0.25, "1h": 1.0, "4h": 4.0, "1d": 24.0}.get(tf, 1.0)


def _simulate_trade(trade: ABTradeRecord, forward_window: List[Candle]) -> Tuple[str, float, float]:
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
            if low <= sl: return "loss", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
            if high >= tp2: return "win", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
        else:
            mae = max(mae, (high - entry) / entry)
            mfe = max(mfe, (entry - low) / entry)
            if high >= sl: return "loss", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
            if low <= tp2: return "win", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)
    return "loss", round(min(mae, 0.5), 4), round(min(mfe, 0.5), 4)


def _calc_pnl(trade: ABTradeRecord) -> float:
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


class ABValidation:
    def __init__(self, use_real_data: bool = True):
        self._scanner = ScannerEngine()
        self._v7 = DecisionEngine()
        self._v11 = DecisionBrain()
        self._use_real_data = use_real_data
        self._data_loader = BinanceDataLoader() if use_real_data else None

    def run(
        self,
        assets: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        months: int = BACKTEST_MONTHS,
    ) -> Tuple[ABResult, ABResult, Dict[str, Any]]:
        targets = assets or BACKTEST_ASSETS
        tfs = timeframes or BACKTEST_TIMEFRAMES
        result_v7 = ABResult(engine_version="V7")
        result_v11 = ABResult(engine_version="V11")

        candle_cache = self._load_data(targets, tfs, months)
        equity_v7 = 10000.0
        equity_v11 = 10000.0
        peak_v7 = 10000.0
        peak_v11 = 10000.0
        trades_v7: List[ABTradeRecord] = []
        trades_v11: List[ABTradeRecord] = []
        equity_curve_v7 = [equity_v7]
        equity_curve_v11 = [equity_v11]

        for pair in targets:
            for tf in tfs:
                all_candles = candle_cache.get(pair, {}).get(tf, [])
                if len(all_candles) < 200:
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
                        log.debug("Scan error %s %s: %s", pair, tf, e)
                        continue

                    for sig in report.signals:
                        fwd_start = window_end
                        fwd_end = min(fwd_start + 96, len(all_candles))
                        forward_window = all_candles[fwd_start:fwd_end]
                        if len(forward_window) < 5:
                            continue

                        v7_trade = self._process_v7(sig, forward_window, pair, tf)
                        if v7_trade:
                            trades_v7.append(v7_trade)
                            pnl = v7_trade.profit_loss_pct
                            equity_v7 += equity_v7 * pnl * 0.02
                            if equity_v7 > peak_v7: peak_v7 = equity_v7
                            equity_curve_v7.append(equity_v7)

                        v11_trade = self._process_v11(sig, forward_window, pair, tf)
                        if v11_trade:
                            trades_v11.append(v11_trade)
                            pnl = v11_trade.profit_loss_pct
                            equity_v11 += equity_v11 * pnl * 0.02
                            if equity_v11 > peak_v11: peak_v11 = equity_v11
                            equity_curve_v11.append(equity_v11)

        self._fill_result(result_v7, trades_v7, equity_curve_v7)
        self._fill_result(result_v11, trades_v11, equity_curve_v11)
        comparison = self._compare(result_v7, result_v11)

        return result_v7, result_v11, comparison

    def _load_data(self, targets, tfs, months):
        if self._use_real_data and self._data_loader:
            log.info("Downloading %d months of real data from Binance...", months)
            return self._data_loader.download_all(targets, tfs, months)
        candle_cache = {}
        for pair in targets:
            candle_cache[pair] = {}
            base = BASE_PRICES.get(pair, 100.0)
            vol = VOLATILITIES.get(pair, 0.02)
            for tf in tfs:
                candle_cache[pair][tf] = self._generate_historical(base, vol, months, tf)
        log.info("Generated synthetic data: %d pairs x %d timeframes", len(targets), len(tfs))
        return candle_cache

    def _generate_historical(self, base_price, vol, months, tf):
        candles_per_day = int(24 * 60 / _tf_minutes(tf))
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
            ts = base_ts + timedelta(minutes=i * _tf_minutes(tf))
            candles.append(Candle(open=round(o, 2), high=round(h, 2), low=round(lv, 2), close=round(price, 2), volume=round(v, 2), timestamp=ts))
        return candles

    def _process_v7(self, sig: Signal, forward_window: List[Candle], pair: str, tf: str) -> Optional[ABTradeRecord]:
        try:
            highs = [c.high for c in forward_window]
            lows = [c.low for c in forward_window]
            closes = [c.close for c in forward_window]
            entry_details = sig.entry_details if hasattr(sig, 'entry_details') else None

            sd = self._v7.evaluate_signal(
                sig,
                entry_details=entry_details,
                highs=highs, lows=lows, closes=closes,
            )
            if not sd.approved:
                return None
            trade = ABTradeRecord(
                pair=pair, timeframe=tf,
                direction=sd.direction,
                entry_price=sd.entry_price,
                stop_loss=sd.stop_loss,
                take_profit_1=sd.take_profit_1,
                take_profit_2=sd.take_profit_2,
                entry_time=sig.timestamp,
                score=sd.entry_score,
                quality=sd.quality,
                classification=sig.classification.value if sig.classification else "",
                regime=sig.regime,
                rr=sd.risk_reward,
                setup=sig.setup,
                engine_version="V7",
                signal_id=sd.signal_id or sd.trace_id,
            )
            sim_result, mae, mfe = _simulate_trade(trade, forward_window)
            trade.result = sim_result
            trade.profit_loss_pct = _calc_pnl(trade)
            trade.mae_pct = mae
            trade.mfe_pct = mfe
            trade.duration_h = 96.0 * _tf_hours(tf)
            return trade
        except Exception as e:
            log.debug("V7 error %s %s: %s", pair, tf, e)
            return None

    def _process_v11(self, sig: Signal, forward_window: List[Candle], pair: str, tf: str) -> Optional[ABTradeRecord]:
        try:
            ctx = _make_market_context(pair, forward_window)
            ind = ctx.indicators
            closes = [c.close for c in forward_window]

            brain_rec = self._v11.evaluate(
                signal=sig,
                candles=forward_window,
                rsi=ind.rsi,
                adx=ind.adx,
                atr_percent=ind.atr_percent,
                rvol=ind.rvol,
                vwap_distance=abs(sig.structure.vwap_distance) if sig.structure else 0.0,
            )

            if brain_rec.estado != DecisionState.EXECUTAR:
                return None

            trade = ABTradeRecord(
                pair=pair, timeframe=tf,
                direction=sig.direction.value if hasattr(sig.direction, 'value') else str(sig.direction),
                entry_price=sig.entry_price,
                stop_loss=sig.stop_loss,
                take_profit_1=sig.take_profit_1,
                take_profit_2=sig.take_profit_2,
                entry_time=sig.timestamp,
                score=sig.scores.quality_score if sig.scores else 0.0,
                quality=sig.quality,
                classification=sig.classification.value if sig.classification else "",
                regime=sig.regime,
                rr=sig.risk_reward,
                setup=sig.setup,
                engine_version="V11",
                decision_state=brain_rec.estado.value,
                probabilidade=brain_rec.judgment.probabilidade if brain_rec.judgment else 0,
                conviccao=brain_rec.judgment.conviccao if brain_rec.judgment else 0,
                risco=brain_rec.judgment.risco if brain_rec.judgment else 0,
                tese_score=brain_rec.tese.score_total,
                contra_score=brain_rec.contra_tese.score_contra,
                justificativa=brain_rec.justificativa_final,
                signal_id=sig.signal_id or "",
            )
            sim_result, mae, mfe = _simulate_trade(trade, forward_window)
            trade.result = sim_result
            trade.profit_loss_pct = _calc_pnl(trade)
            trade.mae_pct = mae
            trade.mfe_pct = mfe
            trade.duration_h = 96.0 * _tf_hours(tf)
            return trade
        except Exception as e:
            log.debug("V11 error %s %s: %s", pair, tf, e)
            return None

    def _fill_result(self, result: ABResult, trades: List[ABTradeRecord], equity_curve: List[float]):
        if not trades:
            return
        result.total_trades = len(trades)
        result.trades = trades
        result.equity_curve = equity_curve

        winners = [t for t in trades if t.result == "win"]
        losers = [t for t in trades if t.result == "loss"]
        result.winning_trades = len(winners)
        result.losing_trades = len(losers)
        result.win_rate = len(winners) / len(trades) if trades else 0

        gross_profit = sum(abs(t.profit_loss_pct) * 10000 * 0.02 for t in winners)
        gross_loss = sum(abs(t.profit_loss_pct) * 10000 * 0.02 for t in losers)
        result.gross_profit = gross_profit
        result.gross_loss = gross_loss
        result.net_pnl = gross_profit - gross_loss
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0
        result.avg_rr = sum(t.rr for t in trades) / len(trades)
        result.avg_trade_duration_h = sum(t.duration_h for t in trades) / len(trades)

        avg_win = gross_profit / len(winners) if winners else 0
        avg_loss = gross_loss / len(losers) if losers else 0
        result.expectancy = (result.win_rate * avg_win - (1 - result.win_rate) * avg_loss) / 10000 if avg_loss > 0 else 0

        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i-1] > 0:
                returns.append((equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1])
        if len(returns) > 1:
            avg_ret = sum(returns) / len(returns)
            std_ret = (sum((r - avg_ret)**2 for r in returns) / len(returns)) ** 0.5
            result.sharpe_ratio = avg_ret / std_ret * (252 ** 0.5) if std_ret > 0 else 0
            neg = [r for r in returns if r < 0]
            if neg:
                neg_std = (sum(r**2 for r in neg) / len(neg)) ** 0.5
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
                max_dd = max(max_dd, dd)
        result.max_drawdown = max_dd
        if result.max_drawdown > 0 and result.sharpe_ratio != 0:
            result.calmar_ratio = result.sharpe_ratio / result.max_drawdown if result.max_drawdown > 0 else 0

        self._compute_by_dimension(result, trades, "setup", lambda t: t.setup)
        self._compute_by_dimension(result, trades, "regime", lambda t: t.regime)
        self._compute_by_dimension(result, trades, "timeframe", lambda t: t.timeframe)
        self._compute_by_dimension(result, trades, "asset", lambda t: t.pair)
        self._compute_by_dimension(result, trades, "classification", lambda t: t.classification)

    def _compute_by_dimension(self, result: ABResult, trades, dim: str, key_fn):
        groups = defaultdict(list)
        for t in trades:
            groups[key_fn(t)].append(t)
        target = getattr(result, f"by_{dim}")
        for k, ts in groups.items():
            wins = sum(1 for t in ts if t.result == "win")
            total = len(ts)
            target[k] = {
                "trades": total, "wins": wins,
                "win_rate": wins / total if total > 0 else 0,
            }

    def _compare(self, a: ABResult, b: ABResult) -> Dict[str, Any]:
        comparison = {}
        metrics = ["win_rate", "profit_factor", "expectancy", "max_drawdown",
                   "sharpe_ratio", "sortino_ratio", "avg_rr", "net_pnl",
                   "total_trades", "winning_trades", "avg_trade_duration_h"]
        for m in metrics:
            av = getattr(a, m, 0)
            bv = getattr(b, m, 0)
            v11_better = None
            if m == "max_drawdown":
                v11_better = b.max_drawdown <= a.max_drawdown
            elif m in ("net_pnl", "winning_trades"):
                v11_better = bv >= av
            else:
                v11_better = bv >= av
            comparison[m] = {
                "V7": av, "V11": bv,
                "diff": round(bv - av, 4),
                "diff_pct": round((bv - av) / abs(av) * 100, 2) if av and av != 0 else None,
                "V11_better": v11_better,
            }
        return comparison


