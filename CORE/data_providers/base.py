from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from ENGINE.market.market_types import Candle
from CORE.utils.timeframe_manager import TimeframeManager

# Usando apenas os timeframes permitidos
TIMEFRAMES_MINUTES: Dict[str, int] = {
    "30m": 30, "1h": 60, "4h": 240, "1d": 1440,
}

DEFAULT_CANDLE_COUNTS: Dict[str, int] = {
    "30m": 200, "1h": 250, "4h": 250, "1d": 250,
}

class IDataProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def get_candles(
        self, symbol: str, timeframe: str, count: Optional[int] = None
    ) -> List[Candle]:
        ...

    @abstractmethod
    def get_symbols(self) -> List[str]:
        ...

    def get_all_timeframes(
        self,
        symbol: str,
        timeframes: Optional[List[str]] = None,
        counts: Optional[Dict[str, int]] = None,
    ) -> Dict[str, List[Candle]]:
        tfs = timeframes or list(TIMEFRAMES_MINUTES.keys())
        cnts = counts or DEFAULT_CANDLE_COUNTS
        result: Dict[str, List[Candle]] = {}
        for tf in tfs:
            if not TimeframeManager.is_valid(tf):
                continue
            count = cnts.get(tf, 250)
            try:
                candles = self.get_candles(symbol, tf, count)
                if candles and len(candles) >= 20:
                    result[tf] = candles
            except Exception:
                pass
        return result

    def get_symbol_ticker(self, symbol: str) -> Optional[float]:
        return None

    def get_ticker_24h_snapshot(self) -> Dict[str, Dict]:
        """RFC V19.3: snapshot de ticker 24h em lote (1 chamada), usado
        apenas para priorizar a ORDEM de varredura do scanner. Default
        seguro (dict vazio) para providers que nao implementam — a
        priorizacao degrada silenciosamente para a ordem alfabetica atual."""
        return {}

    def validate(self) -> bool:
        return True
