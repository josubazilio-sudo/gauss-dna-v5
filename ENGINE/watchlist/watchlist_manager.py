import json
import logging
import os
from typing import List, Optional, Set

log = logging.getLogger(__name__)

WATCHLIST_PATH_ENV = "QUANTOS_WATCHLIST_PATH"
DEFAULT_WATCHLIST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "watchlist_priority.json",
)
WATCHLIST_PRIORITY_BONUS = 3


class WatchlistManager:
    """Gerencia a Watchlist Prioritária.

    Carrega a lista de símbolos do arquivo JSON, permite consulta e
    reordenação da fila de scan para que as moedas da watchlist sejam
    sempre processadas primeiro.
    """

    def __init__(self, path: Optional[str] = None):
        self._path = path or os.getenv(WATCHLIST_PATH_ENV, DEFAULT_WATCHLIST_PATH)
        self._symbols: Set[str] = set()
        self._ordered: List[str] = []
        self._loaded = False
        self.load()

    @property
    def symbols(self) -> Set[str]:
        return self._symbols

    @property
    def ordered(self) -> List[str]:
        return list(self._ordered)

    def load(self) -> bool:
        try:
            if not os.path.isfile(self._path):
                log.warning("WatchlistManager: arquivo nao encontrado em %s", self._path)
                self._symbols = set()
                self._ordered = []
                self._loaded = True
                return True
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("symbols", [])
            normalized = [s.strip().upper() for s in raw if s.strip()]
            self._ordered = normalized
            self._symbols = set(normalized)
            self._loaded = True
            log.info(
                "WatchlistManager: %d simbolos carregados de %s",
                len(self._symbols), self._path,
            )
            return True
        except Exception as e:
            log.error("WatchlistManager: erro ao carregar %s: %s", self._path, e)
            self._symbols = set()
            self._ordered = []
            return False

    def reload(self) -> bool:
        return self.load()

    def is_watchlist(self, symbol: str) -> bool:
        return symbol.upper() in self._symbols

    def reorder_scan_queue(self, pairs: List[str]) -> List[str]:
        """Coloca os pares da watchlist no início da fila de scan.

        Dentro de cada grupo (watchlist / resto), a ordem original é
        preservada para que o priority_score continue atuando.
        """
        if not self._loaded:
            self.load()
        watchlist_in_list = [p for p in pairs if self.is_watchlist(p)]
        rest = [p for p in pairs if not self.is_watchlist(p)]
        return watchlist_in_list + rest

    def count_in_list(self, pairs: List[str]) -> int:
        return sum(1 for p in pairs if self.is_watchlist(p))

    def stats_dict(self) -> dict:
        return {
            "total_watchlist": len(self._symbols),
            "symbols": self._ordered,
        }

    def get_priority_bonus(self, symbol: str) -> int:
        return WATCHLIST_PRIORITY_BONUS if self.is_watchlist(symbol) else 0
