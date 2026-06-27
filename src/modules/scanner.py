"""Scanner MEXC — suporta multi-timeframe."""

import asyncio
import aiohttp
import logging

from config import MEXC_BASE

logger = logging.getLogger(__name__)

_TF_MEXC = {"5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m", "4h": "4h"}


async def fetch(session, url):
    async with session.get(url) as resp:
        return await resp.json()


async def buscar_candles(session, symbol, timeframe="1h", limit=200):
    tf = _TF_MEXC.get(timeframe, "60m")
    url = f"{MEXC_BASE}/klines?symbol={symbol}&interval={tf}&limit={limit}"
    data = await fetch(session, url)
    if isinstance(data, dict) and "code" in data:
        return []
    return [[float(x) for x in row[:6]] for row in data]


async def buscar_top_pares_usdt(session, top_n=300):
    url = f"{MEXC_BASE}/ticker/24hr"
    data = await fetch(session, url)
    if not isinstance(data, list):
        return []
    pares = [p for p in data if isinstance(p, dict) and p.get("symbol", "").endswith("USDT")]
    pares.sort(key=lambda p: float(p.get("quoteVolume", 0) or 0), reverse=True)
    return [p["symbol"] for p in pares[:top_n]]


async def scan_market(session=None, top_n=300, timeframes=None):
    """
    Escaneia multiplos timeframes para cada par.

    Args:
        session: aiohttp session (opcional)
        top_n: numero de pares
        timeframes: lista de timeframes (ex: ["15m", "1h", "4h"])

    Returns: { "SYMBOL": { "15m": [...], "1h": [...], "4h": [...] }, ... }
    """
    if timeframes is None:
        timeframes = ["15m", "1h", "4h"]

    if session is None:
        async with aiohttp.ClientSession() as _session:
            return await _scan_mtf(_session, top_n, timeframes)
    return await _scan_mtf(session, top_n, timeframes)


async def _scan_mtf(session, top_n, timeframes):
    top_pairs = await buscar_top_pares_usdt(session, top_n)
    pairs = top_pairs[:top_n]
    logger.info("Scan multi-timeframe: %d pares, timeframes=%s", len(pairs), timeframes)

    # Rate limit: max 10 concurrent requests to avoid MEXC throttling
    sem = asyncio.Semaphore(10)

    async def _fetch_com_limite(pair, tf):
        async with sem:
            candles = await buscar_candles(session, pair, tf)
            return pair, tf, candles

    tasks = [_fetch_com_limite(pair, tf) for pair in pairs for tf in timeframes]
    resultados = await asyncio.gather(*tasks)
    
    market_data = {}
    for pair, tf, candles in resultados:
        if pair not in market_data:
            market_data[pair] = {}
        if len(candles) >= 50:
            market_data[pair][tf] = candles[:-1]
    
    # Remove pares que nao tem todos os TFs
    market_data = {p: d for p, d in market_data.items() if len(d) == len(timeframes)}

    logger.info("Scan concluido: %d pares com dados completos", len(market_data))
    return market_data
