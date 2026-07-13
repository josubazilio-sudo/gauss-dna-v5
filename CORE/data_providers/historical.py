import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ENGINE.market.market_types import Candle
from .base import IDataProvider, TIMEFRAMES_MINUTES

log = logging.getLogger(__name__)


class HistoricalDataProvider(IDataProvider):
    name = "HistoricalDataProvider"

    def __init__(self, data_dir: Optional[str] = None):
        self._data_dir = Path(data_dir or "CONFIG/historical_data")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._memory: Dict[str, List[Candle]] = {}

    def get_symbols(self) -> List[str]:
        symbols: set = set()
        if not self._data_dir.exists():
            return []
        for f in self._data_dir.iterdir():
            if f.is_file() and f.stem.count("_") == 1:
                symbol = f.stem.split("_")[0]
                symbols.add(symbol.upper())
        result = sorted(symbols)
        log.info("HistoricalDataProvider: discovered %d symbols from %s", len(result), self._data_dir)
        return result

    def get_candles(
        self, symbol: str, timeframe: str, count: Optional[int] = None
    ) -> List[Candle]:
        cache_key = f"{symbol}:{timeframe}"
        if cache_key in self._memory:
            candles = self._memory[cache_key]
            if count and len(candles) > count:
                return candles[-count:]
            return candles

        candles = self._load_from_disk(symbol, timeframe)
        if not candles:
            log.warning("HistoricalDataProvider: no data for %s %s", symbol, timeframe)
            return []

        self._memory[cache_key] = candles
        if count and len(candles) > count:
            return candles[-count:]
        return candles

    def _load_from_disk(self, symbol: str, timeframe: str) -> List[Candle]:
        for ext, loader in [(".csv", self._load_csv), (".parquet", self._load_parquet), (".json", self._load_json)]:
            filepath = self._data_dir / f"{symbol}_{timeframe}{ext}"
            if filepath.exists():
                log.info("HistoricalDataProvider: loading %s", filepath)
                return loader(filepath)
        return []

    def _load_csv(self, filepath: Path) -> List[Candle]:
        candles = []
        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                candles.append(Candle(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                ))
        return candles

    def _load_parquet(self, filepath: Path) -> List[Candle]:
        try:
            import pandas as pd
            df = pd.read_parquet(filepath)
            candles = []
            for _, row in df.iterrows():
                candles.append(Candle(
                    timestamp=row["timestamp"] if isinstance(row["timestamp"], datetime) else datetime.fromisoformat(str(row["timestamp"])),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                ))
            return candles
        except ImportError:
            log.error("HistoricalDataProvider: pandas required for parquet files")
            return []

    def _load_json(self, filepath: Path) -> List[Candle]:
        with open(filepath) as f:
            data = json.load(f)
        candles = []
        for item in data:
            candles.append(Candle(
                timestamp=datetime.fromisoformat(item["timestamp"]),
                open=float(item["open"]),
                high=float(item["high"]),
                low=float(item["low"]),
                close=float(item["close"]),
                volume=float(item["volume"]),
            ))
        return candles

    def save_candles(self, symbol: str, timeframe: str, candles: List[Candle], fmt: str = "csv"):
        filepath = self._data_dir / f"{symbol}_{timeframe}.{fmt}"
        if fmt == "csv":
            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
                for c in candles:
                    writer.writerow([c.timestamp.isoformat(), c.open, c.high, c.low, c.close, c.volume])
        elif fmt == "json":
            data = []
            for c in candles:
                data.append({
                    "timestamp": c.timestamp.isoformat(),
                    "open": c.open, "high": c.high, "low": c.low,
                    "close": c.close, "volume": c.volume,
                })
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
        log.info("HistoricalDataProvider: saved %d candles to %s", len(candles), filepath)
