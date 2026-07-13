import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter

from ENGINE.market.market_types import Candle
from .base import IDataProvider
from .config import MIN_VOLUME_USDT
from CORE.utils.timeframe_manager import TimeframeManager

log = logging.getLogger(__name__)

# Mapeamento mantido para compatibilidade, mas filtrado
TIMEFRAME_TO_MEXC: Dict[str, str] = {
    "30m": "30m", "1h": "60m", "4h": "4h", "1d": "1d",
}

# TTL do cache de candles — evita reusar dados congelados entre ciclos de scan.
CACHE_TTL_SECONDS = 60

# Limite de requisicoes HTTP simultaneas a MEXC — protege contra rate limit
# quando o scan roda com varios pares em paralelo (ThreadPoolExecutor em main.py).
MAX_CONCURRENT_REQUESTS = int(os.getenv("QUANTOS_MEXC_MAX_CONCURRENT", "12"))

# Pool de conexoes HTTP dimensionado para o numero de requisicoes concorrentes
# permitidas (MAX_CONCURRENT_REQUESTS). Sem isso, cada chamada requests.get()
# solta a conexao TCP/TLS ao final e a proxima paga o handshake completo de
# novo — medido em producao: ~10s na 1a chamada a /klines, ~0.3s (30x mais
# rapido) nas chamadas seguintes quando a conexao e reaproveitada.
_POOL_SIZE = max(MAX_CONCURRENT_REQUESTS, 10)

class MexcDataProvider(IDataProvider):
    name = "MexcDataProvider"

    def __init__(self, api_key: str = "", api_secret: str = "", rest_url: str = "https://api.mexc.com"):
        self._api_key = api_key
        self._api_secret = api_secret
        self._rest_url = rest_url
        self._cache: Dict[str, Tuple[float, List[Candle]]] = {}
        self._cache_lock = threading.Lock()
        self._request_gate = threading.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=_POOL_SIZE, pool_maxsize=_POOL_SIZE)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def get_candles(
        self, symbol: str, timeframe: str, count: Optional[int] = None
    ) -> List[Candle]:
        if not TimeframeManager.is_valid(timeframe):
            log.error(f"MexcDataProvider: Invalid timeframe request: {timeframe}")
            return []

        cache_key = f"{symbol}:{timeframe}:{count}"
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
                return cached[1]

        mexc_tf = TIMEFRAME_TO_MEXC.get(timeframe, timeframe)
        limit = min(count or 250, 1000)

        candles = self._fetch_klines(symbol, mexc_tf, limit)
        if candles:
            with self._cache_lock:
                self._cache[cache_key] = (time.time(), candles)
        return candles

    def _fetch_klines(self, symbol: str, interval: str, limit: int = 250) -> List[Candle]:
        try:
            url = f"{self._rest_url}/api/v3/klines"
            params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
            headers = {}
            if self._api_key:
                headers["X-MEXC-APIKEY"] = self._api_key
            with self._request_gate:
                resp = self._session.get(url, params=params, headers=headers, timeout=15)
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
            log.info("MexcDataProvider: fetched %d candles for %s %s", len(candles), symbol, interval)
            return candles
        except Exception as e:
            log.error("MexcDataProvider: error fetching %s %s: %s", symbol, interval, e)
            return []

    def get_symbols(self) -> List[str]:
        """Descobre pares USDT elegiveis: com trading spot habilitado e
        volume 24h acima de MIN_VOLUME_USDT (CORE/data_providers/config.py)."""
        try:
            info_resp = self._session.get(f"{self._rest_url}/api/v3/exchangeInfo", timeout=15)
            info_resp.raise_for_status()
            info = info_resp.json()

            eligible = set()
            for s in info.get("symbols", []):
                if (
                    s.get("status") != "UNKNOWN"
                    and s.get("quoteAsset") == "USDT"
                    and s.get("isSpotTradingAllowed", True)
                ):
                    eligible.add(s["symbol"])

            volumes: Dict[str, float] = {}
            try:
                vol_resp = self._session.get(f"{self._rest_url}/api/v3/ticker/24hr", timeout=20)
                vol_resp.raise_for_status()
                for t in vol_resp.json():
                    sym = t.get("symbol", "")
                    if sym in eligible:
                        try:
                            volumes[sym] = float(t.get("quoteVolume", 0))
                        except (TypeError, ValueError):
                            volumes[sym] = 0.0
            except Exception as e:
                log.warning("MexcDataProvider: falha ao buscar volume 24h, seguindo sem filtro de volume: %s", e)

            if volumes:
                symbols = [s for s in eligible if volumes.get(s, 0.0) >= MIN_VOLUME_USDT]
                dropped_no_volume_data = len(eligible) - len(volumes)
                dropped_low_volume = len(volumes) - len(symbols)
                log.info(
                    "MexcDataProvider: %d/%d pares elegiveis (trading habilitado); "
                    "%d descartados por volume < $%.0f, %d sem dado de volume",
                    len(symbols), len(eligible), dropped_low_volume, MIN_VOLUME_USDT, dropped_no_volume_data,
                )
            else:
                symbols = list(eligible)

            symbols.sort()
            log.info("MexcDataProvider: discovered %d USDT pairs (min volume $%.0f)", len(symbols), MIN_VOLUME_USDT)
            return symbols
        except Exception as e:
            log.error("MexcDataProvider: error fetching exchange info: %s", e)
            return []

    def get_ticker_24h_snapshot(self) -> Dict[str, Dict]:
        """RFC V19.3: reaproveita o MESMO endpoint bulk /api/v3/ticker/24hr
        ja usado em get_symbols() (nao adiciona chamada de API por par),
        mas extrai priceChangePercent/highPrice/lowPrice/lastPrice alem
        de quoteVolume, para priorizar a ordem de varredura do scanner."""
        snapshot: Dict[str, Dict] = {}
        try:
            resp = self._session.get(f"{self._rest_url}/api/v3/ticker/24hr", timeout=20)
            resp.raise_for_status()
            for t in resp.json():
                sym = t.get("symbol", "")
                if not sym:
                    continue
                try:
                    snapshot[sym] = {
                        "quote_volume": float(t.get("quoteVolume", 0) or 0),
                        "price_change_percent": float(t.get("priceChangePercent", 0) or 0),
                        "high_price": float(t.get("highPrice", 0) or 0),
                        "low_price": float(t.get("lowPrice", 0) or 0),
                        "last_price": float(t.get("lastPrice", 0) or 0),
                    }
                except (TypeError, ValueError):
                    continue
        except Exception as e:
            log.warning("MexcDataProvider: falha ao buscar ticker 24h snapshot: %s", e)
        return snapshot

    def get_symbol_ticker(self, symbol: str) -> Optional[float]:
        try:
            url = f"{self._rest_url}/api/v3/ticker/price"
            params = {"symbol": symbol.upper()}
            with self._request_gate:
                resp = self._session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return float(data["price"])
        except Exception as e:
            log.error("MexcDataProvider: error fetching ticker for %s: %s", symbol, e)
            return None

    def validate(self) -> bool:
        try:
            candles = self._fetch_klines("BTCUSDT", "1h", 2)
            return len(candles) >= 2
        except Exception:
            return False
