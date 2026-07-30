"""
K10 Institucional Engine — v2.0
Indicadores: EMA10/21/50/200, ADX, RSI Adaptativo, ATR, RVOL, MACD,
             VWAP, Bollinger, Volume, BOS, CHoCH, FVG, Order Block, Liquidez
Timeframes: 30m (operacional) | 1h (confirmação) | 4h (tendência) | 1D (macro)
"""

import ccxt
import pandas as pd
import numpy as np
from config import BANCA, RISCO_PCT, ALAVANCAGEM_POR_REGIME


class K10Engine:
    def __init__(self):
        self.exchange = ccxt.binance({"enableRateLimit": True})

    # ─────────────────────────────────────────────────────────────────────────
    # DADOS
    # ─────────────────────────────────────────────────────────────────────────
    def _fetch(self, symbol: str, tf: str, limit: int = 300) -> pd.DataFrame:
        try:
            raw = self.exchange.fetch_ohlcv(symbol, tf, limit=limit)
            df = pd.DataFrame(raw, columns=["ts","open","high","low","close","volume"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            return df
        except Exception as e:
            raise RuntimeError(f"Erro {symbol} {tf}: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # INDICADORES
    # ─────────────────────────────────────────────────────────────────────────
    def _calc(self, df: pd.DataFrame) -> pd.DataFrame:
        c, h, l, v = df["close"], df["high"], df["low"], df["volume"]

        # EMAs
        for p in [10, 21, 50, 200]:
            df[f"ema{p}"] = c.ewm(span=p, adjust=False).mean()

        # VWAP
        df["vwap"] = (v * (h + l + c) / 3).cumsum() / v.cumsum()

        # ATR 14
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        df["atr"] = tr.ewm(span=14, adjust=False).mean()

        # ADX 14
        dm_p = (h.diff()).clip(lower=0).where(h.diff() > (-l.diff()), 0.0)
        dm_n = (-l.diff()).clip(lower=0).where((-l.diff()) > h.diff(), 0.0)
        atr14 = tr.ewm(span=14, adjust=False).mean()
        di_p = 100 * dm_p.ewm(span=14, adjust=False).mean() / atr14
        di_n = 100 * dm_n.ewm(span=14, adjust=False).mean() / atr14
        dx = (100 * (di_p - di_n).abs() / (di_p + di_n).replace(0, np.nan))
        df["adx"] = dx.ewm(span=14, adjust=False).mean()
        df["di_p"] = di_p
        df["di_n"] = di_n

        # RSI 14
        delta = c.diff()
        gain = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
        df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

        # MACD 12/26/9
        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        df["macd"]        = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"]   = df["macd"] - df["macd_signal"]

        # Bollinger 20 / desvio 2
        sma20 = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        df["bb_upper"] = sma20 + 2 * std20
        df["bb_lower"] = sma20 - 2 * std20
        df["bb_mid"]   = sma20
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma20

        # RVOL 20
        df["vol_ma"] = v.rolling(20).mean()
        df["rvol"]   = v / df["vol_ma"]

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # REGIME DE MERCADO
    # ─────────────────────────────────────────────────────────────────────────
    def _regime(self, df: pd.DataFrame) -> str:
        r = df.iloc[-1]
        adx      = r["adx"]
        bb_width = r["bb_width"]
        bb_prev  = df["bb_width"].iloc[-5]

        if adx > 25:
            if r["ema10"] > r["ema21"] > r["ema50"] > r["ema200"]:
                return "Bull Trend"
            elif r["ema10"] < r["ema21"] < r["ema50"] < r["ema200"]:
                return "Bear Trend"
            else:
                return "Transição"
        elif adx < 18:
            if bb_width < bb_prev * 0.8:
                return "Compressão"   # Bollinger comprimindo → breakout iminente
            return "Range"
        else:
            return "Transição"

    def _setup_para_regime(self, regime: str) -> str:
        return {
            "Bull Trend":  "TREND FOLLOWING",
            "Bear Trend":  "TREND FOLLOWING",
            "Compressão":  "BREAKOUT",
            "Transição":   "REVERSÃO INSTITUCIONAL",
            "Range":       "SCALPING ADAPTATIVO",
        }.get(regime, "SCALPING ADAPTATIVO")

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRUTURA: BOS / CHoCH / FVG / Order Block / Liquidez
    # ─────────────────────────────────────────────────────────────────────────
    def _bos(self, df: pd.DataFrame, direcao: str) -> bool:
        highs = df["high"].rolling(10).max()
        lows  = df["low"].rolling(10).min()
        if direcao == "LONG":
            return df["close"].iloc[-1] > highs.iloc[-5]
        return df["close"].iloc[-1] < lows.iloc[-5]

    def _choch(self, df: pd.DataFrame) -> bool:
        """Mudança de estrutura: swing anterior quebrado na direção oposta"""
        h = df["high"]
        l = df["low"]
        prev_high = h.iloc[-10:-1].max()
        prev_low  = l.iloc[-10:-1].min()
        c = df["close"].iloc[-1]
        return c > prev_high or c < prev_low

    def _fvg(self, df: pd.DataFrame, direcao: str) -> bool:
        """Fair Value Gap: gap entre candle[-3] e candle[-1]"""
        if len(df) < 4:
            return False
        c1_high = df["high"].iloc[-3]
        c1_low  = df["low"].iloc[-3]
        c3_high = df["high"].iloc[-1]
        c3_low  = df["low"].iloc[-1]
        if direcao == "LONG":
            return c3_low > c1_high   # gap bullish
        return c3_high < c1_low       # gap bearish

    def _order_block(self, df: pd.DataFrame, direcao: str) -> bool:
        """Último candle forte antes de movimento impulsivo"""
        closes = df["close"]
        opens  = df["open"]
        vols   = df["volume"]
        vol_ma = df["vol_ma"]
        for i in range(-5, -1):
            candle_forte = abs(closes.iloc[i] - opens.iloc[i]) > df["atr"].iloc[i] * 0.8
            vol_inst     = vols.iloc[i] > vol_ma.iloc[i] * 1.3
            if candle_forte and vol_inst:
                if direcao == "LONG" and closes.iloc[i] > opens.iloc[i]:
                    return True
                if direcao == "SHORT" and closes.iloc[i] < opens.iloc[i]:
                    return True
        return False

    def _liquidez_capturada(self, df: pd.DataFrame, direcao: str) -> bool:
        """Sweep de topo/fundo antes da entrada"""
        highs = df["high"]
        lows  = df["low"]
        eq_high = highs.iloc[-20:-1].max()
        eq_low  = lows.iloc[-20:-1].min()
        last_h  = highs.iloc[-1]
        last_l  = lows.iloc[-1]
        last_c  = df["close"].iloc[-1]
        if direcao == "LONG":
            # Sweep de fundo: low rompeu mínima e fechou acima
            return last_l < eq_low and last_c > eq_low
        else:
            # Sweep de topo: high rompeu máxima e fechou abaixo
            return last_h > eq_high and last_c < eq_high

    # ─────────────────────────────────────────────────────────────────────────
    # CONFIRMAÇÃO MULTI-TIMEFRAME
    # ─────────────────────────────────────────────────────────────────────────
    def _tendencia_tf(self, df: pd.DataFrame) -> str:
        r = df.iloc[-1]
        if r["ema21"] > r["ema50"]:
            return "ALTA"
        elif r["ema21"] < r["ema50"]:
            return "BAIXA"
        return "NEUTRA"

    def _mtf_ok(self, direcao: str, tend_4h: str, tend_1d: str) -> tuple:
        """Nunca operar contra H4 e D1"""
        if direcao == "LONG":
            ok = tend_4h != "BAIXA" and tend_1d != "BAIXA"
        else:
            ok = tend_4h != "ALTA" and tend_1d != "ALTA"
        motivo = ""
        if not ok:
            motivo = f"Contra tendência H4={tend_4h} D1={tend_1d}"
        return ok, motivo

    # ─────────────────────────────────────────────────────────────────────────
    # FILTROS DE INDICADORES
    # ─────────────────────────────────────────────────────────────────────────
    def _emas_alinhadas(self, df: pd.DataFrame, direcao: str) -> tuple:
        r = df.iloc[-1]
        if direcao == "LONG":
            ok = r["ema10"] > r["ema21"] > r["ema50"] > r["ema200"]
            motivo = "" if ok else f"EMAs desalinhadas para LONG (EMA10={r['ema10']:.2f} EMA21={r['ema21']:.2f} EMA50={r['ema50']:.2f})"
        else:
            ok = r["ema10"] < r["ema21"] < r["ema50"] < r["ema200"]
            motivo = "" if ok else f"EMAs desalinhadas para SHORT"
        return ok, motivo

    def _adx_ok(self, df: pd.DataFrame) -> tuple:
        adx = df["adx"].iloc[-1]
        ok  = adx >= 18
        motivo = "" if ok else f"ADX {adx:.1f} < 18 (mercado lateral)"
        return ok, motivo, adx

    def _rsi_adaptativo(self, df: pd.DataFrame, direcao: str, regime: str) -> tuple:
        rsi = df["rsi"].iloc[-1]
        if direcao == "LONG":
            # Mercado de alta: comprar quando RSI volta de 30–45
            if regime in ("Bull Trend", "Transição"):
                ok = 30 <= rsi <= 55
            else:
                ok = rsi <= 55
            # Nunca comprar acima de 75
            if rsi > 75:
                return False, f"RSI {rsi:.1f} > 75 — sobrecomprado, evitar LONG", rsi
        else:
            # Mercado de baixa: vender quando RSI volta de 55–70
            if regime in ("Bear Trend", "Transição"):
                ok = 45 <= rsi <= 70
            else:
                ok = rsi >= 45
            # Nunca vender abaixo de 25
            if rsi < 25:
                return False, f"RSI {rsi:.1f} < 25 — sobrevendido, evitar SHORT", rsi
        motivo = "" if ok else f"RSI {rsi:.1f} fora da zona ideal para {direcao}"
        return ok, motivo, rsi

    def _macd_ok(self, df: pd.DataFrame, direcao: str) -> tuple:
        hist      = df["macd_hist"].iloc[-1]
        hist_prev = df["macd_hist"].iloc[-2]
        macd      = df["macd"].iloc[-1]
        signal    = df["macd_signal"].iloc[-1]
        if direcao == "LONG":
            ok = (macd > signal) or (hist > hist_prev and hist > 0) or (hist > hist_prev and hist_prev < 0)
        else:
            ok = (macd < signal) or (hist < hist_prev and hist < 0) or (hist < hist_prev and hist_prev > 0)
        motivo = "" if ok else f"MACD desfavorável para {direcao}"
        return ok, motivo

    def _vwap_ok(self, df: pd.DataFrame, direcao: str) -> tuple:
        c    = df["close"].iloc[-1]
        vwap = df["vwap"].iloc[-1]
        if direcao == "LONG":
            ok = c > vwap
            motivo = "" if ok else f"Preço {c:.4f} abaixo do VWAP {vwap:.4f} — somente SHORT"
        else:
            ok = c < vwap
            motivo = "" if ok else f"Preço {c:.4f} acima do VWAP {vwap:.4f} — somente LONG"
        return ok, motivo

    def _rvol_ok(self, df: pd.DataFrame) -> tuple:
        rvol = df["rvol"].iloc[-1]
        ok   = rvol >= 1.20
        motivo = "" if ok else f"RVOL {rvol:.2f} < 1.20 (volume insuficiente)"
        return ok, motivo, rvol

    def _bollinger_ok(self, df: pd.DataFrame, direcao: str, setup: str) -> tuple:
        r = df.iloc[-1]
        c = r["close"]
        if setup == "BREAKOUT":
            # Compressão das bandas = setup ideal
            comprimido = r["bb_width"] < df["bb_width"].rolling(20).mean().iloc[-1] * 0.8
            ok = comprimido
            motivo = "" if ok else "Bollinger não comprimido para Breakout"
        elif setup == "SCALPING ADAPTATIVO":
            # Operar nas bordas das bandas
            if direcao == "LONG":
                ok = c <= r["bb_lower"] * 1.005
                motivo = "" if ok else "Preço não na banda inferior (Scalping)"
            else:
                ok = c >= r["bb_upper"] * 0.995
                motivo = "" if ok else "Preço não na banda superior (Scalping)"
        else:
            # Trend: evitar entrar com preço na banda oposta
            if direcao == "LONG":
                ok = c < r["bb_upper"] * 0.99
                motivo = "" if ok else "Preço na banda superior — exaustão possível"
            else:
                ok = c > r["bb_lower"] * 1.01
                motivo = "" if ok else "Preço na banda inferior — exaustão possível"
        return ok, motivo

    # ─────────────────────────────────────────────────────────────────────────
    # SCORE
    # ─────────────────────────────────────────────────────────────────────────
    def _calcular_score(self, checks: list) -> int:
        """Cada item da lista é (ok: bool, peso: int)"""
        total_peso = sum(p for _, p in checks)
        total_ok   = sum(p for ok, p in checks if ok)
        return round(total_ok / total_peso * 100) if total_peso else 0

    def _convicção(self, score: int) -> str:
        if score >= 90: return "ELITE 🔥"
        if score >= 80: return "ALTA ✅"
        if score >= 70: return "BOA ⚡"
        return "BAIXA ❌"

    # ─────────────────────────────────────────────────────────────────────────
    # GESTÃO DE BANCA
    # ─────────────────────────────────────────────────────────────────────────
    def _gestao_banca(self, regime: str, entrada: float, stop: float, atr: float) -> dict:
        # Alavancagem inversamente proporcional ao ATR
        base = ALAVANCAGEM_POR_REGIME.get(regime, 10)
        atr_medio = atr  # referência
        # Se ATR alto, reduz alavancagem até mínimo 8x
        fator_atr = max(0.5, min(1.0, 0.002 / atr if atr > 0 else 1.0))
        alavancagem = max(8, min(25, round(base * fator_atr)))

        risco_usdt     = round(BANCA * RISCO_PCT / 100, 2)
        dist_stop_pct  = abs(entrada - stop) / entrada if entrada else 0.01
        posicao        = round(min(risco_usdt / dist_stop_pct, BANCA * alavancagem), 2) if dist_stop_pct > 0 else 0
        capital        = round(posicao / alavancagem, 2)
        ganho_tp1      = round(risco_usdt * 2, 2)

        return {
            "alavancagem": alavancagem,
            "capital": capital,
            "posicao": posicao,
            "risco_usdt": risco_usdt,
            "ganho_tp1": ganho_tp1,
            "banca": BANCA,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # ANÁLISE PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────
    def analisar(self, symbol: str) -> dict:
        try:
            df30 = self._calc(self._fetch(symbol, "30m"))
            df1h = self._calc(self._fetch(symbol, "1h",  limit=200))
            df4h = self._calc(self._fetch(symbol, "4h",  limit=200))
            df1d = self._calc(self._fetch(symbol, "1d",  limit=200))
        except Exception as e:
            return {"symbol": symbol, "aprovado": False, "setup_nome": "—",
                    "regime": "Erro", "score": 0, "motivos_rejeicao": [str(e)],
                    "o_que_falta": [], "setup_alternativo": "—"}

        regime  = self._regime(df30)
        setup   = self._setup_para_regime(regime)
        r30     = df30.iloc[-1]

        # Direção baseada nas EMAs do 30m
        if r30["ema10"] > r30["ema21"]:
            direcao = "LONG"
        else:
            direcao = "SHORT"

        # ── Multi-timeframe ───────────────────────────────────────────────────
        tend_4h = self._tendencia_tf(df4h)
        tend_1d = self._tendencia_tf(df1d)
        mtf_ok, mtf_motivo = self._mtf_ok(direcao, tend_4h, tend_1d)

        # ── Todos os filtros ──────────────────────────────────────────────────
        emas_ok,  emas_motivo          = self._emas_alinhadas(df30, direcao)
        adx_ok,   adx_motivo,  adx_v  = self._adx_ok(df30)
        rsi_ok,   rsi_motivo,  rsi_v  = self._rsi_adaptativo(df30, direcao, regime)
        macd_ok,  macd_motivo          = self._macd_ok(df30, direcao)
        vwap_ok,  vwap_motivo          = self._vwap_ok(df30, direcao)
        rvol_ok,  rvol_motivo, rvol_v  = self._rvol_ok(df30)
        boll_ok,  boll_motivo          = self._bollinger_ok(df30, direcao, setup)
        bos_ok                         = self._bos(df30, direcao)
        liq_ok                         = self._liquidez_capturada(df30, direcao)
        ob_ok                          = self._order_block(df30, direcao)

        # ── Níveis ────────────────────────────────────────────────────────────
        c   = r30["close"]
        atr = r30["atr"]
        if direcao == "LONG":
            entrada = round(c, 4)
            stop    = round(c - atr * 1.5, 4)
            tp1     = round(c + atr * 2.0, 4)
            tp2     = round(c + atr * 3.5, 4)
        else:
            entrada = round(c, 4)
            stop    = round(c + atr * 1.5, 4)
            tp1     = round(c - atr * 2.0, 4)
            tp2     = round(c - atr * 3.5, 4)

        rr = round(abs(tp1 - entrada) / abs(stop - entrada), 2) if stop != entrada else 0

        # ── Score (pesos por importância) ─────────────────────────────────────
        checks = [
            (mtf_ok,   20),  # nunca operar contra H4/D1
            (emas_ok,  15),  # EMAs alinhadas
            (adx_ok,   10),  # ADX ≥ 18
            (rvol_ok,  10),  # RVOL ≥ 1.20
            (bos_ok,   10),  # BOS
            (liq_ok,    8),  # liquidez capturada
            (ob_ok,     8),  # order block
            (macd_ok,   7),  # MACD
            (rsi_ok,    5),  # RSI adaptativo
            (vwap_ok,   4),  # VWAP
            (boll_ok,   3),  # Bollinger
        ]
        score = self._calcular_score(checks)
        rr_ok = rr >= 2.0

        # ── Confirmações aprovadas ────────────────────────────────────────────
        nomes = ["MTF H4/D1","EMAs alinhadas","ADX","RVOL","BOS","Liquidez",
                 "Order Block","MACD","RSI","VWAP","Bollinger"]
        confirmacoes = [n for n, (ok, _) in zip(nomes, checks) if ok]

        # ── Falhas ────────────────────────────────────────────────────────────
        motivos = []
        falta   = []
        for motivo in [mtf_motivo, emas_motivo, adx_motivo, rsi_motivo,
                       macd_motivo, vwap_motivo, rvol_motivo, boll_motivo]:
            if motivo:
                motivos.append(motivo)
        if not bos_ok:
            motivos.append("BOS não confirmado")
            falta.append("Break of Structure no 30m")
        if not liq_ok:
            motivos.append("Liquidez não capturada")
            falta.append("Sweep de topo/fundo antes da entrada")
        if not ob_ok:
            motivos.append("Sem Order Block institucional")
            falta.append("Order Block com volume institucional")
        if not rr_ok:
            motivos.append(f"RR {rr} < 2.0")
            falta.append("RR mínimo 1:2")
        if score < 70:
            motivos.append(f"Score {score} < 70 (mínimo exigido)")
            falta.append("Score ≥ 70 para aprovação")

        aprovado = (len(motivos) == 0 and score >= 70 and rr_ok)

        gb = self._gestao_banca(regime, entrada, stop, atr)

        return {
            "symbol":          symbol,
            "aprovado":        aprovado,
            "setup_nome":      setup,
            "regime":          regime,
            "direcao":         direcao,
            "score":           score,
            "convicção":       self._convicção(score),
            "entrada":         entrada,
            "stop":            stop,
            "tp1":             tp1,
            "tp2":             tp2,
            "rr":              rr,
            "adx":             adx_v,
            "rsi":             rsi_v,
            "atr":             atr,
            "rvol":            rvol_v,
            "volume_status":   f"RVOL {rvol_v:.2f}",
            "confirmacoes":    confirmacoes,
            "motivos_rejeicao": motivos,
            "o_que_falta":     falta,
            "setup_alternativo": "—",
            "tend_4h":         tend_4h,
            "tend_1d":         tend_1d,
            "timeframe":       "30m",
            "preco_atual":     c,
            **gb,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # REGIME RÁPIDO (para /regime)
    # ─────────────────────────────────────────────────────────────────────────
    def obter_regime(self, symbol: str) -> dict:
        df30 = self._calc(self._fetch(symbol, "30m"))
        df4h = self._calc(self._fetch(symbol, "4h", limit=100))
        df1d = self._calc(self._fetch(symbol, "1d", limit=100))
        regime = self._regime(df30)
        r = df30.iloc[-1]
        return {
            "regime":            regime,
            "adx":               r["adx"],
            "atr":               r["atr"],
            "tendencia_4h":      self._tendencia_tf(df4h),
            "tendencia_1d":      self._tendencia_tf(df1d),
            "setup_recomendado": self._setup_para_regime(regime),
        }
