import json, logging, time
import numpy as np

logger = logging.getLogger(__name__)

TRADES_FILE = "/root/gauss-dna-v5/k11-signal-bot/k11_trades.json"
WATCHER_LOG = "/root/gauss-dna-v5/k11-signal-bot/structure_watcher.log"
MIN_CANDLES_WAIT = 1
MAX_WATCH_SEC = {"30m": 14400, "1h": 21600, "4h": 57600}
DEFAULT_MAX_WATCH = 21600

def _load_trades():
    try: return json.load(open(TRADES_FILE))
    except: return []

def _save_trades(trades):
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)

def _log(msg):
    logger.warning(f"STRUCTURE_WATCHER: {msg}")
    try:
        with open(WATCHER_LOG, "a") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()) + " | " + msg + "\n")
    except: pass

def _detectar_short(symbol, tf, exchange):
    try:
        import pandas as pd
        ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=100)
        if not ohlcv or len(ohlcv) < 20: return None
        df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","volume"])
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        c = float(closes[-2])
        atr = float(np.mean([highs[i]-lows[i] for i in range(-14,0)]))
        def ema(arr, n):
            k = 2/(n+1); e = arr[0]
            for x in arr[1:]: e = x*k + e*(1-k)
            return e
        e10 = ema(closes[-30:], 10)
        e21 = ema(closes[-50:], 21)
        ema12 = ema(closes[-50:], 12)
        ema26 = ema(closes[-100:], 26)
        macd = ema12 - ema26
        if not (e10 < e21 and c < e21 and macd < 0): return None
        stop = round(c + atr * 1.8, 8)
        tp1 = round(c - atr * 2.7, 8)
        tp2 = round(c - atr * 5.4, 8)
        return {"symbol":symbol,"direcao":"SHORT","timeframe":tf,
                "entrada":c,"stop":stop,"tp1":tp1,"tp2":tp2,
                "rr":3.0,"score":80,"tier":"PRATA",
                "setup_nome":"REVERSAO ESTRUTURAL","atr":atr,
                "confirmacoes":["Quebra de estrutura","EMA10<EMA21","MACD negativo"],
                "reversao_estrutural":True}
    except Exception as e:
        _log(f"Erro SHORT {symbol}: {e}")
        return None

def verificar_quebra_estrutura(exchange):
    sinais = []
    trades = _load_trades()
    agora = time.time()
    modificado = False
    for trade in trades:
        if trade.get("resultado") != "ABERTO": continue
        if trade.get("direcao","LONG") != "LONG": continue
        if trade.get("estrutura_invalidada"): continue
        symbol = trade.get("symbol","")
        tf = trade.get("timeframe","30m")
        entrada = float(trade.get("entrada",0))
        try:
            from datetime import datetime
            ts = datetime.fromisoformat(trade.get("ts","")).timestamp()
        except: ts = agora - 9999
        if agora - ts > MAX_WATCH_SEC.get(tf, DEFAULT_MAX_WATCH): continue
        tf_sec = {"30m":1800,"1h":3600,"4h":14400}.get(tf,3600)
        if agora - ts < tf_sec * MIN_CANDLES_WAIT: continue
        try:
            preco = float(exchange.fetch_ticker(symbol)["last"])
        except: continue
        stop = float(trade.get("stop", entrada*0.98))
        if preco >= stop: continue
        _log(f"QUEBRA | {symbol} {tf} entrada={entrada} preco={preco:.6g} stop={stop:.6g}")
        trade["estrutura_invalidada"] = True
        trade["resultado"] = "INVALIDADO"
        modificado = True
        short = _detectar_short(symbol, tf, exchange)
        if short:
            _log(f"SHORT REVERSAO | {symbol} entrada={short['entrada']:.6g}")
            sinais.append(short)
        else:
            sinais.append({"aviso_apenas":True,
                "msg":f"ESTRUTURA QUEBRADA\n{symbol} {tf} LONG\nEntrada:{entrada} Atual:{preco:.6g}\nSem condicao SHORT"})
    if modificado: _save_trades(trades)
    return sinais
