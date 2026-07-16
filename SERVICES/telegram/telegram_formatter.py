import logging
from typing import Any, Optional
from ENGINE.common.score_normalizer import scale_1_to_100
from ENGINE.common.operational import OperationalCalculator

log = logging.getLogger(__name__)

SEPARATOR = "\n" + "\u2501" * 30 + "\n"
SEPARATOR_SHORT = "\n" + "\u2501" * 15 + "\n"

TREND_LABELS = {
    "uptrend": "Alta",
    "downtrend": "Baixa",
    "ranging": "Lateral",
    "reversal": "Revers\u00e3o",
    "counter-uptrend": "Contra-Alta",
    "counter-downtrend": "Contra-Baixa",
}

DIRECTION_EMOJI = {
    "LONG": "\U0001f7e2 LONG",
    "BUY": "\U0001f7e2 LONG",
    "SHORT": "\U0001f534 SHORT",
    "SELL": "\U0001f534 SHORT",
}

_MARKDOWN_SPECIAL_CHARS = ("_", "*", "`", "[")


def _escape_markdown(text: str) -> str:
    for ch in _MARKDOWN_SPECIAL_CHARS:
        text = text.replace(ch, "\\" + ch)
    return text


def _unwrap(obj: Any) -> Any:
    """BUG FIX: SERVICES/telegram/signal_compat.py:_AttrDict.__getattr__
    embrulha automaticamente qualquer dict aninhado em outro _AttrDict.
    Isso quebra sistematicamente checagens `isinstance(x, dict)` feitas
    neste arquivo para campos aninhados (overall_score, probability,
    coherence_score, weighted_vote, risk_decomposition, coherence_audit)
    quando o sinal chega embrulhado — o valor nunca e reconhecido como
    dict, mesmo contendo os dados certos. Devolve sempre o dict cru por
    baixo do wrapper, se houver."""
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


def _pct(value: float) -> str:
    signal = "+" if value >= 0 else ""
    return f"{signal}{value:.2f}%"


def _usdt(value: float) -> str:
    signal = "+" if value >= 0 else ""
    return f"{signal}{value:.2f} USDT"


class TelegramFormatter:

    @staticmethod
    def format_signal(signal: Any, message_type: str = "new", update_label: Optional[str] = None) -> str:
        if update_label:
             header = f"\U0001f504 *{update_label}*"
        else:
             header = "\U0001f6a8 *NOVO SINAL*" if message_type == "new" else "\U0001f504 *ATUALIZA\u00c7\u00c3O*"

        symbol = _escape_markdown(_str(signal, "symbol", "???"))
        timeframe = _escape_markdown(_str(signal, "timeframe", "---"))
        direction = _str(signal, "direction", "NEUTRAL").upper()
        dir_emoji = DIRECTION_EMOJI.get(direction, direction)

        entry = float(_get(signal, "entry_price", 0.0))
        stop = float(_get(signal, "stop_loss", 0.0))
        tp1 = float(_get(signal, "take_profit_1", 0.0))
        rr = float(_get(signal, "risk_reward", 0.0))

        quality_raw = float(_get(signal, "quality_score", _get(signal, "quality", 0.0)))
        quality_pct = scale_1_to_100(quality_raw)

        confidence_raw = float(_get(signal, "confidence_score", _get(signal, "confidence", 0.0)))
        confidence_pct = scale_1_to_100(confidence_raw)

        consensus_raw = float(_get(signal, "consensus_score", _get(signal, "consensus", 0.0)))
        consensus_pct = scale_1_to_100(consensus_raw)

        trend = _str(signal, "trend", "")
        kalman_dir = _str(signal, "kalman_direction", "")

        adx_val = float(_get(signal, "adx", 0.0))
        rvol_val = float(_get(signal, "rvol", 0.0))
        atr_val = float(_get(signal, "atr_value", 0.0))
        flow_val = float(_get(signal, "flow_score", 0.0))

        overall = _unwrap(_get(signal, "overall_score", {}))
        if isinstance(overall, dict):
            overall_value = float(overall.get("overall_score", _get(signal, "overall_score_value", 0)))
            overall_bar = _str(overall, "overall_bar", _str(signal, "overall_score_bar", ""))
            overall_tier = _str(overall, "overall_tier", _str(signal, "overall_score_tier", ""))
            overall_emoji = _str(overall, "overall_tier_emoji", "")
        else:
            overall_value = float(_get(signal, "overall_score_value", 0))
            overall_bar = _str(signal, "overall_score_bar", "")
            overall_tier = _str(signal, "overall_score_tier", "")
            overall_emoji = ""

        conviction = _str(signal, "conviction_level", "")
        expectancy = _str(signal, "expectancy_level", "")
        time_to_tp1 = _str(signal, "time_to_tp1", "")

        structure_val = float(_get(signal, "structural_score", 0.0))
        liquidity_val = float(_get(signal, "liquidity_score", 0.0))
        flow_scaled = scale_1_to_100(flow_val)

        audit = _get(signal, "audit", {})
        audit_signal_id = _str(audit, "signal_id", _str(signal, "signal_id", "---"))
        audit_version = _str(audit, "engine_version", _str(signal, "engine_version", "V19.0"))
        audit_cycle = _get(audit, "cycle_id", _get(signal, "cycle_id", 0))
        audit_processing = float(_get(audit, "processing_time_ms", 0))
        audit_timestamp = _str(audit, "timestamp_utc", "")
        fingerprint = _get(signal, "fingerprint", {})
        fp_server = _str(fingerprint, "server", "")
        fp_pid = _get(fingerprint, "pid", "")
        fp_build = _str(fingerprint, "build", "")

        quantity = float(_get(signal, "quantity", 0.0))
        balance = float(_get(signal, "balance", 0.0))
        leverage = float(_get(signal, "leverage", 1.0))
        calc = OperationalCalculator()
        ops = calc.calculate(entry, stop, tp1, quantity, balance, leverage)

        lines = []

        # BLOCK 1: HEADER
        lines.append(header)
        lines.append(f"\U0001f48e *{symbol}* | {dir_emoji} | {timeframe}")
        if _get(signal, "_watchlist_priority", False):
            lines.append("\u2b50 *WATCHLIST PRIORIT\u00c1RIA*")
        lines.append(SEPARATOR)

        # RFC V18.5: REGIME E SETUP
        sig_regime = _str(signal, "regime", "")
        sig_setup = _str(signal, "setup_type", "")
        sig_strategy = _str(signal, "strategy_desc", "")
        sig_objective = _str(signal, "objective", "")
        sig_continuation = _str(signal, "continuation", "")

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
            "pullback_short": "Pullback Short",
            "breakdown": "Breakdown",
            "range_reversal": "Range Reversal",
            "fade": "Fade",
            "reversal": "Reversao",
            "breakout": "Breakout",
            "mean_reversion": "Retorno a Media",
        }

        if sig_regime:
            regime_desc = _escape_markdown(REGIME_LABELS.get(sig_regime, sig_regime.title()))
            lines.append(f"\U0001f9e0 *Regime*: {regime_desc}")
        if sig_setup:
            setup_desc = _escape_markdown(SETUP_LABELS.get(sig_setup, sig_setup.title()))
            lines.append(f"\U0001f3af *Setup*: {setup_desc}")
        if sig_strategy:
            lines.append(f"\U0001f4cc *Estrategia*: {_escape_markdown(sig_strategy)}")
        if sig_objective:
            lines.append(f"\U0001f3d7 *Objetivo*: {_escape_markdown(sig_objective)}")
        if sig_continuation:
            esaca = _escape_markdown(sig_continuation)
            lines.append(f"\U0001f4c8 *Continuacao*: {esaca}")

        # BLOCK 2: CLASSIFICACAO E QUALIDADE
        lines.append("\U0001f3af *Classifica\u00e7\u00e3o e Qualidade*")
        if overall_value > 0:
            tier_tag = overall_tier
            if overall_emoji:
                tier_tag = f"{overall_emoji} {overall_tier}"
            lines.append(f"`[ {overall_bar} ]`  {overall_value:.1f}/100  |  {tier_tag}")
        if quality_pct > 0:
            lines.append(f"\u2b50 Qualidade: {quality_pct:.1f}")
        lines.append(SEPARATOR)

        # BLOCK 3: CONVICCAO E EXPECTATIVA
        lines.append("\U0001f4aa *Convic\u00e7\u00e3o e Expectativa*")
        if conviction:
            lines.append(f"\U0001f9e0 Convic\u00e7\u00e3o: {conviction}")
        if expectancy:
            lines.append(f"\U0001f4c8 Expectativa: {expectancy}")
        # BUG FIX (RFC V20.2): lista de penalizacoes removida daqui \u2014
        # duplicava (e podia divergir de) `penalty_details` (Bloco
        # Analise), que e mais completa (gate + peso perdido + motivo).
        lines.append(SEPARATOR)

        # BLOCK 4: PRECOS
        lines.append("\U0001f4b0 *Entrada / TP / Stop*")
        if entry > 0:
            lines.append(f"Entrada: `${_price(entry)}`")
        if tp1 > 0:
            lines.append(f"TP: `${_price(tp1)}`")
        if stop > 0:
            lines.append(f"Stop: `${_price(stop)}`")
        if rr > 0:
            lines.append(f"RR: {rr:.2f}")
        lines.append(SEPARATOR)

        # BLOCK 5: OPERACIONAL
        lines.append("\U0001f4ca *Operacional*")
        if ops["retorno_ativo_pct"] > 0:
            lines.append(f"\U0001f4c8 Retorno do ativo: {_pct(ops['retorno_ativo_pct'])}")
        if ops["lucro_liquido_usdt"] > 0:
            lines.append(f"\U0001f4b0 Lucro l\u00edquido: {_usdt(ops['lucro_liquido_usdt'])}")
        if ops["perda_maxima_usdt"] > 0:
            lines.append(f"\U0001f6d1 Perda m\u00e1xima: {_usdt(-ops['perda_maxima_usdt'])}")
        if ops["quantidade"] > 0:
            lines.append(f"\U0001f4e6 Quantidade: {ops['quantidade']:.6f}")
        if ops["alavancagem_efetiva"] > 0:
            lines.append(f"\u2696\ufe0f Alavancagem: {ops['alavancagem_efetiva']:.1f}x")
        if ops["valor_nominal"] > 0:
            lines.append(f"\U0001f3e6 Valor nominal: {_usdt(ops['valor_nominal'])}")
        if ops["margem_utilizada_usdt"] > 0:
            lines.append(f"\U0001f3e6 Margem: {_usdt(ops['margem_utilizada_usdt'])}")
        if ops["retorno_margem_pct"] > 0:
            lines.append(f"\U0001f4c8 Sobre margem: {_pct(ops['retorno_margem_pct'])}")
        if ops["retorno_patrimonio_pct"] > 0:
            lines.append(f"\U0001f3e6 Sobre patrim\u00f4nio: {_pct(ops['retorno_patrimonio_pct'])}")
        lines.append(SEPARATOR)

        # V19.1: Confluência e Risco Decomposto
        confluence = float(_get(signal, "confluence_score", 0))
        risk_dec = _unwrap(_get(signal, "risk_decomposition", {}))
        main_reason = _str(signal, "main_reason", "")
        mtf_conflict = _get(signal, "mtf_conflict", False)

        # V18.4: Probabilidade, Coherence Score, Validação
        prob_data = _unwrap(_get(signal, "probability", {}))
        prob_value = float(_get(prob_data, "probability", 0)) if isinstance(prob_data, dict) else float(prob_data)
        prob_level = _str(prob_data, "level", "") if isinstance(prob_data, dict) else ""
        coherence = _unwrap(_get(signal, "coherence_audit", {}))
        coherence_score_data = _unwrap(_get(signal, "coherence_score", {}))
        cs_value = float(_get(coherence_score_data, "coherence_score", 0)) if isinstance(coherence_score_data, dict) else 0
        cs_level = _str(coherence_score_data, "coherence_level", "") if isinstance(coherence_score_data, dict) else ""
        weighted_vote = _unwrap(_get(signal, "weighted_vote", {}))
        wv_pct = float(_get(weighted_vote, "concordance_pct", 0)) if isinstance(weighted_vote, dict) else 0
        penalty_details = _get(signal, "penalty_details", [])
        validation_errors = _get(signal, "final_validation_errors", [])

        # BLOCK 6: ANALISE INSTITUCIONAL
        lines.append("\U0001f50d *An\u00e1lise*")
        if prob_value > 0:
            prob_line = f"\U0001f3b1 Probabilidade: {prob_value:.1f}"
            if prob_level:
                prob_line += f" ({prob_level})"
            lines.append(prob_line)
        if confidence_pct > 0:
            lines.append(f"\U0001f9e0 Confian\u00e7a: {confidence_pct:.1f}")
        if consensus_pct > 0:
            lines.append(f"\U0001f91d Consenso: {consensus_pct:.1f}")
        if confluence > 0:
            lines.append(f"\U0001f3af Conflu\u00eancia: {confluence:.1f}")
        # BUG FIX (RFC V20.2): classificacao removida daqui \u2014 o Bloco 2
        # ja exibe `overall_tier` (derivado do overall_score numerico).
        # Exibir `classification_label` (calculado independentemente
        # pelo Scanner) aqui causava o card mostrar duas classificacoes
        # divergentes para o mesmo sinal (ex.: "OURO" no cabecalho e
        # "PRATA" na analise) \u2014 ha uma unica fonte de verdade agora.
        if trend:
            trend_label = _escape_markdown(TREND_LABELS.get(trend.lower(), trend.title()))
            lines.append(f"\U0001f4c8 Tend\u00eancia: {trend_label}")
        if kalman_dir and kalman_dir != "UNKNOWN":
            lines.append(f"\U0001f52e Kalman: {_escape_markdown(kalman_dir.upper())}")
        if rvol_val > 0:
            lines.append(f"\U0001f4c8 RVOL: {rvol_val:.2f}x")
        if adx_val > 0:
            lines.append(f"\U0001f4ca ADX: {adx_val:.1f}")
        if atr_val > 0 and entry > 0:
            atr_pct = atr_val / entry * 100
            lines.append(f"\U0001f4c9 ATR: {atr_pct:.2f}%")
        if flow_scaled > 0:
            lines.append(f"\U0001f30a Fluxo: {flow_scaled:.1f}")
        if structure_val > 0:
            structure_pct = scale_1_to_100(structure_val)
            lines.append(f"\U0001f3d7 Estrutura: {structure_pct:.1f}")
        if liquidity_val > 0:
            liquidity_pct = scale_1_to_100(liquidity_val)
            lines.append(f"\U0001f4a7 Liquidez: {liquidity_pct:.1f}")
        if isinstance(risk_dec, dict) and risk_dec.get("risco_total", 0) > 0:
            lines.append(f"\u26a0\ufe0f Risco total: {risk_dec['risco_total']:.0f}/100")
        if mtf_conflict:
            lines.append(f"\u26d4 Conflito Direcional entre Timeframes detectado!")
        if cs_value > 0:
            cs_emoji = "\U0001f9e0" if cs_value >= 85 else "\u26a0\ufe0f" if cs_value >= 60 else "\u274c"
            cs_line = f"{cs_emoji} Coer\u00eancia: {cs_value:.0f}/100"
            if cs_level:
                cs_line += f" ({cs_level})"
            lines.append(cs_line)
        if isinstance(coherence, dict) and coherence.get("modulos"):
            mods = coherence["modulos"]
            incoerentes = [k.upper() for k, v in mods.items() if v != "OK"]
            if incoerentes:
                lines.append(f"\u26a0\ufe0f Coer\u00eancia: {', '.join(incoerentes[:4])}")
            else:
                lines.append("\u2705 Coer\u00eancia institucional OK")
        if wv_pct > 0 and wv_pct < 100:
            lines.append(f"\U0001f5f3 Vota\u00e7\u00e3o: {wv_pct:.0f}% concord\u00e2ncia")
        if penalty_details and isinstance(penalty_details, list):
            for pd in penalty_details[:3]:
                gate = pd.get("gate", "")
                peso = pd.get("peso_perdido", 0)
                lines.append(f"\u26a0\ufe0f {gate}: -{peso}")
        if validation_errors:
            for e in validation_errors[:2]:
                lines.append(f"\u274c {_escape_markdown(e)}")
        # RFC V18.5: Motivo do sinal
        approval = _get(signal, "approval_reasons", [])
        if approval and isinstance(approval, list):
            lines.append("\U0001f9e0 *Motivo do sinal*")
            for reason in approval[:6]:
                lines.append(f"\u2022 {_escape_markdown(reason)}")
        if main_reason:
            lines.append(f"\U0001f4a1 {_escape_markdown(main_reason)}")
        lines.append(SEPARATOR)

        # BLOCK 7: AUDITORIA
        lines.append("\U0001f50d *Auditoria*")
        lines.append(f"Signal ID: `{audit_signal_id}`")
        lines.append(f"Vers\u00e3o: {audit_version}")
        if audit_cycle:
            lines.append(f"Ciclo: #{audit_cycle}")
        if audit_processing > 0:
            lines.append(f"Processamento: {audit_processing:.1f}ms")
        if audit_timestamp:
            lines.append(f"UTC: {audit_timestamp}")
        # RFC V25.3 (temporario): fingerprint de instancia para rastrear a
        # origem do sinal — remover ou mover so para o log apos a auditoria.
        if fp_server:
            lines.append(f"Servidor: {fp_server}")
        if fp_pid:
            lines.append(f"PID: {fp_pid}")
        if fp_build:
            lines.append(f"Build: {fp_build}")

        return "\n".join(lines)
