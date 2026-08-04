"""
K10 Watchlist — Futuros USDT MEXC
Busca apenas pares realmente listados nos futuros da MEXC
"""

import ccxt

def get_watchlist(min_volume_usdt: float = 500_000) -> list:
    try:
        exchange = ccxt.mexc({
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })

        # Carrega apenas mercados do tipo swap (futuros perpétuos MEXC)
        markets = exchange.load_markets()

        # Filtra apenas os que são swap/futuro USDT e estão ativos
        futuros = []
        for symbol, market in markets.items():
            if not market.get("active", False):
                continue
            if market.get("type") not in ("swap", "future"):
                continue
            if not market.get("linear", False):
                continue
            if not symbol.endswith("/USDT:USDT"):
                continue
            futuros.append(symbol)

        if not futuros:
            print("⚠️ Nenhum futuro encontrado, usando fallback")
            return WATCHLIST_FALLBACK

        # Filtra por volume mínimo
        try:
            tickers = exchange.fetch_tickers(futuros)
            com_volume = []
            for symbol in futuros:
                ticker = tickers.get(symbol, {})
                vol = ticker.get("quoteVolume", 0) or 0
                if vol >= min_volume_usdt:
                    com_volume.append((symbol, vol))
            com_volume.sort(key=lambda x: x[1], reverse=True)
            result = [p[0] for p in com_volume]
        except Exception:
            # Se fetch_tickers falhar, retorna todos os futuros sem filtro de volume
            result = futuros

        print(f"✅ MEXC futuros reais encontrados: {len(result)}")
        return result

    except Exception as e:
        print(f"Erro ao buscar watchlist MEXC: {e}")
        return WATCHLIST_FALLBACK


# Fallback — pares confirmados nos futuros MEXC
# Lista prioritária — seus pares favoritos (escaneados primeiro)
WATCHLIST_PRIORITY = [
    "PENDLE/USDT:USDT",
    "SPCX/USDT:USDT",
    "OPG/USDT:USDT",
    "EPIC/USDT:USDT",
    "SKYAI/USDT:USDT",
    "HOME/USDT:USDT",
    "ALLO/USDT:USDT",
    "WLD/USDT:USDT",
    "H/USDT:USDT",
    "BEAT/USDT:USDT",
]

WATCHLIST_FALLBACK = [
    "BTC/USDT:USDT","ETH/USDT:USDT","BNB/USDT:USDT","SOL/USDT:USDT","XRP/USDT:USDT",
    "ADA/USDT:USDT","DOGE/USDT:USDT","AVAX/USDT:USDT","DOT/USDT:USDT","MATIC/USDT:USDT",
    "LINK/USDT:USDT","UNI/USDT:USDT","ATOM/USDT:USDT","LTC/USDT:USDT","ETC/USDT:USDT",
    "APT/USDT:USDT","ARB/USDT:USDT","OP/USDT:USDT","SUI/USDT:USDT","INJ/USDT:USDT",
    "TIA/USDT:USDT","SEI/USDT:USDT","WLD/USDT:USDT","PEPE/USDT:USDT","NEAR/USDT:USDT",
    "AAVE/USDT:USDT","CRV/USDT:USDT","DYDX/USDT:USDT","JUP/USDT:USDT","ONDO/USDT:USDT",
    "BONK/USDT:USDT","WIF/USDT:USDT","FLOKI/USDT:USDT","SHIB/USDT:USDT","FIL/USDT:USDT",
    "ALGO/USDT:USDT","SAND/USDT:USDT","MANA/USDT:USDT","AXS/USDT:USDT","GMX/USDT:USDT",
    "PENDLE/USDT:USDT","MKR/USDT:USDT","SNX/USDT:USDT","BLUR/USDT:USDT","FTM/USDT:USDT",
]
