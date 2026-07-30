"""
K10 Watchlist — Futuros USDT (300-500 pares)
Gerada automaticamente via Binance Futures API
"""

import ccxt

def get_watchlist(min_volume_usdt: float = 1_000_000) -> list:
    """
    Busca todos os pares de futuros USDT na Binance com volume mínimo.
    Retorna lista ordenada por volume decrescente.
    """
    try:
        exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        })
        markets = exchange.load_markets()
        tickers = exchange.fetch_tickers()

        pares = []
        for symbol, market in markets.items():
            if not symbol.endswith("/USDT"):
                continue
            if not market.get("future", False) and not market.get("swap", False):
                continue
            ticker = tickers.get(symbol, {})
            vol = ticker.get("quoteVolume", 0) or 0
            if vol >= min_volume_usdt:
                pares.append((symbol, vol))

        pares.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in pares]

    except Exception as e:
        print(f"Erro ao buscar watchlist: {e}")
        return WATCHLIST_FALLBACK


# ── Fallback estático (top 50 caso a API falhe) ───────────────────────────────
WATCHLIST_FALLBACK = [
    "BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","XRP/USDT",
    "ADA/USDT","DOGE/USDT","AVAX/USDT","DOT/USDT","MATIC/USDT",
    "LINK/USDT","UNI/USDT","ATOM/USDT","LTC/USDT","ETC/USDT",
    "FIL/USDT","APT/USDT","ARB/USDT","OP/USDT","SUI/USDT",
    "INJ/USDT","TIA/USDT","SEI/USDT","WLD/USDT","PEPE/USDT",
    "SHIB/USDT","FLOKI/USDT","BONK/USDT","WIF/USDT","BOME/USDT",
    "NEAR/USDT","FTM/USDT","ALGO/USDT","SAND/USDT","MANA/USDT",
    "AXS/USDT","GALA/USDT","ENJ/USDT","CHZ/USDT","FLOW/USDT",
    "AAVE/USDT","MKR/USDT","SNX/USDT","CRV/USDT","1INCH/USDT",
    "DYDX/USDT","BLUR/USDT","GMX/USDT","PENDLE/USDT","JUP/USDT",
]
