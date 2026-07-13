import os
import json
import time
import logging
from enum import Enum
from typing import Optional, List, Tuple, Dict, Any
from SERVICES.telegram.update_engine import UpdateEngine

log = logging.getLogger(__name__)

SIGNAL_STATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "MEMORY", "state")
SIGNAL_FILE = os.path.join(SIGNAL_STATE_DIR, "signals.json")


class SignalState(Enum):
    OPEN = "OPEN"
    TP1 = "TP1"
    BREAKEVEN = "BREAKEVEN"
    TRAILING = "TRAILING"
    TP_FINAL = "TP_FINAL"
    STOPPED = "STOPPED"
    CANCELADA = "CANCELADA"


def make_signal_id(symbol, timeframe, direction, entry, stop):
    s = stop if stop is not None else 0
    return f"{symbol.upper()}_{timeframe.upper()}_{direction.upper()}_{float(entry):.2f}_{float(s):.2f}"


def estado_ativo(state):
    return state in (SignalState.OPEN, SignalState.TP1, SignalState.BREAKEVEN, SignalState.TRAILING)


def make_setup_hash(symbol, timeframe, direction, entry, tp, stop):
    """V19.1: hash unico do setup para deteccao de duplicatas."""
    return f"{symbol.upper()}_{timeframe.upper()}_{direction.upper()}_{entry:.4f}_{tp:.4f}_{stop:.4f}"


class SignalRecord:
    def __init__(self, signal_id, symbol, timeframe, direction, entry, stop,
                 score=0, conviction=0, classificacao="", estado=SignalState.OPEN,
                 take_profit=0.0, trend="", consensus=0.0, raw_data: Optional[Dict[str, Any]] = None):
        self.signal_id = signal_id
        self.symbol = symbol.upper()
        self.timeframe = timeframe.upper()
        self.direction = direction.upper()
        self.entry = float(entry)
        self.stop = float(stop)
        self.take_profit = float(take_profit)
        self.score = score
        self.conviction = conviction
        self.classificacao = classificacao
        self.trend = trend
        self.consensus = consensus
        self.estado = estado
        self.envio_ts = time.time()
        self.ultimo_update_ts = time.time()
        self.candles_desde_envio = 0
        self.setup_hash = make_setup_hash(symbol, timeframe, direction, entry, take_profit, stop)
        self.raw_data = raw_data or {}

    def diff(self, other):
        """V19.1: detecta mudancas relevantes para reenvio."""
        changes = {}
        if abs(self.entry - other.entry) / max(self.entry, 0.0001) * 100 > 0.30:
            changes["entrada"] = abs(self.entry - other.entry) / max(self.entry, 0.0001) * 100
        if abs(self.stop - other.stop) / max(self.stop, 0.0001) * 100 > 0.20:
            changes["stop"] = abs(self.stop - other.stop) / max(self.stop, 0.0001) * 100
        if other.take_profit > 0 and abs(self.take_profit - other.take_profit) / max(self.take_profit, 0.0001) * 100 > 0.30:
            changes["tp"] = abs(self.take_profit - other.take_profit) / max(self.take_profit, 0.0001) * 100
        if other.score - self.score >= 10:
            changes["score"] = other.score - self.score
        if other.conviction - self.conviction >= 15:
            changes["conviccao"] = other.conviction - self.conviction
        if other.consensus > 0 and abs(other.consensus - self.consensus) > 15:
            changes["consenso"] = other.consensus - self.consensus
        if other.trend and other.trend != self.trend:
            changes["tendencia"] = other.trend
        return changes

    def to_dict(self):
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "entry": self.entry,
            "stop": self.stop,
            "take_profit": self.take_profit,
            "score": self.score,
            "conviction": self.conviction,
            "classificacao": self.classificacao,
            "trend": self.trend,
            "consensus": self.consensus,
            "estado": self.estado.value,
            "envio_ts": self.envio_ts,
            "ultimo_update_ts": self.ultimo_update_ts,
            "setup_hash": self.setup_hash,
            "raw_data": self.raw_data,
        }

    @staticmethod
    def from_dict(d):
        r = SignalRecord(
            d.get("signal_id", ""), d.get("symbol", ""), d.get("timeframe", ""),
            d.get("direction", ""), d.get("entry", 0.0), d.get("stop", 0.0),
            d.get("score", 0), d.get("conviction", 0),
            d.get("classificacao", ""), SignalState(d.get("estado", "OPEN")),
            d.get("take_profit", 0.0), d.get("trend", ""), d.get("consensus", 0.0),
            raw_data=d.get("raw_data", {}),
        )
        r.envio_ts = d.get("envio_ts", time.time())
        r.ultimo_update_ts = d.get("ultimo_update_ts", time.time())
        r.setup_hash = d.get("setup_hash", r.setup_hash)
        return r


class SignalTracker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._signals = {}
        self._by_symbol = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(SIGNAL_FILE):
                with open(SIGNAL_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                for d in data:
                    r = SignalRecord.from_dict(d)
                    self._signals[r.signal_id] = r
                    self._by_symbol.setdefault(r.symbol, []).append(r)
                log.info("SignalTracker: loaded %d signals from %s", len(self._signals), SIGNAL_FILE)
        except Exception as e:
            log.warning("SignalTracker: error loading signals: %s", e)

    def _save(self):
        try:
            os.makedirs(SIGNAL_STATE_DIR, exist_ok=True)
            data = [r.to_dict() for r in self._signals.values()]
            with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.warning("SignalTracker: error saving signals: %s", e)

    def get_ativo_para(self, symbol, direction, timeframe="1H"):
        ativos = self._by_symbol.get(symbol.upper(), [])
        for r in ativos:
            if r.direction == direction.upper() and r.timeframe == timeframe.upper() and estado_ativo(r.estado):
                return r
        return None

    def get_recently_approved_pairs(self, window_hours: float = 4.0) -> list:
        """RFC V19.3: leitura apenas — pares com sinal aprovado/enviado nas
        ultimas `window_hours` horas, usados como bonus de PRIORITY_SCORE
        (nao afeta aprovacao/reenvio de sinal, so a ordem do scanner)."""
        cutoff = time.time() - window_hours * 3600
        return [
            symbol for symbol, records in self._by_symbol.items()
            if any(r.envio_ts >= cutoff for r in records)
        ]

    def registrar_envio(self, signal_id, symbol, timeframe, direction, entry, stop,
                        score=0, conviction=0, classificacao="", candles_total=0,
                        take_profit=0.0, raw_data: Optional[Dict[str, Any]] = None):
        r = SignalRecord(signal_id, symbol, timeframe, direction, entry, stop,
                         score, conviction, classificacao, take_profit=take_profit,
                         raw_data=raw_data)
        r.candles_desde_envio = candles_total
        self._signals[signal_id] = r
        self._by_symbol.setdefault(symbol.upper(), []).append(r)
        self._save()
        return r

    def atualizar(self, signal_id, score=None, conviction=None, estado=None,
                  entry=None, stop=None, candles_total=None, raw_data: Optional[Dict[str, Any]] = None):
        r = self._signals.get(signal_id)
        if not r:
            return None
        if score is not None:
            r.score = score
        if conviction is not None:
            r.conviction = conviction
        if entry is not None:
            r.entry = float(entry)
        if stop is not None:
            r.stop = float(stop)
        if estado is not None:
            if isinstance(estado, str):
                estado = SignalState(estado)
            r.estado = estado
        if candles_total is not None:
            r.candles_desde_envio = candles_total
        if raw_data is not None:
            r.raw_data = raw_data
        r.ultimo_update_ts = time.time()
        self._save()
        return r

    def encerrar(self, signal_id, estado_final=SignalState.CANCELADA):
        return self.atualizar(signal_id, estado=estado_final)

    def pode_reenviar(self, signal_id, new_data: Dict[str, Any]):
        """RFC V18.5: usa UpdateEngine para decidir se reenvia."""
        r = self._signals.get(signal_id)
        if not r:
            return True, "novo_sinal"
        
        if not estado_ativo(r.estado):
            return True, f"sinal_encerrado_{r.estado.value}"

        old_data = r.raw_data if (hasattr(r, "raw_data") and r.raw_data) else r.to_dict()
        update_type = UpdateEngine.get_update_type(old_data, new_data)
        if update_type:
            return True, update_type
            
        return False, "setup_identico_sem_mudancas_relevantes"


_signal_tracker = SignalTracker()


def get_tracker():
    return _signal_tracker
