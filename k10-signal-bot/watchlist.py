"""
K10 Watchlist — Futuros USDT MEXC (300-500 pares)
"""

import ccxt

def get_watchlist(min_volume_usdt: float = 500_000) -> list:
    """
    Busca todos os pares de futuros USDT na MEXC com volume mínimo.
    Retorna lista ordenada por volume decrescente.
    """
    try:
        exchange = ccxt.mexc({
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })
        markets = exchange.load_markets()
        tickers = exchange.fetch_tickers()

        pares = []
        for symbol, market in markets.items():
            if not symbol.endswith("/USDT:USDT"):
                continue
            ticker = tickers.get(symbol, {})
            vol = ticker.get("quoteVolume", 0) or 0
            if vol >= min_volume_usdt:
                pares.append((symbol, vol))

        pares.sort(key=lambda x: x[1], reverse=True)
        result = [p[0] for p in pares]
        print(f"MEXC futuros encontrados: {len(result)}")
        return result

    except Exception as e:
        print(f"Erro ao buscar watchlist MEXC: {e}")
        return WATCHLIST_FALLBACK


# ── Fallback estático MEXC ────────────────────────────────────────────────────
WATCHLIST_FALLBACK = [
    "BTC/USDT:USDT","ETH/USDT:USDT","BNB/USDT:USDT","SOL/USDT:USDT","XRP/USDT:USDT",
    "ADA/USDT:USDT","DOGE/USDT:USDT","AVAX/USDT:USDT","DOT/USDT:USDT","MATIC/USDT:USDT",
    "LINK/USDT:USDT","UNI/USDT:USDT","ATOM/USDT:USDT","LTC/USDT:USDT","ETC/USDT:USDT",
    "APT/USDT:USDT","ARB/USDT:USDT","OP/USDT:USDT","SUI/USDT:USDT","INJ/USDT:USDT",
    "TIA/USDT:USDT","SEI/USDT:USDT","WLD/USDT:USDT","PEPE/USDT:USDT","NEAR/USDT:USDT",
    "FTM/USDT:USDT","AAVE/USDT:USDT","CRV/USDT:USDT","DYDX/USDT:USDT","JUP/USDT:USDT",
    "BONK/USDT:USDT","WIF/USDT:USDT","FLOKI/USDT:USDT","SHIB/USDT:USDT","GALA/USDT:USDT",
    "SAND/USDT:USDT","MANA/USDT:USDT","AXS/USDT:USDT","CHZ/USDT:USDT","FLOW/USDT:USDT",
    "MKR/USDT:USDT","SNX/USDT:USDT","1INCH/USDT:USDT","BLUR/USDT:USDT","GMX/USDT:USDT",
    "PENDLE/USDT:USDT","ONDO/USDT:USDT","FIL/USDT:USDT","ALGO/USDT:USDT","ENJ/USDT:USDT",
]
