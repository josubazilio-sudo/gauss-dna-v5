"""
K11 Signal Validator — RFC Sync
================================
Valida integridade e atualidade do sinal ANTES do envio ao Telegram.
Não altera Score, EQ, RVOL, RSI, MACD, BOS, EMA, setups ou thresholds.
Bloqueia apenas sinais com preço defasado ou geometria inválida.
"""

import time
import logging
import ccxt

logger = logging.getLogger(__name__)

# ── Exchange singleton (reutiliza conexão) ───────────────────────────────────
_exchange = None

def _get_exchange():
    global _exchange
    if _exchange is None:
        _exchange = ccxt.mexc({
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })
    return _exchange

# ── Configurações ────────────────────────────────────────────────────────────
# Máximo de candles de atraso permitidos por timeframe
TF_MAX_CANDLE_AGE_SEC = {
    "30m": 30 * 60 * 1.5,   # 45 min — 1.5 candles de margem
    "1h":  60 * 60 * 1.5,   # 90 min
    "4h":  4  * 60 * 60 * 1.5,
    "1d":  24 * 60 * 60 * 1.5,
}
DEFAULT_MAX_AGE_SEC = 60 * 60 * 2  # 2h fallback

# Distância máxima em múltiplos de ATR
MAX_DIST_ATR = 2.0   # bloqueia se |preco_atual - entrada| > 2 * ATR

# Fallback percentual se ATR não disponível (2%)
MAX_DIST_PCT_FALLBACK = 0.02

# ── Log de bloqueios ─────────────────────────────────────────────────────────
_BLOCK_LOG = "/root/gauss-dna-v5/k11-signal-bot/signal_validator.log"

def _log_block(symbol, tf, direcao, entrada, preco_atual, atr, dist_atr, candle_ts, reason, sinal):
    msg = (
        f"BLOCKED | {symbol} | {tf} | {direcao} | "
        f"ENTRY {entrada} | PRICE {preco_atual:.6g} | "
        f"DIST_ATR {dist_atr:.2f} | ATR {atr:.6g} | "
        f"CANDLE_TS {candle_ts} | "
        f"SCORE {sinal.get('score','?')} | EQ {sinal.get('entry_quality','?')} | "
        f"SETUP {sinal.get('setup_nome','?')} | "
        f"BLOCK: {reason}"
    )
    logger.warning(f"SIGNAL_VALIDATOR: {msg}")
    try:
        with open(_BLOCK_LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())} | {msg}\n")
    except Exception:
        pass


def _fetch_current_price(symbol: str) -> float | None:
    """Busca preço atual na exchange. Retorna None em caso de falha."""
    try:
        ticker = _get_exchange().fetch_ticker(symbol)
        return float(ticker["last"])
    except Exception as e:
        logger.warning(f"SIGNAL_VALIDATOR: fetch_ticker({symbol}) falhou — {e}")
        return None


def validar(sinal: dict) -> dict:
    """
    Recebe o dict de sinal do K10Engine e retorna:
      - o mesmo dict com "valido": True  → enviar
      - o mesmo dict com "valido": False + "block_reason" → bloquear

    Não toca em nenhum campo de estratégia.
    """
    symbol   = sinal.get("symbol", "?")
    tf       = sinal.get("timeframe", "30m")
    direcao  = sinal.get("direcao", "LONG")
    entrada  = sinal.get("entrada", 0)
    stop     = sinal.get("stop", 0)
    tp1      = sinal.get("tp1", 0)
    tp2      = sinal.get("tp2", 0)
    atr      = sinal.get("atr", 0)
    candle_ts = sinal.get("candle_ts")   # pode não existir ainda

    # ── 1. Buscar preço atual ────────────────────────────────────────────────
    preco_atual = _fetch_current_price(symbol)
    if preco_atual is None:
        reason = "PRICE_UNAVAILABLE"
        logger.warning(f"SIGNAL_VALIDATOR: {symbol} — sem preço atual, sinal bloqueado")
        sinal["valido"] = False
        sinal["block_reason"] = reason
        sinal["preco_no_envio"] = None
        return sinal

    sinal["preco_no_envio"] = preco_atual

    # ── 2. Validar staleness pelo timestamp do candle ────────────────────────
    if candle_ts is not None:
        try:
            candle_age_sec = time.time() - float(candle_ts)
            max_age = TF_MAX_CANDLE_AGE_SEC.get(tf, DEFAULT_MAX_AGE_SEC)
            if candle_age_sec > max_age:
                reason = f"STALE_SIGNAL (candle age {candle_age_sec/60:.0f}min > {max_age/60:.0f}min)"
                _log_block(symbol, tf, direcao, entrada, preco_atual, atr or 0, 0, candle_ts, reason, sinal)
                sinal["valido"] = False
                sinal["block_reason"] = reason
                return sinal
        except Exception:
            pass

    # ── 3. Validar distância entrada × preço atual (adaptativa por ATR) ──────
    if entrada and entrada > 0:
        dist_abs = abs(preco_atual - entrada)

        if atr and atr > 0:
            dist_atr = dist_abs / atr
            limite   = MAX_DIST_ATR
            bloqueado_dist = dist_atr > limite
            desc_dist = f"{dist_atr:.2f}x ATR"
        else:
            dist_pct  = dist_abs / entrada
            dist_atr  = 0
            limite    = MAX_DIST_PCT_FALLBACK
            bloqueado_dist = dist_pct > limite
            desc_dist = f"{dist_pct*100:.1f}%"

        if bloqueado_dist:
            reason = f"INVALID_ENTRY_DISTANCE ({desc_dist} > {limite}x ATR)"
            _log_block(symbol, tf, direcao, entrada, preco_atual, atr or 0, dist_atr, candle_ts or "?", reason, sinal)
            sinal["valido"] = False
            sinal["block_reason"] = reason
            return sinal

    # ── 4. Validar geometria TP/Stop ─────────────────────────────────────────
    geo_ok = True
    geo_reason = ""

    if direcao == "LONG":
        if stop >= entrada:
            geo_ok = False; geo_reason = f"INVALID_GEOMETRY: stop({stop}) >= entry({entrada})"
        elif tp1 <= entrada:
            geo_ok = False; geo_reason = f"INVALID_GEOMETRY: tp1({tp1}) <= entry({entrada})"
        elif tp2 <= entrada:
            geo_ok = False; geo_reason = f"INVALID_GEOMETRY: tp2({tp2}) <= entry({entrada})"
    elif direcao == "SHORT":
        if stop <= entrada:
            geo_ok = False; geo_reason = f"INVALID_GEOMETRY: stop({stop}) <= entry({entrada})"
        elif tp1 >= entrada:
            geo_ok = False; geo_reason = f"INVALID_GEOMETRY: tp1({tp1}) >= entry({entrada})"
        elif tp2 >= entrada:
            geo_ok = False; geo_reason = f"INVALID_GEOMETRY: tp2({tp2}) >= entry({entrada})"

    if not geo_ok:
        _log_block(symbol, tf, direcao, entrada, preco_atual, atr or 0, 0, candle_ts or "?", geo_reason, sinal)
        sinal["valido"] = False
        sinal["block_reason"] = geo_reason
        return sinal

    # ── Sinal válido ─────────────────────────────────────────────────────────
    sinal["valido"] = True
    sinal["block_reason"] = None
    logger.info(f"SIGNAL_VALIDATOR: {symbol} {tf} {direcao} OK | price={preco_atual:.6g} entry={entrada:.6g}")
    return sinal
