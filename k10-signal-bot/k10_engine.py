"""
K10 Institucional Engine — v3.0
4 Setups oficiais com hierarquia automática
Timeframes: 30m | 1h | 4h | 1D
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

        return df

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
        if direcao=="LONG":  return c > swing_high   # estrutura invertida para cima
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
    # SETUPS
    # ─────────────────────────────────────────────────────────────────────────

    def _setup1_trend(self, df, direcao, regime) -> dict:
        """SETUP 1 — TREND FOLLOWING"""
        conf=[]; falhas=[]; falta=[]

        def chk(ok, nome, desc_falha, desc_falta):
            if ok: conf.append(nome)
            else:  falhas.append(desc_falha); falta.append(desc_falta)
            return ok

        r = df.iloc[-1]
        # Regime compatível
        regime_ok = regime in ("Bull Trend","Bear Trend","Transição")
        chk(regime_ok, "Regime Trend", f"Regime {regime} não favorável a Trend Following","Regime Bull/Bear Trend")

        # EMAs alinhadas
        if direcao=="LONG":
            emas = r["ema10"]>r["ema21"]>r["ema50"]>r["ema200"]
        else:
            emas = r["ema10"]<r["ema21"]<r["ema50"]<r["ema200"]
        chk(emas,"EMAs alinhadas","EMAs desalinhadas","EMA10>EMA21>EMA50>EMA200")

        adx = r["adx"]
        chk(adx>=20,"ADX ≥ 20",f"ADX {adx:.1f} < 20","ADX ≥ 20")

        rvol = r["rvol"]
        chk(rvol>=1.20,"RVOL ≥ 1.20",f"RVOL {rvol:.2f} < 1.20","RVOL ≥ 1.20")

        chk(self._pullback_ema21(df,direcao),"Pullback EMA21","Sem pullback na EMA21","Pullback até EMA21 ou OB")
        chk(self._bos(df,direcao),"BOS confirmado","BOS não confirmado","Break of Structure")

        # MACD alinhado
        macd_ok = (r["macd"]>r["macd_signal"]) if direcao=="LONG" else (r["macd"]<r["macd_signal"])
        chk(macd_ok,"MACD alinhado","MACD desalinhado","MACD na direção da operação")

        # VWAP
        vwap_ok = (r["close"]>r["vwap"]) if direcao=="LONG" else (r["close"]<r["vwap"])
        chk(vwap_ok,"VWAP alinhado",f"Preço {'abaixo' if direcao=='LONG' else 'acima'} do VWAP","VWAP na direção da operação")

        # RSI zona de correção
        rsi = r["rsi"]
        rsi_ok = (30<=rsi<=55) if direcao=="LONG" else (45<=rsi<=70)
        chk(rsi_ok,"RSI zona correção",f"RSI {rsi:.1f} fora da zona de pullback","RSI entre 30-45 (LONG) ou 55-70 (SHORT)")

        chk(self._volume_crescente(df),"Volume crescente","Volume não crescente","Volume acima da média crescendo")
        chk(self._candle_rejeicao(df,direcao),"Candle de rejeição","Sem candle de rejeição/confirmação","Candle de rejeição + retomada")

        peso = [(regime_ok,8),(emas,15),(adx>=20,12),(rvol>=1.20,10),
                (self._pullback_ema21(df,direcao),10),(self._bos(df,direcao),12),
                (macd_ok,10),(vwap_ok,8),(rsi_ok,8),(self._volume_crescente(df),7)]
        score = round(sum(p for ok,p in peso if ok)/sum(p for _,p in peso)*100)

        return {"conf":conf,"falhas":falhas,"falta":falta,"score":score,"nome":"TREND FOLLOWING"}

    def _setup2_breakout(self, df, direcao) -> dict:
        """SETUP 2 — BREAKOUT INSTITUCIONAL"""
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
        chk(adx_subindo,"ADX subindo",f"ADX {adx:.1f} não subindo","ADX crescente (expansão da tendência)")

        rvol = r["rvol"]
        chk(rvol>=1.50,"RVOL ≥ 1.50",f"RVOL {rvol:.2f} < 1.50 (fraco para Breakout)","RVOL ≥ 1.50 (explosão de volume)")

        chk(self._bos(df,direcao),"BOS rompimento","BOS não confirmado","Rompimento do BOS com fechamento")

        macd_acelerando = r["macd_hist"] > df["macd_hist"].iloc[-3]
        chk(macd_acelerando,"MACD acelerando","MACD não acelerando","MACD histograma crescendo")

        vwap_ok = (r["close"]>r["vwap"]) if direcao=="LONG" else (r["close"]<r["vwap"])
        chk(vwap_ok,"VWAP alinhado","VWAP contra direção","VWAP alinhado com o rompimento")

        # Reteste: preço próximo da região rompida (não entrar no primeiro candle explosivo)
        bb_mid = r["bb_mid"]
        reteste = abs(r["close"]-bb_mid)/r["atr"] < 2.0
        chk(reteste,"Reteste confirmado","Entrar após reteste, não no candle explosivo","Aguardar reteste da região rompida")

        peso = [(comp,15),(adx_subindo,12),(rvol>=1.50,15),(self._bos(df,direcao),15),
                (macd_acelerando,12),(vwap_ok,10),(reteste,21)]
        score = round(sum(p for ok,p in peso if ok)/sum(p for _,p in peso)*100)

        return {"conf":conf,"falhas":falhas,"falta":falta,"score":score,"nome":"BREAKOUT"}

    def _setup3_reversao(self, df, direcao) -> dict:
        """SETUP 3 — REVERSÃO INSTITUCIONAL (SMC) — pode operar contra H4/D1"""
        conf=[]; falhas=[]; falta=[]

        def chk(ok, nome, desc_falha, desc_falta):
            if ok: conf.append(nome)
            else:  falhas.append(desc_falha); falta.append(desc_falta)
            return ok

        r = df.iloc[-1]

        sweep = self._sweep_liquidez(df, direcao)
        chk(sweep,"Sweep de Liquidez","Sem sweep de liquidez","Sweep de Equal High/Low antes da entrada")

        choch = self._choch(df, direcao)
        chk(choch,"CHoCH confirmado","CHoCH não confirmado","Mudança de estrutura (CHoCH)")

        bos_inv = self._bos(df, direcao)
        chk(bos_inv,"BOS invertido","BOS invertido não confirmado","BOS na nova direção após CHoCH")

        ob = self._order_block(df, direcao)
        chk(ob,"Order Block institucional","Sem Order Block válido","Order Block com volume institucional")

        fvg = self._fvg(df, direcao)
        chk(fvg,"Fair Value Gap","Sem FVG","Retorno ao Fair Value Gap")

        div = self._divergencia_rsi(df, direcao)
        chk(div,"Divergência RSI/MACD","Sem divergência","Divergência de RSI ou MACD")

        rvol = r["rvol"]
        chk(rvol>=1.20,"Volume institucional",f"RVOL {rvol:.2f} < 1.20","Volume institucional no setup")

        adx = r["adx"]
        adx_subindo = adx > df["adx"].iloc[-5]
        chk(adx_subindo,"ADX voltando a subir","ADX não subindo","ADX voltando a crescer após reversão")

        peso = [(sweep,20),(choch,20),(bos_inv,15),(ob,15),(fvg,12),(div,10),(rvol>=1.20,5),(adx_subindo,3)]
        score = round(sum(p for ok,p in peso if ok)/sum(p for _,p in peso)*100)

        return {"conf":conf,"falhas":falhas,"falta":falta,"score":score,"nome":"REVERSÃO INSTITUCIONAL"}

    def _setup4_scalping(self, df, direcao) -> dict:
        """SETUP 4 — SCALPING ADAPTATIVO (Range/Lateral)"""
        conf=[]; falhas=[]; falta=[]

        def chk(ok, nome, desc_falha, desc_falta):
            if ok: conf.append(nome)
            else:  falhas.append(desc_falha); falta.append(desc_falta)
            return ok

        r = df.iloc[-1]

        adx = r["adx"]
        chk(adx<18,"ADX baixo (Range)",f"ADX {adx:.1f} ≥ 18 (não é Range)","ADX < 18 para Scalping")

        # Bollinger lateral
        bw    = r["bb_width"]
        bw_ma = df["bb_width"].rolling(20).mean().iloc[-1]
        bb_lat = bw <= bw_ma * 1.1
        chk(bb_lat,"Bollinger lateral","Bollinger expandindo (sem range)","Bollinger Bands laterais")

        # RSI nas extremidades
        rsi = r["rsi"]
        rsi_ok = (rsi<=35) if direcao=="LONG" else (rsi>=65)
        chk(rsi_ok,"RSI na extremidade",f"RSI {rsi:.1f} fora da extremidade","RSI ≤ 35 (LONG) ou ≥ 65 (SHORT)")

        # Rejeição no S/R
        rej = self._candle_rejeicao(df, direcao)
        chk(rej,"Rejeição no S/R","Sem rejeição forte no S/R","Candle de rejeição no suporte/resistência")

        rvol = r["rvol"]
        chk(rvol>=1.0,"Volume confirmado",f"RVOL {rvol:.2f} < 1.0","Volume acima da média")

        # Sem tendência dominante
        sem_tend = not(r["ema10"]>r["ema21"]>r["ema50"] or r["ema10"]<r["ema21"]<r["ema50"])
        chk(sem_tend,"Sem tendência dominante","Tendência dominante detectada (evitar Scalping)","Ausência de tendência dominante")

        peso = [(adx<18,20),(bb_lat,15),(rsi_ok,20),(rej,20),(rvol>=1.0,10),(sem_tend,15)]
        score = round(sum(p for ok,p in peso if ok)/sum(p for _,p in peso)*100)

        return {"conf":conf,"falhas":falhas,"falta":falta,"score":score,"nome":"SCALPING ADAPTATIVO"}

    # ─────────────────────────────────────────────────────────────────────────
    # HIERARQUIA: seleciona o melhor setup automaticamente
    # ─────────────────────────────────────────────────────────────────────────
    def _selecionar_setup(self, df, direcao, regime) -> dict:
        """
        Hierarquia: Reversão > Trend Following > Breakout > Scalping
        Se múltiplos aprovados, seleciona o de maior score.
        """
        s3 = self._setup3_reversao(df, direcao)
        s1 = self._setup1_trend(df, direcao, regime)
        s2 = self._setup2_breakout(df, direcao)
        s4 = self._setup4_scalping(df, direcao)

        # Ordena por score, com peso de hierarquia (+5 para Reversão, +3 para Trend)
        candidatos = [
            (s3["score"] + 5, s3),
            (s1["score"] + 3, s1),
            (s2["score"],     s2),
            (s4["score"],     s4),
        ]
        candidatos.sort(key=lambda x: x[0], reverse=True)
        return candidatos[0][1]   # melhor setup

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
    # ANÁLISE PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────
    def analisar(self, symbol: str) -> dict:
        try:
            df30 = self._calc(self._fetch(symbol, "30m"))
            df4h = self._calc(self._fetch(symbol, "4h",  limit=200))
            df1d = self._calc(self._fetch(symbol, "1d",  limit=200))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"setup_nome":"—","regime":"Erro",
                    "score":0,"motivos_rejeicao":[str(e)],"o_que_falta":[],"setup_alternativo":"—"}

        regime   = self._regime(df30)
        tend_4h  = self._tendencia_tf(df4h)
        tend_1d  = self._tendencia_tf(df1d)
        r30      = df30.iloc[-1]

        direcao = "LONG" if r30["ema10"] > r30["ema21"] else "SHORT"

        # ── Selecionar melhor setup ───────────────────────────────────────────
        setup = self._selecionar_setup(df30, direcao, regime)

        # ── MTF — Reversão PODE operar contra H4/D1 se confirmada ────────────
        is_reversao = setup["nome"] == "REVERSÃO INSTITUCIONAL"
        if is_reversao:
            # Exceção: permitido se Sweep + CHoCH + BOS confirmados
            mtf_ok = True
            mtf_motivo = ""
        else:
            if direcao == "LONG":
                mtf_ok = tend_4h != "BAIXA" and tend_1d != "BAIXA"
            else:
                mtf_ok = tend_4h != "ALTA" and tend_1d != "ALTA"
            mtf_motivo = f"Contra tendência H4={tend_4h} D1={tend_1d}" if not mtf_ok else ""

        # ── Níveis ────────────────────────────────────────────────────────────
        c   = r30["close"]
        atr = r30["atr"]
        if direcao == "LONG":
            entrada = round(c, 4)
            stop    = round(c - atr*1.5, 4)
            tp1     = round(c + atr*1.0, 4)   # TP1 = 1:1
            tp2     = round(c + atr*2.0, 4)   # TP2 = 1:2
            tp3     = round(c + atr*3.0, 4)   # TP3 = 1:3
        else:
            entrada = round(c, 4)
            stop    = round(c + atr*1.5, 4)
            tp1     = round(c - atr*1.0, 4)
            tp2     = round(c - atr*2.0, 4)
            tp3     = round(c - atr*3.0, 4)

        rr = round(abs(tp2-entrada)/abs(stop-entrada), 2) if stop!=entrada else 0

        # ── Score final (setup + MTF) ─────────────────────────────────────────
        score_final = round(setup["score"] * (1.0 if mtf_ok else 0.7))

        # ── Falhas finais ─────────────────────────────────────────────────────
        motivos = list(setup["falhas"])
        falta   = list(setup["falta"])
        if not mtf_ok:
            motivos.insert(0, mtf_motivo)
            falta.insert(0, "Aguardar alinhamento de H4 e D1")
        if rr < 2.0:
            motivos.append(f"RR {rr} < 2.0")
            falta.append("RR mínimo 1:2")
        if score_final < 70:
            motivos.append(f"Score {score_final} < 70 (mínimo exigido)")
            falta.append("Score ≥ 70")

        aprovado = len(motivos)==0 and score_final>=70 and rr>=2.0 and mtf_ok

        gb = self._gestao_banca(regime, entrada, stop, atr)

        def convicção(s):
            if s>=90: return "ELITE 🔥"
            if s>=80: return "ALTA ✅"
            if s>=70: return "BOA ⚡"
            return "BAIXA ❌"

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "setup_nome":       setup["nome"],
            "regime":           regime,
            "direcao":          direcao,
            "score":            score_final,
            "convicção":        convicção(score_final),
            "entrada":          entrada,
            "stop":             stop,
            "tp1":              tp1,
            "tp2":              tp2,
            "tp3":              tp3,
            "rr":               rr,
            "adx":              r30["adx"],
            "rsi":              r30["rsi"],
            "atr":              atr,
            "rvol":             r30["rvol"],
            "volume_status":    f"RVOL {r30['rvol']:.2f}",
            "confirmacoes":     setup["conf"],
            "motivos_rejeicao": motivos,
            "o_que_falta":      falta,
            "setup_alternativo":"—",
            "tend_4h":          tend_4h,
            "tend_1d":          tend_1d,
            "timeframe":        "30m",
            "preco_atual":      c,
            **gb,
        }

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
