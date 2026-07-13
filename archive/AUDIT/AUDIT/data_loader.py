import json
import logging
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ENGINE.market.market_types import Candle

log = logging.getLogger(__name__)

BINANCE_BASE = "https://api.binance.com"
DATA_DIR = Path(__file__).parent / "data" / "historical"
MAX_CANDLES_PER_REQUEST = 1000
REQUEST_DELAY = 0.2

TF_MINUTES: Dict[str, int] = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "4h": 240, "1d": 1440, "1w": 10080,
}

BINANCE_INTERVALS: Dict[str, str] = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w",
}

BACKTEST_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
BACKTEST_TIMEFRAMES = ["15m", "1h", "4h"]


class BinanceDataLoader:
    def __init__(self, cache_dir: Optional[Path] = None):
        self._cache_dir = cache_dir or DATA_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def download(self, pair: str, tf: str, start: datetime, end: Optional[datetime] = None) -> List[Candle]:
        pair_upper = pair.upper()
        interval = BINANCE_INTERVALS.get(tf)
        if not interval:
            log.error("Unsupported timeframe: %s", tf)
            return []

        cache_file = self._cache_dir / f"{pair_upper}_{tf}.json"
        if cache_file.exists():
            cached = self._load_cache(cache_file, start, end)
            if cached and cached[-1].timestamp >= start:
                log.info("Loaded %d cached candles for %s %s", len(cached), pair_upper, tf)
                return cached

        candles: List[Candle] = []
        end = end or datetime.now(timezone.utc)
        current_start = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        while current_start < end_ms:
            url = (
                f"{BINANCE_BASE}/api/v3/klines"
                f"?symbol={pair_upper}&interval={interval}"
                f"&startTime={current_start}&limit={MAX_CANDLES_PER_REQUEST}"
            )
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "QuantOS/2.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                log.error("Binance HTTP %d for %s %s: %s", e.code, pair_upper, tf, e.read().decode())
                break
            except Exception as e:
                log.error("Binance request failed for %s %s: %s", pair_upper, tf, e)
                break

            if not data:
                break

            for k in data:
                ts = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc)
                candles.append(Candle(
                    timestamp=ts,
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                ))

            log.info("Downloaded %d candles for %s %s (from %s)", len(data), pair_upper, tf,
                      candles[-1].timestamp.isoformat() if candles else "?")

            current_start = data[-1][0] + 1
            time.sleep(REQUEST_DELAY)

            if len(data) < MAX_CANDLES_PER_REQUEST:
                break

        if candles:
            self._save_cache(cache_file, candles)

        log.info("Total %d candles for %s %s (%s to %s)", len(candles), pair_upper, tf,
                  candles[0].timestamp.isoformat() if candles else "?",
                  candles[-1].timestamp.isoformat() if candles else "?")
        return candles

    def download_all(self, assets: Optional[List[str]] = None,
                     timeframes: Optional[List[str]] = None,
                     months: int = 24) -> Dict[str, Dict[str, List[Candle]]]:
        targets = assets or BACKTEST_ASSETS
        tfs = timeframes or BACKTEST_TIMEFRAMES
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=30 * months)

        data: Dict[str, Dict[str, List[Candle]]] = {}
        for pair in targets:
            data[pair] = {}
            for tf in tfs:
                log.info("Downloading %s %s from %s to %s", pair, tf, start.date(), end.date())
                data[pair][tf] = self.download(pair, tf, start, end)
                if not data[pair][tf]:
                    log.warning("No data for %s %s", pair, tf)

        return data

    def _load_cache(self, path: Path, start: datetime, end: datetime) -> List[Candle]:
        try:
            with open(path, "r") as f:
                raw = json.load(f)
            candles = []
            for r in raw:
                ts = datetime.fromisoformat(r["t"])
                if start <= ts <= end:
                    candles.append(Candle(
                        timestamp=ts,
                        open=r["o"], high=r["h"],
                        low=r["l"], close=r["c"],
                        volume=r["v"],
                    ))
            return candles
        except Exception as e:
            log.debug("Cache load failed: %s", e)
            return []

    def _save_cache(self, path: Path, candles: List[Candle]) -> None:
        try:
            raw = [
                {"t": c.timestamp.isoformat(), "o": c.open, "h": c.high,
                 "l": c.low, "c": c.close, "v": c.volume}
                for c in candles
            ]
            with open(path, "w") as f:
                json.dump(raw, f)
        except Exception as e:
            log.warning("Cache save failed: %s", e)

    @staticmethod
    def split_walk_forward(candles: List[Candle],
                           train_pct: float = 0.5,
                           val_pct: float = 0.25) -> Tuple[List[Candle], List[Candle], List[Candle]]:
        n = len(candles)
        train_end = int(n * train_pct)
        val_end = train_end + int(n * val_pct)
        return candles[:train_end], candles[train_end:val_end], candles[val_end:]

    @staticmethod
    def validate_integrity(candles: List[Candle]) -> List[str]:
        issues = []
        for i, c in enumerate(candles):
            if c.high < c.low:
                issues.append(f"Candle {i}: high {c.high} < low {c.low}")
            if c.open < 0 or c.high < 0 or c.low < 0 or c.close < 0:
                issues.append(f"Candle {i}: negative price")
            if c.volume < 0:
                issues.append(f"Candle {i}: negative volume")
            if i > 0 and c.timestamp <= candles[i - 1].timestamp:
                issues.append(f"Candle {i}: timestamp not increasing")
            if c.high < c.open or c.high < c.close:
                issues.append(f"Candle {i}: high < open or close")
            if c.low > c.open or c.low > c.close:
                issues.append(f"Candle {i}: low > open or close")
        return issues
