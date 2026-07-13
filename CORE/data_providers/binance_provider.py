import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ENGINE.market.market_types import Candle
from .base import IDataProvider
from CORE.utils.timeframe_manager import TimeframeManager

log = logging.getLogger(__name__)

# Mapeamento mantido para compatibilidade, mas filtrado
TIMEFRAME_TO_BINANCE: Dict[str, str] = {
    "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1d",
}

# TTL do cache de candles — evita reusar dados congelados entre ciclos de scan.
CACHE_TTL_SECONDS = 60

class BinanceDataProvider(IDataProvider):
    name = "BinanceDataProvider"

    def __init__(self, api_key: str = "", api_secret: str = "", rest_url: str = "https://api.binance.com"):
        self._api_key = api_key
        self._api_secret = api_secret
        self._rest_url = rest_url
        self._cache: Dict[str, Tuple[float, List[Candle]]] = {}

    def get_candles(
        self, symbol: str, timeframe: str, count: Optional[int] = None
    ) -> List[Candle]:
        if not TimeframeManager.is_valid(timeframe):
            log.error(f"BinanceDataProvider: Invalid timeframe request: {timeframe}")
            return []

        cache_key = f"{symbol}:{timeframe}:{count}"
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        binance_tf = TIMEFRAME_TO_BINANCE.get(timeframe, timeframe)
        limit = min(count or 250, 1000)

        candles = self._fetch_klines(symbol, binance_tf, limit)
        if candles:
            self._cache[cache_key] = (time.time(), candles)
        return candles

    def _fetch_klines(self, symbol: str, interval: str, limit: int = 250) -> List[Candle]:
        try:
            import requests
            url = f"{self._rest_url}/api/v3/klines"
            params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            candles = []
            for k in data:
                candles.append(Candle(
                    timestamp=datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                ))
            log.info("BinanceDataProvider: fetched %d candles for %s %s", len(candles), symbol, interval)
            return candles
        except Exception as e:
            log.error("BinanceDataProvider: error fetching %s %s: %s", symbol, interval, e)
            return []

    def get_symbols(self) -> List[str]:
        try:
            import requests
            url = f"{self._rest_url}/api/v3/exchangeInfo"
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            symbols = []
            for s in data.get("symbols", []):
                if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
                    symbols.append(s["symbol"])
            symbols.sort()
            log.info("BinanceDataProvider: discovered %d USDT pairs", len(symbols))
            return symbols
        except Exception as e:
            log.error("BinanceDataProvider: error fetching exchange info: %s", e)
            return []

    def get_symbol_ticker(self, symbol: str) -> Optional[float]:
        try:
            import requests
            url = f"{self._rest_url}/api/v3/ticker/price"
            params = {"symbol": symbol.upper()}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return float(data["price"])
        except Exception as e:
            log.error("BinanceDataProvider: error fetching ticker for %s: %s", symbol, e)
            return None

    def validate(self) -> bool:
        try:
            candles = self._fetch_klines("BTCUSDT", "1h", 2)
            return len(candles) >= 2
        except Exception:
            return False
