"""Scanner MEXC."""

import aiohttp
import logging

from config import MEXC_BASE, MEXC_CONTRACT

logger = logging.getLogger(__name__)

_TF_MEXC = {"5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m", "4h": "4h"}


async def fetch(session, url):
    async with session.get(url) as resp:
        return await resp.json()


async def buscar_candles(session, symbol, timeframe="1h", limit=200):
    tf = _TF_MEXC.get(timeframe, "60m")
    url = f"{MEXC_BASE}/klines?symbol={symbol}&interval={tf}&limit={limit}"
    data = await fetch(session, url)
    if "code" in data:
        return []
    return [[float(x) for x in row[:6]] for row in data]


async def buscar_top_pares_usdt(session, top_n=300):
    url = f"{MEXC_BASE}/ticker/24hr"
    data = await fetch(session, url)
    pares = [p for p in data if p["symbol"].endswith("USDT")]
    pares.sort(key=lambda p: float(p["quoteVolume"]), reverse=True)
    return [p["symbol"] for p in pares[:top_n]]


async def scan_market(session=None, top_n=300, timeframe="1h"):
    if session is None:
        async with aiohttp.ClientSession() as _session:
            return await _scan(_session, top_n, timeframe)
    return await _scan(session, top_n, timeframe)


async def _scan(session, top_n, timeframe):
    top_pairs = await buscar_top_pares_usdt(session, top_n)
    pairs = top_pairs[:top_n]

    market_data = {}
    for pair in pairs:
        candles = await buscar_candles(session, pair, timeframe)
        if len(candles) >= 50:
            # Remove o candle atual (incompleto) — usa apenas velas fechadas
            market_data[pair] = candles[:-1]

    logger.info("Scan concluído: %d pares carregados", len(market_data))
    return market_data
