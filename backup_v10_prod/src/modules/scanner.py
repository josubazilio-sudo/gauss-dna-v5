"""Scanner MEXC — suporta multi-timeframe."""

import asyncio
import aiohttp
import logging

from config import MEXC_BASE

logger = logging.getLogger(__name__)

_TF_MEXC = {"5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m", "4h": "4h"}


async def fetch(session, url, timeout=15, retries=3):
    for i in range(retries):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    return await resp.json()
                await asyncio.sleep(0.5 * (i + 1)) # Backoff simples
        except Exception as e:
            if i == retries - 1:
                logger.error(f"Falha na API após {retries} tentativas: {url} | Erro: {e}")
            await asyncio.sleep(1)
    return None


async def buscar_candles(session, symbol, timeframe="1h", limit=200):
    tf = _TF_MEXC.get(timeframe, "60m")
    url = f"{MEXC_BASE}/klines?symbol={symbol}&interval={tf}&limit={limit}"
    data = await fetch(session, url, timeout=8)
    if not isinstance(data, list):
        return []
    try:
        return [[float(x) for x in row[:6]] for row in data]
    except Exception:
        return []


async def buscar_top_pares_usdt(session, top_n=300):
    url = f"{MEXC_BASE}/ticker/24hr"
    data = await fetch(session, url, timeout=15)
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

    market_data = {}
    batch_size = 2
    total_batches = (len(pairs) + batch_size - 1) // batch_size

    for batch_idx in range(0, len(pairs), batch_size):
        batch = pairs[batch_idx:batch_idx + batch_size]
        tasks = [
            asyncio.create_task(buscar_candles(session, pair, tf))
            for pair in batch for tf in timeframes
        ]
        resultados = await asyncio.gather(*tasks)

        i = 0
        for pair in batch:
            for tf in timeframes:
                candles = resultados[i]
                i += 1
                if pair not in market_data:
                    market_data[pair] = {}
                if len(candles) >= 50:
                    market_data[pair][tf] = candles[:-1]
            if len(market_data.get(pair, {})) != len(timeframes):
                market_data.pop(pair, None)

        if batch_idx + batch_size < len(pairs):
            await asyncio.sleep(0.8)

    logger.info("Scan concluido: %d pares com dados completos", len(market_data))
    return market_data
