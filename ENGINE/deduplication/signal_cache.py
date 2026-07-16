import hashlib
import logging
import math
import time
from typing import Any, Dict, Optional, Tuple

TIMEFRAME_SECONDS = {
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "1d": 86400,
}

# RFC V26.X: diferenca maxima de entrada, em %, para duas leituras do
# mesmo ativo/direcao/timeframe/candle serem consideradas o MESMO sinal.
DUPLICATE_ENTRY_MAX_DIFF_PCT = 0.10

log = logging.getLogger(__name__)


def _get_candle_open(timeframe: str) -> int:
    seconds = TIMEFRAME_SECONDS.get(timeframe, 3600)
    return int(time.time() // seconds) * seconds


def _is_small_change(value_a: float, value_b: float, max_change: float) -> bool:
    if value_a == 0 and value_b == 0:
        return True
    if value_a == 0 or value_b == 0:
        return False
    pct = abs(value_a - value_b) / max(abs(value_a), abs(value_b)) * 100
    return pct <= max_change


def _setup_fingerprint(data: Optional[Dict]) -> Tuple[bool, bool, bool, bool]:
    """RFC V26.X: assinatura do setup estrutural (BOS/CHoCH/Order Block/
    FVG) que sustenta o sinal — lida dos mesmos campos reais que
    SignalDecision.to_dict() ja expoe (bos/choch/fvg como contagens,
    selected_order_block como string), sem recalcular nada."""
    if not data:
        return (False, False, False, False)
    return (
        bool(data.get("bos", 0)),
        bool(data.get("choch", 0)),
        bool(data.get("selected_order_block")),
        bool(data.get("fvg", 0)),
    )


def compute_signal_fingerprint(
    symbol: str, timeframe: str, direction: str,
    entry_price: float, candle_open: int, data: Optional[Dict] = None,
) -> str:
    """RFC V26.X: fingerprint unico por setup — mesmo ativo, direcao,
    timeframe, candle, faixa de entrada (bucket de
    DUPLICATE_ENTRY_MAX_DIFF_PCT%) e setup estrutural produzem o mesmo
    fingerprint. Bucketing logaritmico: dois precos caem no mesmo bucket
    se e somente se estiverem a menos de DUPLICATE_ENTRY_MAX_DIFF_PCT%
    um do outro — um bucket de largura absoluta (entry/largura) nao
    funciona aqui porque a largura tambem escala com o preco, cancelando
    a proporcao e colapsando qualquer preco no mesmo bucket."""
    if entry_price <= 0:
        bucket = 0
    else:
        ratio = 1 + DUPLICATE_ENTRY_MAX_DIFF_PCT / 100
        bucket = round(math.log(entry_price) / math.log(ratio))
    raw = (
        f"{symbol.upper()}|{timeframe}|{direction.upper()}|{candle_open}|"
        f"{bucket}|{_setup_fingerprint(data)}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


class SignalCacheEngine:
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._entry_score: Dict[str, float] = {}
        self._quality: Dict[str, float] = {}
        self._probability: Dict[str, float] = {}
        self._direction: Dict[str, str] = {}
        self._entry_price: Dict[str, float] = {}
        # RFC V26.X: assinatura do setup estrutural (BOS/CHoCH/Order
        # Block/FVG) do ultimo sinal enviado por chave, e contador de
        # duplicados bloqueados (para o diagnostico diario).
        self._setup: Dict[str, Tuple[bool, bool, bool, bool]] = {}
        self._duplicate_blocked_count: int = 0

    @property
    def duplicate_blocked_count(self) -> int:
        return self._duplicate_blocked_count

    def fingerprint(
        self, symbol: str, timeframe: str, direction: str,
        entry_price: float, data: Optional[Dict] = None,
    ) -> str:
        """RFC V26.X: fingerprint unico do setup atual (ver
        compute_signal_fingerprint), para rastreabilidade/auditoria."""
        candle_open = _get_candle_open(timeframe)
        return compute_signal_fingerprint(
            symbol, timeframe, direction, entry_price, candle_open, data,
        )

    def _make_key(self, symbol: str, timeframe: str, direction: str, candle_open: int) -> str:
        return f"{symbol.upper()}_{timeframe}_{direction.upper()}_{candle_open}"

    def _can_send_by_cache(self, key: str, data: Optional[Dict] = None) -> bool:
        return key not in self._cache

    def _can_send_by_reversal(self, key: str, direction: str, candle_open: int) -> bool:
        base_key = f"{key.rsplit('_', 1)[0]}"
        for existing_key, existing_entry in list(self._cache.items()):
            if existing_key.startswith(base_key) and existing_entry.get("candle_open") == candle_open:
                existing_dir = existing_entry.get("direction", "")
                if existing_dir != direction:
                    return True
        return False

    def _can_send_by_small_changes(self, key: str, data: Optional[Dict]) -> bool:
        if data is None:
            return False
        entry = data.get("entry_price", 0) or data.get("entry", 0)
        quality = data.get("quality", 0) or data.get("quality_score", 0)
        prob = data.get("probability", 0)
        if isinstance(prob, dict):
            prob = prob.get("probability", 0) or prob.get("value", 0)

        old_entry = self._entry_price.get(key)
        old_quality = self._quality.get(key)
        old_prob = self._probability.get(key)
        old_setup = self._setup.get(key)

        if old_entry is not None and not _is_small_change(entry, old_entry, DUPLICATE_ENTRY_MAX_DIFF_PCT):
            return True
        if old_quality is not None and not _is_small_change(quality, old_quality, 2.0):
            return True
        if old_prob is not None and not _is_small_change(prob, old_prob, 2.0):
            return True
        # RFC V26.X: mesmo com preco/qualidade/probabilidade parecidos, um
        # setup estrutural diferente (novo BOS/CHoCH/Order Block/FVG desde
        # o ultimo envio) e um sinal genuinamente novo, nao um duplicado.
        if old_setup is not None and old_setup != _setup_fingerprint(data):
            return True
        return False

    def can_send(self, symbol: str, timeframe: str, direction: str, data: Optional[Dict] = None) -> bool:
        candle_open = _get_candle_open(timeframe)
        key = self._make_key(symbol, timeframe, direction, candle_open)

        if self._can_send_by_reversal(key, direction, candle_open):
            log.info(
                "[SIGNAL CACHE] %s %s %s — Reversao de direcao detectada. Permitindo novo envio.",
                symbol, timeframe, direction,
            )
            return True

        if not self._can_send_by_cache(key, data):
            if self._can_send_by_small_changes(key, data):
                log.info(
                    "[SIGNAL CACHE] %s %s %s — Alteracoes significativas detectadas. Permitindo novo envio.",
                    symbol, timeframe, direction,
                )
                return True
            self._duplicate_blocked_count += 1
            fp = compute_signal_fingerprint(
                symbol, timeframe, direction,
                (data or {}).get("entry_price", 0) or (data or {}).get("entry", 0),
                candle_open, data,
            )
            log.info(
                "[SIGNAL CACHE] DUPLICADO BLOQUEADO: %s %s %s | fingerprint=%s",
                symbol, timeframe, direction, fp,
            )
            return False

        return True

    def mark_sent(self, symbol: str, timeframe: str, direction: str, data: Optional[Dict] = None):
        candle_open = _get_candle_open(timeframe)
        key = self._make_key(symbol, timeframe, direction, candle_open)

        entry = (data or {}).get("entry_price", 0) or (data or {}).get("entry", 0)
        quality = (data or {}).get("quality", 0) or (data or {}).get("quality_score", 0)
        prob = (data or {}).get("probability", 0)
        if isinstance(prob, dict):
            prob = prob.get("probability", 0) or prob.get("value", 0)

        self._cache[key] = {
            "timestamp": time.time(),
            "candle_open": candle_open,
            "direction": direction,
        }
        self._entry_price[key] = entry
        self._quality[key] = quality
        self._probability[key] = prob
        self._direction[key] = direction
        self._setup[key] = _setup_fingerprint(data)

        self._cleanup()

    def mark_seen(self, symbol: str, timeframe: str, direction: str, data: Optional[Dict] = None):
        candle_open = _get_candle_open(timeframe)
        key = self._make_key(symbol, timeframe, direction, candle_open)

        if key not in self._cache:
            entry = (data or {}).get("entry_price", 0) or (data or {}).get("entry", 0)
            quality = (data or {}).get("quality", 0) or (data or {}).get("quality_score", 0)
            prob = (data or {}).get("probability", 0)
            if isinstance(prob, dict):
                prob = prob.get("probability", 0) or prob.get("value", 0)

            self._cache[key] = {
                "timestamp": time.time(),
                "candle_open": candle_open,
                "direction": direction,
            }
            self._entry_price[key] = entry
            self._quality[key] = quality
            self._probability[key] = prob
            self._direction[key] = direction
            self._setup[key] = _setup_fingerprint(data)

    def is_different_setup(self, symbol: str, timeframe: str, direction: str, entry_price: float) -> bool:
        base_key = f"{symbol.upper()}_{timeframe}_{direction.upper()}"
        for key in list(self._cache.keys()):
            if key.startswith(base_key):
                old_entry = self._entry_price.get(key)
                if old_entry is not None:
                    pct_diff = abs(entry_price - old_entry) / max(abs(old_entry), 0.000001) * 100
                    if pct_diff > 0.20:
                        return True
        return False

    def is_same_candle(self, timeframe: str) -> bool:
        candle_open = _get_candle_open(timeframe)
        for entry in self._cache.values():
            if entry.get("candle_open") == candle_open:
                return True
        return False

    def _cleanup(self, max_age: float = 172800):
        cutoff = time.time() - max_age
        keys_to_delete = [k for k, v in self._cache.items() if v["timestamp"] < cutoff]
        for k in keys_to_delete:
            del self._cache[k]
            self._entry_price.pop(k, None)
            self._quality.pop(k, None)
            self._probability.pop(k, None)
            self._direction.pop(k, None)
            self._setup.pop(k, None)
        if keys_to_delete:
            log.debug("[SIGNAL CACHE] Limpeza: %d entradas antigas removidas.", len(keys_to_delete))
