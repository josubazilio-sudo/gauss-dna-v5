from datetime import datetime
from typing import Any, Dict, Union


def _ensure_datetime(val: Any) -> Any:
    if val is None:
        return datetime.now()
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val)
        except (ValueError, TypeError):
            pass
    return val


def _ensure_enum(val: Any) -> Any:
    if isinstance(val, str):
        return _EnumCompat(val)
    return val


class _EnumCompat:
    def __init__(self, value: str):
        self.value = value

    def __str__(self) -> str:
        return self.value

    def upper(self) -> str:
        return self.value.upper()


class _AttrDict:
    def __init__(self, data: Union[Dict[str, Any], Any]):
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        if isinstance(self._data, dict):
            if name in self._data:
                val = self._data[name]
                return _wrap(val)
            return None
        return getattr(self._data, name)

    def __repr__(self):
        return repr(self._data)

    def __str__(self):
        return str(self._data)


def _wrap(val: Any) -> Any:
    if isinstance(val, dict):
        return _AttrDict(val)
    if isinstance(val, list):
        return [_wrap(v) for v in val]
    return val


def wrap_signal(signal: Any) -> Any:
    if isinstance(signal, dict):
        wrapped = _AttrDict(signal)
        wrapped._data["direction"] = _ensure_enum(signal.get("direction", "neutral"))
        wrapped._data["timestamp"] = _ensure_datetime(signal.get("timestamp"))
        wrapped._data.setdefault("setup", "N/A")
        wrapped._data.setdefault("context", "N/A")
        wrapped._data.setdefault("structure", {})
        wrapped._data.setdefault("approval_reasons", [])
        wrapped._data.setdefault("penalty_reasons", signal.get("penalty_reasons", []))
        wrapped._data.setdefault("pair", signal.get("ticker", signal.get("pair", "N/A")))
        wrapped._data.setdefault("ticker", signal.get("pair", signal.get("ticker", "N/A")))
        wrapped._data.setdefault("symbol", signal.get("symbol", signal.get("ticker", signal.get("pair", "N/A"))))
        wrapped._data.setdefault("quality", signal.get("quality_score", signal.get("quality", 0)))
        wrapped._data.setdefault("quality_score", signal.get("quality", signal.get("quality_score", 0)))
        wrapped._data.setdefault("institutional_score", signal.get("institutional_score", signal.get("score", 0)))
        wrapped._data.setdefault("timeframe", signal.get("timeframe", "N/A"))
        wrapped._data.setdefault("entry_price", signal.get("entry_price", 0))
        wrapped._data.setdefault("stop_loss", signal.get("stop_loss", 0))
        wrapped._data.setdefault("take_profit_1", signal.get("take_profit_1", 0))
        wrapped._data.setdefault("take_profit_2", signal.get("take_profit_2", 0))
        wrapped._data.setdefault("risk_reward", signal.get("risk_reward", 0))
        wrapped._data.setdefault("confidence", signal.get("confidence", 0))
        wrapped._data.setdefault("reason", signal.get("reason", signal.get("approval_reasons", [""])[0] if isinstance(signal.get("approval_reasons"), list) and signal.get("approval_reasons") else "N/A"))
        wrapped._data.setdefault("trend", signal.get("trend", ""))
        wrapped._data.setdefault("kalman_direction", signal.get("kalman_direction", "UNKNOWN"))
        wrapped._data.setdefault("kalman_confidence", signal.get("kalman_confidence", 0.0))
        wrapped._data.setdefault("kalman_trend_state", signal.get("kalman_trend_state", "ranging"))
        wrapped._data.setdefault("kalman_tendency", signal.get("kalman_tendency", 0.0))
        wrapped._data.setdefault("classification_label", signal.get("classification_label", "reprovado"))
        wrapped._data.setdefault("adx", signal.get("adx", signal.get("adx_value", 0.0)))
        wrapped._data.setdefault("rvol", signal.get("rvol", signal.get("rvol_value", 0.0)))
        wrapped._data.setdefault("atr_value", signal.get("atr_value", signal.get("atr", 0.0)))
        wrapped._data.setdefault("flow_score", signal.get("flow_score", 0.0))
        wrapped._data.setdefault("conviction_score", signal.get("conviction_score", 0.0))
        wrapped._data.setdefault("regime", signal.get("regime", "unknown"))
        wrapped._data.setdefault("entry_score", signal.get("entry_score", 0.0))
        wrapped._data.setdefault("consensus_score", signal.get("consensus_score", signal.get("consensus", 0.0)))
        wrapped._data.setdefault("signal_id", signal.get("signal_id", ""))
        wrapped._data.setdefault("trace_id", signal.get("trace_id", ""))
        wrapped._data.setdefault("overall_score", signal.get("overall_score", {}))
        wrapped._data.setdefault("overall_score_value", signal.get("overall_score_value", 0))
        wrapped._data.setdefault("overall_score_bar", signal.get("overall_score_bar", ""))
        wrapped._data.setdefault("overall_score_tier", signal.get("overall_score_tier", ""))
        wrapped._data.setdefault("conviction_level", signal.get("conviction_level", ""))
        wrapped._data.setdefault("expectancy_level", signal.get("expectancy_level", ""))
        wrapped._data.setdefault("time_to_tp1", signal.get("time_to_tp1", ""))
        wrapped._data.setdefault("liquidity_score", signal.get("liquidity_score", 0))
        wrapped._data.setdefault("structural_score", signal.get("structural_score", 0))
        wrapped._data.setdefault("consensus", signal.get("consensus", 0.0))
        wrapped._data.setdefault("audit", signal.get("audit", {}))
        wrapped._data.setdefault("cycle_id", signal.get("cycle_id", 0))
        wrapped._data.setdefault("engine_version", signal.get("engine_version", "V18.2"))
        return wrapped
    return signal
