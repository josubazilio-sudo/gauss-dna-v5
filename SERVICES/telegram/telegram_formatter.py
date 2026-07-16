import logging
from typing import Any, Optional
from ENGINE.common.score_normalizer import scale_1_to_100
from ENGINE.common.operational import OperationalCalculator

log = logging.getLogger(__name__)

SEPARATOR = "\n" + "\u2501" * 20 + "\n"

DIRECTION_EMOJI = {
    "LONG": "\U0001f7e2 LONG",
    "BUY": "\U0001f7e2 LONG",
    "SHORT": "\U0001f534 SHORT",
    "SELL": "\U0001f534 SHORT",
}

REGIME_LABELS = {
    "strong_trend_up": "Tendencia Forte Alta",
    "strong_trend_down": "Tendencia Forte Baixa",
    "ranging": "Lateral",
    "compression": "Compressao",
    "exhaustion": "Exaustao",
}

SETUP_LABELS = {
    "trend_pullback": "Trend Pullback",
    "trend_breakout": "Trend Breakout",
    "trend_following": "Trend Following",
    "trend_continuation": "Trend Continuation",
    "pullback_short": "Pullback Short",
    "breakdown": "Breakdown",
    "range_reversal": "Range Reversal",
    "fade": "Fade",
    "reversal": "Reversao",
    "breakout": "Breakout",
    "mean_reversion": "Retorno a Media",
}

_MARKDOWN_SPECIAL_CHARS = ("_", "*", "`", "[")


def _escape_markdown(text: str) -> str:
    for ch in _MARKDOWN_SPECIAL_CHARS:
        text = text.replace(ch, "\\" + ch)
    return text


def _unwrap(obj: Any) -> Any:
    return getattr(obj, "_data", obj)


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        val = obj.get(key, default)
    else:
        val = getattr(obj, key, default)
    return default if val is None else val


def _str(obj: Any, key: str, default: str = "") -> str:
    val = _get(obj, key, default)
    return str(val) if val is not None else default


def _price(value: float) -> str:
    if value >= 1:
        return f"{value:.2f}"
    if value >= 0.01:
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return f"{value:.8f}".rstrip("0").rstrip(".")


class TelegramFormatter:

    @staticmethod
    def format_signal(signal: Any, message_type: str = "new", update_label: Optional[str] = None) -> str:
        symbol = _str(signal, "symbol", "???")
        timeframe = _str(signal, "timeframe", "---")
        direction = _str(signal, "direction", "NEUTRAL").upper()
        dir_emoji = DIRECTION_EMOJI.get(direction, direction)

        entry = float(_get(signal, "entry_price", 0.0))
        stop = float(_get(signal, "stop_loss", 0.0))
        tp1 = float(_get(signal, "take_profit_1", 0.0))
        rr = float(_get(signal, "risk_reward", 0.0))

        overall_value = float(_get(signal, "overall_score_value", 0))
        overall_tier = _str(signal, "overall_score_tier", "")
        is_elite = overall_value >= 80

        prob_data = _unwrap(_get(signal, "probability", {}))
        prob_value = float(_get(prob_data, "probability", 0)) if isinstance(prob_data, dict) else float(prob_data)

        confidence_raw = float(_get(signal, "confidence_score", _get(signal, "confidence", 0.0)))
        confidence_pct = scale_1_to_100(confidence_raw)

        risk_dec = _unwrap(_get(signal, "risk_decomposition", {}))
        risk_total = float(_get(risk_dec, "risco_total", 0)) if isinstance(risk_dec, dict) else 0

        sig_regime = _str(signal, "regime", "")
        sig_setup = _str(signal, "setup_type", "")

        bos = bool(_get(signal, "bos", 0))
        choch = bool(_get(signal, "choch", 0))
        fvg = bool(_get(signal, "fvg", 0))
        has_ob = bool(_get(signal, "selected_order_block", ""))
        kalman_dir = _str(signal, "kalman_direction", "")

        quantity = float(_get(signal, "quantity", 0.0))
        balance = float(_get(signal, "balance", 0.0))
        leverage = float(_get(signal, "leverage", 1.0))
        calc = OperationalCalculator()
        ops = calc.calculate(entry, stop, tp1, quantity, balance, leverage)

        main_reason = _str(signal, "main_reason", "")

        lines = []

        # HEADER
        if update_label:
            lines.append(f"\U0001f504 {update_label}")
        elif is_elite:
            lines.append("\U0001f451 ELITE SIGNAL")
        else:
            lines.append("\U0001f3c6 APROVADO")
        lines.append("")
        lines.append(f"*{symbol}*")
        lines.append(f"{dir_emoji} | {timeframe}")
        lines.append(SEPARATOR)

        # SCORE
        lines.append("\U0001f3af Score")
        lines.append(f"{overall_value:.1f}/100 \U0001f3c6")
        lines.append("")
        lines.append("\U0001f3b2 Probabilidade")
        lines.append(f"{prob_value:.0f}%")
        lines.append("")
        lines.append("\U0001f9e0 Confianca")
        lines.append(f"{confidence_pct:.0f}%")
        lines.append("")
        lines.append("\u26a0\ufe0f Risco")
        lines.append(f"{risk_total:.0f}/100")
        lines.append(SEPARATOR)

        # PRICES
        lines.append("\U0001f4b0 Entrada")
        lines.append(f"{_price(entry)}")
        lines.append("")
        lines.append("\U0001f3af Take Profit")
        lines.append(f"{_price(tp1)}")
        lines.append("")
        lines.append("\U0001f6d1 Stop Loss")
        lines.append(f"{_price(stop)}")
        lines.append("")
        lines.append("\u2696\ufe0f RR")
        lines.append(f"{rr:.2f}")
        lines.append(SEPARATOR)

        # CONTEXT
        lines.append("\U0001f9e0 Contexto")
        lines.append("")
        if sig_regime:
            regime_desc = REGIME_LABELS.get(sig_regime, sig_regime.title())
            lines.append("Regime")
            lines.append(f"{regime_desc}")
            lines.append("")
        if sig_setup:
            setup_desc = SETUP_LABELS.get(sig_setup, sig_setup.title())
            lines.append("Setup")
            lines.append(f"{setup_desc}")
        lines.append(SEPARATOR)

        # CONFLUENCES
        confl_lines = []
        if bos:
            confl_lines.append("\u2705 BOS")
        if choch:
            confl_lines.append("\u2705 CHoCH")
        if has_ob:
            confl_lines.append("\u2705 Order Block")
        if fvg:
            confl_lines.append("\u2705 Fair Value Gap")
        if kalman_dir and kalman_dir != "UNKNOWN":
            confl_lines.append(f"\u2705 Kalman {kalman_dir.upper()}")
        for cl in confl_lines:
            lines.append(cl)
        if confl_lines:
            lines.append(SEPARATOR)

        # OPERATION
        lines.append("\U0001f4b5 Operacao")
        lines.append("")
        lines.append("Capital")
        lines.append(f"{balance:.0f} USDT")
        lines.append("")
        lines.append("Alavancagem")
        lines.append(f"{leverage:.0f}x")
        lines.append("")
        lines.append("Lucro Estimado")
        lines.append(f"{ops['lucro_liquido_usdt']:.2f} USDT")
        lines.append("")
        lines.append("Perda Maxima")
        lines.append(f"{ops['perda_maxima_usdt']:.2f} USDT")
        lines.append(SEPARATOR)

        # MAIN REASON
        if main_reason:
            lines.append("\U0001f9e0 Motivo")
            lines.append("")
            lines.append(main_reason)
            lines.append(SEPARATOR)

        # STATUS
        lines.append("\U0001f7e2 STATUS")
        lines.append("")
        lines.append("ENTRADA LIBERADA")

        return "\n".join(lines)
