import math
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from ENGINE.market.market_types import Candle
from .base import IDataProvider, TIMEFRAMES_MINUTES, DEFAULT_CANDLE_COUNTS


class MockDataProvider(IDataProvider):
    name = "MockDataProvider"

    def __init__(self, seed: Optional[int] = None):
        self._seed = seed
        self._rng = random.Random(seed) if seed is not None else random
        self._cache: Dict[str, List[Candle]] = {}

    def get_candles(
        self, symbol: str, timeframe: str, count: Optional[int] = None
    ) -> List[Candle]:
        cache_key = f"{symbol}:{timeframe}:{count}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        tf_minutes = TIMEFRAMES_MINUTES.get(timeframe, 60)
        n = count or DEFAULT_CANDLE_COUNTS.get(timeframe, 250)

        now = datetime.now(timezone.utc)
        base = self.base_prices.get(symbol, 50000.0)

        candles = self._generate_realistic_candles(base, n, tf_minutes, now, symbol)
        self._cache[cache_key] = candles
        return candles

    def _generate_realistic_candles(
        self, base: float, count: int, tf_minutes: int,
        now: datetime, symbol: str,
    ) -> List[Candle]:
        candles: List[Candle] = []

        regime = self._rng.choice(["trending_up", "trending_down", "ranging", "volatile"])
        trend_strength = self._rng.uniform(0.1, 0.8)
        trend_direction = 1.0 if regime in ("trending_up",) else -1.0 if regime in ("trending_down",) else 0.0

        adx_base = self._rng.uniform(15, 45)
        rvol_base = self._rng.uniform(0.5, 2.0)

        price = base
        phase = self._rng.uniform(0, 6.28)

        support = base * 0.95
        resistance = base * 1.05

        for i in range(count):
            ts = now - timedelta(minutes=tf_minutes * (count - i))

            swing = 0.002 * math.sin(phase + i * 0.1)
            trend = trend_direction * trend_strength * 0.001

            if regime == "volatile":
                vol = self._rng.uniform(0.003, 0.008)
            elif regime == "ranging":
                vol = self._rng.uniform(0.001, 0.003)
            else:
                vol = self._rng.uniform(0.001, 0.005)

            noise = self._rng.uniform(-vol, vol)

            mean_reversion = 0.0
            if price < support:
                mean_reversion = 0.002
            elif price > resistance:
                mean_reversion = -0.002

            change = price * (trend + swing + noise + mean_reversion)
            close = price + change

            if regime == "ranging":
                close = max(min(close, resistance), support)
                resistance += self._rng.uniform(-0.0005, 0.0005) * price
                support += self._rng.uniform(-0.0005, 0.0005) * price

            high = max(price, close) * (1 + abs(self._rng.gauss(0, vol * 0.3)))
            low = min(price, close) * (1 - abs(self._rng.gauss(0, vol * 0.3)))

            rvol_osc = rvol_base + 0.5 * math.sin(i * 0.05)
            volume = self._rng.uniform(500, 5000) * max(rvol_osc, 0.3) * (1 + abs(swing) * 3)

            candle = Candle(
                timestamp=ts,
                open=price,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
            candles.append(candle)
            price = close

        return candles

    def get_symbols(self) -> List[str]:
        return list(self.base_prices.keys())

    @property
    def base_prices(self) -> Dict[str, float]:
        return {
            "BTCUSDT": 65000.0, "ETHUSDT": 3500.0, "SOLUSDT": 145.0,
            "BNBUSDT": 580.0, "ADAUSDT": 0.45, "DOGEUSDT": 0.12,
        }

    def get_symbol_ticker(self, symbol: str) -> Optional[float]:
        base = self.base_prices.get(symbol, 50000.0)
        noise = self._rng.uniform(-0.005, 0.005) * base
        return base + noise

    def validate(self) -> bool:
        return True
