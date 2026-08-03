"""
K10 Engine V11 — RFC V11: Entrada no Início do Movimento
Gates: Exaustão | Entrada Precoce | Distância | Volume | Tendência | Momentum
Timeframes: 30m | 1h | 4h | 1D
"""

import ccxt
import pandas as pd
import numpy as np
from config import BANCA, RISCO_PCT, ALAVANCAGEM_POR_REGIME
from scoring import calcular_score, TIER_EMOJI, TIER_RANK


class K10Engine:
    def __init__(self):
        self.exchange = ccxt.mexc({"enableRateLimit": True, "options": {"defaultType": "swap"}})

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

        for p in [10, 21, 50, 200]:
            df[f"ema{p}"] = c.ewm(span=p, adjust=False).mean()

        df["vwap"] = (v * (h + l + c) / 3).cumsum() / v.cumsum()

        tr = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()], axis=1).max(axis=1)
        df["atr"] = tr.ewm(span=14, adjust=False).mean()

        dm_p = (h.diff()).clip(lower=0).where(h.diff()>(-l.diff()), 0.0)
        dm_n = (-l.diff()).clip(lower=0).where((-l.diff())>h.diff(), 0.0)
        atr14 = tr.ewm(span=14, adjust=False).mean()
        di_p  = 100 * dm_p.ewm(span=14, adjust=False).mean() / atr14
        di_n  = 100 * dm_n.ewm(span=14, adjust=False).mean() / atr14
        dx    = 100*(di_p-di_n).abs()/(di_p+di_n).replace(0,np.nan)
        df["adx"]  = dx.ewm(span=14, adjust=False).mean()
        df["di_p"] = di_p
        df["di_n"] = di_n

        delta = c.diff()
        gain  = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
        df["rsi"] = 100 - 100/(1 + gain/loss.replace(0,np.nan))

        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        df["macd"]        = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"]   = df["macd"] - df["macd_signal"]

        sma20 = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        df["bb_upper"] = sma20 + 2*std20
        df["bb_lower"] = sma20 - 2*std20
        df["bb_mid"]   = sma20
        df["bb_width"] = (df["bb_upper"]-df["bb_lower"])/sma20

        df["vol_ma"] = v.rolling(20).mean()
        df["rvol"]   = v / df["vol_ma"]

        # Chande Momentum Oscillator (CMO)
        diff = c.diff()
        up   = diff.clip(lower=0).rolling(14).sum()
        dn   = (-diff.clip(upper=0)).rolling(14).sum()
        df["cmo"] = 100 * (up - dn) / (up + dn).replace(0, np.nan)

        # StochRSI
        rsi_series = df["rsi"]
        rsi_min = rsi_series.rolling(14).min()
        rsi_max = rsi_series.rolling(14).max()
        df["stoch_rsi"] = (rsi_series - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan)

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # RFC V11 — GATE 1: EXAUSTÃO
    # ─────────────────────────────────────────────────────────────────────────
    def _gate_exaustao(self, df: pd.DataFrame, direcao: str) -> tuple[bool, str]:
        r   = df.iloc[-1]
        rsi = float(r["rsi"])
        cmo      = float(r["cmo"])      if not np.isnan(r["cmo"])      else 0.0
        stoch_rsi = float(r["stoch_rsi"]) if not np.isnan(r["stoch_rsi"]) else 0.5
        c   = float(r["close"])
        atr = float(r["atr"])
        e21 = float(r["ema21"])

        dist_ema21 = abs(c - e21) / atr if atr > 0 else 0

        # Candles consecutivos na mesma direção
        ultimos = df["close"].iloc[-5:].values
        candles_alta  = sum(1 for i in range(1, len(ultimos)) if ultimos[i] > ultimos[i-1])
        candles_baixa = sum(1 for i in range(1, len(ultimos)) if ultimos[i] < ultimos[i-1])

        # Movimento consumido: quanto o preço já andou desde a última reversão
        high_recente = float(df["high"].iloc[-30:].max())
        low_recente  = float(df["low"].iloc[-30:].min())
        range_total  = high_recente - low_recente
        if range_total > 0 and atr > 0:
            if direcao == "LONG":
                movimento_consumido = (c - low_recente) / range_total  # 0=fundo, 1=topo
            else:
                movimento_consumido = (high_recente - c) / range_total  # 0=topo, 1=fundo
        else:
            movimento_consumido = 0.5

        if direcao == "LONG":
            if rsi > 72:
                return False, f"Exaustão: RSI {rsi:.1f} > 72"
            if c > float(r["bb_upper"]):
                return False, "Exaustão: Preço acima da Banda Superior"
            if dist_ema21 > 1.5:
                return False, f"Exaustão: Distância EMA21 = {dist_ema21:.2f} ATR > 1.5"
            if candles_alta >= 3:
                return False, f"Exaustão: {candles_alta} candles consecutivos de alta"
            if cmo > 70:
                return False, f"Exaustão: CMO {cmo:.1f} > 70"
            if movimento_consumido > 0.85:
                return False, f"Movimento consumido: preço já está {movimento_consumido*100:.0f}% do range — compra no topo"
            if stoch_rsi > 0.95:
                return False, f"StochRSI {stoch_rsi*100:.0f}% — sobrecomprado extremo, aguardar pullback"
        else:
            if rsi < 28:
                return False, f"Exaustão: RSI {rsi:.1f} < 28"
            if c < float(r["bb_lower"]):
                return False, "Exaustão: Preço abaixo da Banda Inferior"
            if dist_ema21 > 1.5:
                return False, f"Exaustão: Distância EMA21 = {dist_ema21:.2f} ATR > 1.5"
            if candles_baixa >= 3:
                return False, f"Exaustão: {candles_baixa} candles consecutivos de queda"
            if cmo < -70:
                return False, f"Exaustão: CMO {cmo:.1f} < -70"
            if movimento_consumido > 0.85:
                return False, f"Movimento consumido: preço já está {movimento_consumido*100:.0f}% do range — venda no fundo"
            if stoch_rsi < 0.05:
                return False, f"StochRSI {stoch_rsi*100:.0f}% — sobrevendido extremo, aguardar bounce"

        return True, ""

    # ─────────────────────────────────────────────────────────────────────────
    # RFC V11 — GATE 2: ENTRADA PRECOCE (mínimo 3 de 8)
    # ─────────────────────────────────────────────────────────────────────────
    def _gate_entrada_precoce(self, df: pd.DataFrame, direcao: str) -> tuple[bool, list, int]:
        r    = df.iloc[-1]
        c    = float(r["close"])
        atr  = float(r["atr"])
        e21  = float(r["ema21"])
        e10  = float(r["ema10"])
        rvol = float(r["rvol"])

        checklist = []

        # 1. Pullback concluído
        dist_ema21 = abs(c - e21) / atr if atr > 0 else 99
        pullback_ok = dist_ema21 <= 1.2
        if pullback_ok: checklist.append("Pullback concluído")

        # 2. Rompimento recente (BOS ou CHoCH)
        highs = df["high"].rolling(10).max().iloc[-5]
        lows  = df["low"].rolling(10).min().iloc[-5]
        bos_ok = (c > highs) if direcao == "LONG" else (c < lows)
        if bos_ok: checklist.append("BOS/CHoCH confirmado")

        # 3. Reteste confirmado (preço voltou à zona após romper)
        bb_mid = float(r["bb_mid"])
        reteste_ok = abs(c - bb_mid) / atr < 2.0 if atr > 0 else False
        if reteste_ok: checklist.append("Reteste confirmado")

        # 4. Volume crescente
        vol_crescente = df["volume"].iloc[-1] > df["volume"].iloc[-4:-1].mean()
        if vol_crescente: checklist.append("Volume crescente")

        # 5. RVOL acima do mínimo
        rvol_ok = rvol >= 1.2
        if rvol_ok: checklist.append("RVOL acima do mínimo")

        # 6. MACD cruzando agora
        macd_hist_agora   = float(r["macd_hist"])
        macd_hist_anterior = float(df["macd_hist"].iloc[-3])
        macd_cruzando = (
            (macd_hist_anterior < 0 and macd_hist_agora > 0) if direcao == "LONG"
            else (macd_hist_anterior > 0 and macd_hist_agora < 0)
        )
        if macd_cruzando: checklist.append("MACD cruzando agora")

        # 7. EMA10 cruzando EMA21 recentemente
        e10_ant = float(df["ema10"].iloc[-4])
        e21_ant = float(df["ema21"].iloc[-4])
        ema_cruzou = (
            (e10_ant <= e21_ant and e10 > e21) if direcao == "LONG"
            else (e10_ant >= e21_ant and e10 < e21)
        )
        if ema_cruzou: checklist.append("EMA10 cruzou EMA21 recentemente")

        # 8. Candle de confirmação fechado
        o = float(r["open"]); h = float(r["high"]); l = float(r["low"])
        corpo = abs(c - o); total = h - l
        candle_confirmacao = corpo > total * 0.5 if total > 0 else False
        if direcao == "LONG" and c > o and candle_confirmacao:
            checklist.append("Candle de confirmação fechado")
        elif direcao == "SHORT" and c < o and candle_confirmacao:
            checklist.append("Candle de confirmação fechado")

        aprovado = len(checklist) >= 2
        return aprovado, checklist, len(checklist)

    # ─────────────────────────────────────────────────────────────────────────
    # RFC V11 — GATE 3: DISTÂNCIA
    # ─────────────────────────────────────────────────────────────────────────
    def _gate_distancia(self, df: pd.DataFrame, direcao: str, entrada: float, stop: float) -> tuple[bool, str]:
        r    = df.iloc[-1]
        c    = float(r["close"])
        atr  = float(r["atr"])
        vwap = float(r["vwap"])

        dist_entrada = abs(c - entrada) / atr if atr > 0 else 0
        if dist_entrada > 0.35:
            return False, f"Distância entrada: {dist_entrada:.2f} ATR > 0.35 (entrada atrasada)"

        dist_vwap = abs(c - vwap) / atr if atr > 0 else 0
        if dist_vwap > 3.0:
            return False, f"Preço muito distante da VWAP: {dist_vwap:.2f} ATR"

        return True, ""

    # ─────────────────────────────────────────────────────────────────────────
    # RFC V11 — GATE 4: VOLUME OBRIGATÓRIO
    # ─────────────────────────────────────────────────────────────────────────
    def _gate_volume(self, df: pd.DataFrame) -> tuple[bool, str]:
        r    = df.iloc[-1]
        rvol = float(r["rvol"])

        if rvol < 1.0:
            return False, f"Volume insuficiente: RVOL {rvol:.2f} < 1.0"

        vol_decrescente = df["volume"].iloc[-1] < df["volume"].iloc[-4:-1].mean() * 0.8
        if vol_decrescente:
            return False, "Volume decrescente (sem participação institucional)"

        return True, ""

    # ─────────────────────────────────────────────────────────────────────────
    # RFC V11 — GATE 5: TENDÊNCIA (EMA)
    # ─────────────────────────────────────────────────────────────────────────
    def _gate_tendencia(self, df: pd.DataFrame, direcao: str) -> tuple[bool, int]:
        r = df.iloc[-1]
        e10 = float(r["ema10"]); e21 = float(r["ema21"]); e50 = float(r["ema50"])

        if direcao == "LONG":
            alinhado = e10 > e21 > e50
        else:
            alinhado = e10 < e21 < e50

        penalizacao = 0 if alinhado else -20
        return alinhado, penalizacao

    # ─────────────────────────────────────────────────────────────────────────
    # RFC V11 — GATE 6: MOMENTUM ACELERANDO
    # ─────────────────────────────────────────────────────────────────────────
    def _gate_momentum(self, df: pd.DataFrame, direcao: str) -> tuple[bool, str]:
        hist = df["macd_hist"].iloc[-5:].values
        if len(hist) < 3:
            return True, ""

        if direcao == "LONG":
            # Bloquear apenas se 3 candles seguidos desacelerando E histograma negativo
            desacelerando = hist[-1] < hist[-2] < hist[-3] and hist[-1] < 0
            if desacelerando:
                return False, "Momentum desacelerando (MACD negativo e caindo há 3 períodos)"
        else:
            desacelerando = hist[-1] > hist[-2] > hist[-3] and hist[-1] > 0
            if desacelerando:
                return False, "Momentum desacelerando (MACD positivo e subindo há 3 períodos)"

        return True, ""

    # ─────────────────────────────────────────────────────────────────────────
    # REGIME
    # ─────────────────────────────────────────────────────────────────────────
    def _regime(self, df: pd.DataFrame) -> str:
        r   = df.iloc[-1]
        adx = r["adx"]
        bw  = r["bb_width"]
        bw_ma = df["bb_width"].rolling(20).mean().iloc[-1]

        if adx > 25:
            if r["ema10"]>r["ema21"]>r["ema50"]>r["ema200"]:
                return "Bull Trend"
            elif r["ema10"]<r["ema21"]<r["ema50"]<r["ema200"]:
                return "Bear Trend"
            return "Transição"
        elif adx < 18:
            if bw < bw_ma * 0.8:
                return "Compressão"
            return "Range"
        return "Transição"

    def _tendencia_tf(self, df: pd.DataFrame) -> str:
        r = df.iloc[-1]
        if r["ema21"] > r["ema50"]: return "ALTA"
        if r["ema21"] < r["ema50"]: return "BAIXA"
        return "NEUTRA"

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRUTURA SMC
    # ─────────────────────────────────────────────────────────────────────────
    def _bos(self, df, direcao):
        highs = df["high"].rolling(10).max()
        lows  = df["low"].rolling(10).min()
        c     = df["close"].iloc[-1]
        return (c > highs.iloc[-5]) if direcao=="LONG" else (c < lows.iloc[-5])

    def _choch(self, df, direcao):
        swing_high = df["high"].iloc[-20:-1].max()
        swing_low  = df["low"].iloc[-20:-1].min()
        c = df["close"].iloc[-1]
        if direcao=="LONG":  return c > swing_high
        return c < swing_low

    def _fvg(self, df, direcao):
        if len(df) < 4: return False
        c1h = df["high"].iloc[-3]; c1l = df["low"].iloc[-3]
        c3h = df["high"].iloc[-1]; c3l = df["low"].iloc[-1]
        return (c3l > c1h) if direcao=="LONG" else (c3h < c1l)

    def _order_block(self, df, direcao):
        atr = df["atr"].iloc[-1]
        vol_ma = df["vol_ma"]
        for i in range(-6,-1):
            forte = abs(df["close"].iloc[i]-df["open"].iloc[i]) > atr*0.7
            inst  = df["volume"].iloc[i] > vol_ma.iloc[i]*1.3
            if forte and inst:
                if direcao=="LONG" and df["close"].iloc[i]>df["open"].iloc[i]: return True
                if direcao=="SHORT" and df["close"].iloc[i]<df["open"].iloc[i]: return True
        return False

    def _sweep_liquidez(self, df, direcao):
        eq_high = df["high"].iloc[-20:-1].max()
        eq_low  = df["low"].iloc[-20:-1].min()
        lh = df["high"].iloc[-1]
        ll = df["low"].iloc[-1]
        lc = df["close"].iloc[-1]
        if direcao=="LONG":  return ll < eq_low  and lc > eq_low
        return lh > eq_high and lc < eq_high

    def _divergencia_rsi(self, df, direcao):
        closes = df["close"].iloc[-14:]
        rsis   = df["rsi"].iloc[-14:]
        if direcao=="LONG":
            return closes.iloc[-1] < closes.iloc[0] and rsis.iloc[-1] > rsis.iloc[0]
        return closes.iloc[-1] > closes.iloc[0] and rsis.iloc[-1] < rsis.iloc[0]

    def _pullback_ema21(self, df, direcao):
        c    = df["close"].iloc[-1]
        e21  = df["ema21"].iloc[-1]
        atr  = df["atr"].iloc[-1]
        return abs(c - e21) <= atr * 0.8

    def _bollinger_comprimido(self, df):
        bw    = df["bb_width"].iloc[-1]
        bw_ma = df["bb_width"].rolling(20).mean().iloc[-1]
        return bw < bw_ma * 0.85

    def _volume_crescente(self, df):
        return df["volume"].iloc[-1] > df["volume"].iloc[-3:-1].mean()

    def _candle_rejeicao(self, df, direcao):
        o = df["open"].iloc[-1];  c = df["close"].iloc[-1]
        h = df["high"].iloc[-1];  l = df["low"].iloc[-1]
        corpo = abs(c-o); total = h-l
        if total == 0: return False
        sombra_pct = (h-max(o,c))/total if direcao=="LONG" else (min(o,c)-l)/total
        return sombra_pct > 0.4 and corpo < total*0.5

    # ─────────────────────────────────────────────────────────────────────────
    # SETUPS (mantidos + penalização de tendência V11)
    # ─────────────────────────────────────────────────────────────────────────
    def _setup1_trend(self, df, direcao, regime) -> dict:
        conf=[]; falhas=[]; falta=[]
        def chk(ok, nome, desc_falha, desc_falta):
            if ok: conf.append(nome)
            else:  falhas.append(desc_falha); falta.append(desc_falta)
            return ok
        r = df.iloc[-1]
        regime_ok = regime in ("Bull Trend","Bear Trend","Transição")
        chk(regime_ok,"Regime Trend",f"Regime {regime} não favorável","Regime Bull/Bear Trend")
        emas = (r["ema10"]>r["ema21"]>r["ema50"]>r["ema200"]) if direcao=="LONG" else (r["ema10"]<r["ema21"]<r["ema50"]<r["ema200"])
        chk(emas,"EMAs alinhadas","EMAs desalinhadas","EMA10>EMA21>EMA50>EMA200")
        adx = r["adx"]
        chk(adx>=20,"ADX ≥ 20",f"ADX {adx:.1f} < 20","ADX ≥ 20")
        rvol = r["rvol"]
        chk(rvol>=1.20,"RVOL ≥ 1.20",f"RVOL {rvol:.2f} < 1.20","RVOL ≥ 1.20")
        chk(self._pullback_ema21(df,direcao),"Pullback EMA21","Sem pullback na EMA21","Pullback até EMA21")
        chk(self._bos(df,direcao),"BOS confirmado","BOS não confirmado","Break of Structure")
        macd_ok = (r["macd"]>r["macd_signal"]) if direcao=="LONG" else (r["macd"]<r["macd_signal"])
        chk(macd_ok,"MACD alinhado","MACD desalinhado","MACD na direção")
        vwap_ok = (r["close"]>r["vwap"]) if direcao=="LONG" else (r["close"]<r["vwap"])
        chk(vwap_ok,"VWAP alinhado","VWAP contra direção","VWAP na direção")
        rsi = r["rsi"]
        rsi_ok = (30<=rsi<=55) if direcao=="LONG" else (45<=rsi<=70)
        chk(rsi_ok,"RSI zona correção",f"RSI {rsi:.1f} fora da zona","RSI 30-55 (LONG) / 45-70 (SHORT)")
        chk(self._volume_crescente(df),"Volume crescente","Volume não crescente","Volume acima da média")
        chk(self._candle_rejeicao(df,direcao),"Candle de rejeição","Sem candle de rejeição","Candle de rejeição")
        peso = [(regime_ok,8),(emas,15),(adx>=20,12),(rvol>=1.20,10),(self._pullback_ema21(df,direcao),10),
                (self._bos(df,direcao),12),(macd_ok,10),(vwap_ok,8),(rsi_ok,8),(self._volume_crescente(df),7)]
        score = round(sum(p for ok,p in peso if ok)/sum(p for _,p in peso)*100)
        return {"conf":conf,"falhas":falhas,"falta":falta,"score":score,"nome":"TREND FOLLOWING"}

    def _setup2_breakout(self, df, direcao) -> dict:
        conf=[]; falhas=[]; falta=[]
        def chk(ok, nome, desc_falha, desc_falta):
            if ok: conf.append(nome)
            else:  falhas.append(desc_falha); falta.append(desc_falta)
            return ok
        r = df.iloc[-1]
        comp = self._bollinger_comprimido(df)
        chk(comp,"Bollinger comprimido","Bollinger não comprimido","Consolidação + BB comprimidas")
        adx = r["adx"]
        adx_subindo = adx > df["adx"].iloc[-5]
        chk(adx_subindo,"ADX subindo",f"ADX {adx:.1f} não subindo","ADX crescente")
        rvol = r["rvol"]
        chk(rvol>=1.50,"RVOL ≥ 1.50",f"RVOL {rvol:.2f} < 1.50","RVOL ≥ 1.50")
        chk(self._bos(df,direcao),"BOS rompimento","BOS não confirmado","Rompimento do BOS")
        macd_acelerando = r["macd_hist"] > df["macd_hist"].iloc[-3]
        chk(macd_acelerando,"MACD acelerando","MACD não acelerando","MACD histograma crescendo")
        vwap_ok = (r["close"]>r["vwap"]) if direcao=="LONG" else (r["close"]<r["vwap"])
        chk(vwap_ok,"VWAP alinhado","VWAP contra direção","VWAP alinhado")
        reteste = abs(r["close"]-r["bb_mid"])/r["atr"] < 2.0
        chk(reteste,"Reteste confirmado","Aguardar reteste","Reteste da região rompida")
        peso = [(comp,15),(adx_subindo,12),(rvol>=1.50,15),(self._bos(df,direcao),15),
                (macd_acelerando,12),(vwap_ok,10),(reteste,21)]
        score = round(sum(p for ok,p in peso if ok)/sum(p for _,p in peso)*100)
        return {"conf":conf,"falhas":falhas,"falta":falta,"score":score,"nome":"BREAKOUT"}

    def _setup3_reversao(self, df, direcao) -> dict:
        conf=[]; falhas=[]; falta=[]
        def chk(ok, nome, desc_falha, desc_falta):
            if ok: conf.append(nome)
            else:  falhas.append(desc_falha); falta.append(desc_falta)
            return ok
        r = df.iloc[-1]
        sweep = self._sweep_liquidez(df, direcao)
        chk(sweep,"Sweep de Liquidez","Sem sweep de liquidez","Sweep de Equal High/Low")
        choch = self._choch(df, direcao)
        chk(choch,"CHoCH confirmado","CHoCH não confirmado","Mudança de estrutura")
        bos_inv = self._bos(df, direcao)
        chk(bos_inv,"BOS invertido","BOS invertido não confirmado","BOS na nova direção")
        ob = self._order_block(df, direcao)
        chk(ob,"Order Block institucional","Sem Order Block válido","Order Block com volume")
        fvg = self._fvg(df, direcao)
        chk(fvg,"Fair Value Gap","Sem FVG","Retorno ao FVG")
        div = self._divergencia_rsi(df, direcao)
        chk(div,"Divergência RSI/MACD","Sem divergência","Divergência de RSI ou MACD")
        rvol = r["rvol"]
        chk(rvol>=1.20,"Volume institucional",f"RVOL {rvol:.2f} < 1.20","Volume institucional")
        adx_subindo = r["adx"] > df["adx"].iloc[-5]
        chk(adx_subindo,"ADX voltando a subir","ADX não subindo","ADX crescente após reversão")
        peso = [(sweep,20),(choch,20),(bos_inv,15),(ob,15),(fvg,12),(div,10),(rvol>=1.20,5),(adx_subindo,3)]
        score = round(sum(p for ok,p in peso if ok)/sum(p for _,p in peso)*100)
        return {"conf":conf,"falhas":falhas,"falta":falta,"score":score,"nome":"REVERSÃO INSTITUCIONAL"}

    def _setup4_scalping(self, df, direcao) -> dict:
        conf=[]; falhas=[]; falta=[]
        def chk(ok, nome, desc_falha, desc_falta):
            if ok: conf.append(nome)
            else:  falhas.append(desc_falha); falta.append(desc_falta)
            return ok
        r = df.iloc[-1]
        adx = r["adx"]
        chk(adx<18,"ADX baixo (Range)",f"ADX {adx:.1f} ≥ 18","ADX < 18")
        bw    = r["bb_width"]
        bw_ma = df["bb_width"].rolling(20).mean().iloc[-1]
        bb_lat = bw <= bw_ma * 1.1
        chk(bb_lat,"Bollinger lateral","Bollinger expandindo","Bollinger lateral")
        rsi = r["rsi"]
        rsi_ok = (rsi<=35) if direcao=="LONG" else (rsi>=65)
        chk(rsi_ok,"RSI na extremidade",f"RSI {rsi:.1f} fora da extremidade","RSI ≤ 35 / ≥ 65")
        rej = self._candle_rejeicao(df, direcao)
        chk(rej,"Rejeição no S/R","Sem rejeição no S/R","Candle de rejeição")
        rvol = r["rvol"]
        chk(rvol>=1.0,"Volume confirmado",f"RVOL {rvol:.2f} < 1.0","Volume acima da média")
        sem_tend = not(r["ema10"]>r["ema21"]>r["ema50"] or r["ema10"]<r["ema21"]<r["ema50"])
        chk(sem_tend,"Sem tendência dominante","Tendência dominante detectada","Ausência de tendência dominante")
        peso = [(adx<18,20),(bb_lat,15),(rsi_ok,20),(rej,20),(rvol>=1.0,10),(sem_tend,15)]
        score = round(sum(p for ok,p in peso if ok)/sum(p for _,p in peso)*100)
        return {"conf":conf,"falhas":falhas,"falta":falta,"score":score,"nome":"SCALPING ADAPTATIVO"}

    def _selecionar_setup(self, df, direcao, regime) -> dict:
        s3 = self._setup3_reversao(df, direcao)
        s1 = self._setup1_trend(df, direcao, regime)
        s2 = self._setup2_breakout(df, direcao)
        s4 = self._setup4_scalping(df, direcao)
        candidatos = [
            (s3["score"] + 5, s3),
            (s1["score"] + 3, s1),
            (s2["score"],     s2),
            (s4["score"],     s4),
        ]
        candidatos.sort(key=lambda x: x[0], reverse=True)
        return candidatos[0][1]

    # ─────────────────────────────────────────────────────────────────────────
    # GESTÃO DE BANCA
    # ─────────────────────────────────────────────────────────────────────────
    def _gestao_banca(self, regime, entrada, stop, atr):
        base = ALAVANCAGEM_POR_REGIME.get(regime, 10)
        fator_atr = max(0.5, min(1.0, 0.002/atr if atr>0 else 1.0))
        alavancagem = max(8, min(25, round(base * fator_atr)))
        risco_usdt  = round(BANCA * RISCO_PCT / 100, 2)
        dist_stop   = abs(entrada-stop)/entrada if entrada else 0.01
        posicao     = round(min(risco_usdt/dist_stop, BANCA*alavancagem), 2) if dist_stop>0 else 0
        capital     = round(posicao/alavancagem, 2)
        return {"alavancagem":alavancagem,"capital":capital,"posicao":posicao,
                "risco_usdt":risco_usdt,"ganho_tp1":round(risco_usdt*2,2),"banca":BANCA}

    # ─────────────────────────────────────────────────────────────────────────
    # ANÁLISE PRINCIPAL V11
    # ─────────────────────────────────────────────────────────────────────────
    def analisar(self, symbol: str, timeframe: str = None) -> dict:
        """
        Se timeframe=None, analisa 30m/1h/4h/1d e retorna o melhor sinal aprovado.
        Se timeframe específico, analisa apenas aquele.
        """
        tfs_para_analisar = [timeframe] if timeframe else ["30m", "1h", "4h", "1d"]
        resultados = []
        for tf in tfs_para_analisar:
            r = self._analisar_tf(symbol, tf)
            resultados.append(r)
        # Retornar o melhor aprovado, ou o de maior score se nenhum aprovado
        aprovados = [r for r in resultados if r.get("aprovado")]
        if aprovados:
            return max(aprovados, key=lambda x: x["score"])
        return max(resultados, key=lambda x: x["score"])

    def _analisar_tf(self, symbol: str, tf: str = "30m") -> dict:
        limit_superior = 200 if tf in ("4h","1d") else 300
        try:
            df_tf = self._calc(self._fetch(symbol, tf, limit=limit_superior))
            df4h  = self._calc(self._fetch(symbol, "4h", limit=200))
            df1d  = self._calc(self._fetch(symbol, "1d", limit=200))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"setup_nome":"—","regime":"Erro",
                    "score":0,"motivos_rejeicao":[str(e)],"o_que_falta":[],"setup_alternativo":"—",
                    "timeframe":tf}

        regime   = self._regime(df_tf)
        tend_4h  = self._tendencia_tf(df4h)
        tend_1d  = self._tendencia_tf(df1d)
        r30      = df_tf.iloc[-1]

        direcao = "LONG" if r30["ema10"] > r30["ema21"] else "SHORT"
        df30 = df_tf  # alias para o resto do código

        # Níveis antecipados para gates de distância
        c   = float(r30["close"])
        atr = float(r30["atr"])
        entrada = round(c, 4)
        stop    = round(c - atr*1.5, 4) if direcao=="LONG" else round(c + atr*1.5, 4)
        tp1     = round(c + atr*1.0, 4) if direcao=="LONG" else round(c - atr*1.0, 4)
        tp2     = round(c + atr*2.0, 4) if direcao=="LONG" else round(c - atr*2.0, 4)
        tp3     = round(c + atr*3.0, 4) if direcao=="LONG" else round(c - atr*3.0, 4)
        rr      = round(abs(tp2-entrada)/abs(stop-entrada), 2) if stop != entrada else 0

        motivos = []
        falta   = []

        # ── GATE 1: EXAUSTÃO ─────────────────────────────────────────────────
        exaustao_ok, exaustao_msg = self._gate_exaustao(df30, direcao)
        if not exaustao_ok:
            motivos.append(exaustao_msg)
            falta.append("Aguardar zona de menor pressão / pullback")

        # ── GATE 2: ENTRADA PRECOCE ───────────────────────────────────────────
        precoce_ok, precoce_confs, precoce_cnt = self._gate_entrada_precoce(df30, direcao)
        if not precoce_ok:
            motivos.append(f"Entrada precoce: apenas {precoce_cnt}/2 critérios confirmados")
            falta.append("Mínimo 2 de: Pullback, BOS/CHoCH, Reteste, Volume, RVOL, MACD, EMA10x21, Candle")

        # ── GATE 3: DISTÂNCIA ─────────────────────────────────────────────────
        dist_ok, dist_msg = self._gate_distancia(df30, direcao, entrada, stop)
        if not dist_ok:
            motivos.append(dist_msg)
            falta.append("Aguardar aproximação do preço à entrada ideal")

        # ── GATE 4: VOLUME OBRIGATÓRIO ────────────────────────────────────────
        vol_ok, vol_msg = self._gate_volume(df30)
        if not vol_ok:
            motivos.append(vol_msg)
            falta.append("Aguardar participação institucional (RVOL ≥ 1.0)")

        # ── GATE 5: TENDÊNCIA ─────────────────────────────────────────────────
        tend_ok, tend_pen = self._gate_tendencia(df30, direcao)

        # ── GATE 6: MOMENTUM ──────────────────────────────────────────────────
        mom_ok, mom_msg = self._gate_momentum(df30, direcao)
        if not mom_ok:
            motivos.append(mom_msg)
            falta.append("Aguardar momentum acelerando na direção")

        # ── SETUP PRINCIPAL ───────────────────────────────────────────────────
        setup = self._selecionar_setup(df30, direcao, regime)

        # ── MTF ───────────────────────────────────────────────────────────────
        is_reversao = setup["nome"] == "REVERSÃO INSTITUCIONAL"
        if is_reversao:
            mtf_ok = True
        else:
            if direcao == "LONG":
                mtf_ok = tend_4h != "BAIXA" and tend_1d != "BAIXA"
            else:
                mtf_ok = tend_4h != "ALTA" and tend_1d != "ALTA"
            if not mtf_ok:
                motivos.insert(0, f"Contra tendência H4={tend_4h} D1={tend_1d}")
                falta.insert(0, "Aguardar alinhamento H4 e D1")

        if rr < 2.0:
            motivos.append(f"RR {rr} < 2.0")
            falta.append("RR mínimo 1:2")

        # ── SCORE ─────────────────────────────────────────────────────────────
        atr_pct    = atr / c * 100 if c > 0 else 0
        stop_pct   = abs(stop-c)/c*100
        atr_cons   = round(atr_pct / (atr_pct + stop_pct) * 100) if (atr_pct + stop_pct) > 0 else 0
        dist_ema21 = round(abs(c - float(r30["ema21"])) / atr, 2) if atr > 0 else 0
        kalman     = "UP" if direcao == "LONG" else "DOWN"

        # Bônus V11: prioridade a entrada precoce e volume
        bonus_precoce   = precoce_cnt * 3   # até +24
        bonus_vol       = min(round((float(r30["rvol"]) - 1.0) * 15), 20) if float(r30["rvol"]) >= 1.0 else 0
        penalizacao_tend = tend_pen          # -20 se EMAs desalinhadas

        score_data = {
            "confirmacoes":       setup["conf"] + precoce_confs,
            "direcao":            direcao,
            "tend_4h":            tend_4h,
            "tend_1d":            tend_1d,
            "adx":                float(r30["adx"]),
            "rsi":                float(r30["rsi"]),
            "rvol":               float(r30["rvol"]),
            "rr":                 rr,
            "atr_consumido":      atr_cons,
            "atr_pct":            atr_pct,
            "dist_ema21_atr":     dist_ema21,
            "kalman":             kalman,
            "mtf_ok":             mtf_ok,
            "macd_hist":          float(r30["macd_hist"]),
            "liquidez_status":    "ALTA" if float(r30["rvol"]) >= 1.2 else "BAIXA",
            "liquidez_score":     min(round(float(r30["rvol"]) * 60), 100),
            "timing_score":       min(round(float(r30["adx"]) + (50 - abs(float(r30["rsi"]) - 50))), 100),
            "institucional_score":round(len(setup["conf"]) * 12),
            "cruzamento_antigo":  False,
            "bonus_v11":          bonus_precoce + bonus_vol,
            "penalizacao_v11":    penalizacao_tend,
        }

        sc          = calcular_score(score_data)
        score_final = max(0, min(100, sc["score_final"] + bonus_precoce + bonus_vol + penalizacao_tend))
        tier        = sc["tier"]
        aprovado_sc = score_final >= 70

        if not aprovado_sc:
            motivos.append(f"Score {score_final} < 70")
            falta.append("Score ≥ 70")

        # ── Exaustão detectada (para exibir no cartão) ────────────────────────
        exaustao_label = exaustao_msg if not exaustao_ok else "Nenhuma"

        aprovado = (
            len(motivos) == 0
            and aprovado_sc
            and rr >= 2.0
            and mtf_ok
            and exaustao_ok
            and precoce_ok
            and vol_ok
            and mom_ok
        )

        gb = self._gestao_banca(regime, entrada, stop, atr)

        # Confirmações V11 para o cartão
        smc_confs = []
        if self._bos(df30, direcao):        smc_confs.append("BOS")
        if self._choch(df30, direcao):      smc_confs.append("CHoCH")
        if self._order_block(df30, direcao):smc_confs.append("Order Block")
        if self._fvg(df30, direcao):        smc_confs.append("FVG")
        if self._sweep_liquidez(df30, direcao): smc_confs.append("Liquidez")
        if len([p for p in precoce_confs if "Reteste" in p]): smc_confs.append("Reteste")

        def conv(s):
            if s >= 90: return "ELITE 🔥"
            if s >= 80: return "ALTA ✅"
            if s >= 70: return "BOA ⚡"
            return "BAIXA ❌"

        return {
            "symbol":            symbol,
            "aprovado":          aprovado,
            "setup_nome":        setup["nome"],
            "regime":            regime,
            "direcao":           direcao,
            "score":             score_final,
            "conviccao":         conv(score_final),
            "entrada":           entrada,
            "stop":              stop,
            "tp1":               tp1,
            "tp2":               tp2,
            "tp3":               tp3,
            "rr":                rr,
            "adx":               float(r30["adx"]),
            "rsi":               float(r30["rsi"]),
            "atr":               atr,
            "rvol":              float(r30["rvol"]),
            "cmo":               float(r30["cmo"]) if not np.isnan(r30["cmo"]) else 0.0,
            "vwap":              float(r30["vwap"]),
            "ema10":             float(r30["ema10"]),
            "ema21":             float(r30["ema21"]),
            "ema50":             float(r30["ema50"]),
            "macd_hist":         float(r30["macd_hist"]),
            "bb_upper":          float(r30["bb_upper"]),
            "bb_lower":          float(r30["bb_lower"]),
            "confirmacoes":      setup["conf"],
            "confirmacoes_smc":  smc_confs,
            "confirmacoes_v11":  precoce_confs,
            "exaustao":          exaustao_label,
            "tier":              tier,
            "penalizacoes":      sc["penalizacoes"],
            "bonus":             sc["bonus"],
            "score_componentes": sc["componentes"],
            "motivos_rejeicao":  motivos,
            "o_que_falta":       falta,
            "setup_alternativo": "—",
            "tend_4h":           tend_4h,
            "tend_1d":           tend_1d,
            "timeframe":         tf,
            "preco_atual":       c,
            **gb,
        }

    def analisar_tf(self, symbol: str, tf: str) -> dict:
        """Analisa um símbolo em um timeframe específico"""
        return self._analisar_tf(symbol, tf)

    def obter_regime(self, symbol: str) -> dict:
        df30 = self._calc(self._fetch(symbol, "30m"))
        df4h = self._calc(self._fetch(symbol, "4h", limit=100))
        df1d = self._calc(self._fetch(symbol, "1d", limit=100))
        regime = self._regime(df30)
        r = df30.iloc[-1]
        regime_setup = {
            "Bull Trend":"TREND FOLLOWING","Bear Trend":"TREND FOLLOWING",
            "Compressão":"BREAKOUT","Transição":"REVERSÃO INSTITUCIONAL","Range":"SCALPING ADAPTATIVO"
        }
        return {"regime":regime,"adx":r["adx"],"atr":r["atr"],
                "tendencia_4h":self._tendencia_tf(df4h),
                "tendencia_1d":self._tendencia_tf(df1d),
                "setup_recomendado":regime_setup.get(regime,"SCALPING ADAPTATIVO")}
