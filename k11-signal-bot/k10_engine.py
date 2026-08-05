"""
K11 Engine EQ V3 — Entry Quality Motor
Foco: qualidade do ponto de entrada, não quantidade de filtros
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from config import BANCA, RISCO_PCT


def sessao_atual():
    h_utc = datetime.now(timezone.utc).hour
    h_brt = (h_utc - 3) % 24
    if 9 <= h_brt < 13:  return f"LONDRES+NY ({h_brt:02d}h BRT)", 100
    if 4 <= h_brt < 13:  return f"LONDRES ({h_brt:02d}h BRT)", 85
    if 9 <= h_brt < 18:  return f"NY ({h_brt:02d}h BRT)", 85
    return f"({h_brt:02d}h BRT)", 60


class K10Engine:
    def __init__(self):
        self.exchange = ccxt.mexc({
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })

    def _fetch(self, symbol, tf, limit=300):
        try:
            raw = self.exchange.fetch_ohlcv(symbol, tf, limit=limit)
            df  = pd.DataFrame(raw, columns=["ts","open","high","low","close","volume"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            return df
        except Exception as e:
            raise RuntimeError(f"{symbol} {tf}: {e}")

    def _calc(self, df):
        c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
        for p in [10, 21, 50, 200]:
            df[f"ema{p}"] = c.ewm(span=p, adjust=False).mean()
        tr   = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
        df["atr"] = tr.ewm(span=14, adjust=False).mean()
        dm_p = h.diff().clip(lower=0).where(h.diff()>(-l.diff()),0.0)
        dm_n = (-l.diff()).clip(lower=0).where((-l.diff())>h.diff(),0.0)
        atr14= tr.ewm(span=14,adjust=False).mean()
        di_p = 100*dm_p.ewm(span=14,adjust=False).mean()/atr14
        di_n = 100*dm_n.ewm(span=14,adjust=False).mean()/atr14
        dx   = 100*(di_p-di_n).abs()/(di_p+di_n).replace(0,np.nan)
        df["adx"] = dx.ewm(span=14,adjust=False).mean()
        delta= c.diff()
        gain = delta.clip(lower=0).ewm(span=14,adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(span=14,adjust=False).mean()
        df["rsi"] = 100-100/(1+gain/loss.replace(0,np.nan))
        ema12= c.ewm(span=12,adjust=False).mean()
        ema26= c.ewm(span=26,adjust=False).mean()
        df["macd"]        = ema12-ema26
        df["macd_signal"] = df["macd"].ewm(span=9,adjust=False).mean()
        df["macd_hist"]   = df["macd"]-df["macd_signal"]
        vol_sma = v.rolling(20,min_periods=10).mean()
        df["vol_ma"] = vol_sma
        df["rvol"]   = (v.shift(1)/vol_sma.replace(0,np.nan)).clip(0,50)
        df["vwap"]   = (v*(h+l+c)/3).cumsum()/v.cumsum()
        return df

    def _detectar_ob(self, df, direcao):
        dfc = df.iloc[:-1]
        atr = float(dfc["atr"].iloc[-1])
        c_atual = float(dfc["close"].iloc[-1])
        for i in range(-2, -12, -1):
            try:
                vela = dfc.iloc[i]; prox = dfc.iloc[i+1]
                o=float(vela["open"]); cv=float(vela["close"])
                rvol_p = float(prox["rvol"]) if not np.isnan(prox["rvol"]) else 0
                mov = abs(float(prox["close"])-float(prox["open"])) > atr*0.5
                if direcao=="LONG" and cv<o and float(prox["close"])>float(prox["open"]) and rvol_p>=0.8 and mov:
                    if float(vela["low"]) <= c_atual <= float(vela["high"])*1.005:
                        return True, float(vela["low"]), float(vela["high"])
                if direcao=="SHORT" and cv>o and float(prox["close"])<float(prox["open"]) and rvol_p>=0.8 and mov:
                    if float(vela["low"])*0.995 <= c_atual <= float(vela["high"]):
                        return True, float(vela["low"]), float(vela["high"])
            except: continue
        return False, 0, 0

    def _bos_idade(self, df, direcao):
        """Quantas velas desde o BOS/CHoCH mais recente."""
        dfc = df.iloc[:-1]
        highs = dfc["high"].values
        lows  = dfc["low"].values
        closes= dfc["close"].values
        n = len(closes)
        for i in range(n-2, max(n-15, 0), -1):
            swing_h = highs[max(0,i-5):i].max() if i>=5 else highs[:i].max() if i>0 else 0
            swing_l = lows[max(0,i-5):i].min() if i>=5 else lows[:i].min() if i>0 else 9e9
            if direcao=="LONG" and closes[i] > swing_h:
                return n - 1 - i
            if direcao=="SHORT" and closes[i] < swing_l:
                return n - 1 - i
        return 99

    def _entry_quality(self, df, direcao, ob_ok, ob_low, ob_high):
        """
        Entry Quality V3 — qualidade do ponto de entrada (0-100)
        Base 50: sobe com bônus, cai com penalidades
        """
        dfc = df.iloc[:-1]
        r   = dfc.iloc[-1]
        c   = float(r["close"])
        atr = float(r["atr"])
        e21 = float(r["ema21"])
        rsi = float(r["rsi"])
        mh  = float(r["macd_hist"])
        mh2 = float(dfc["macd_hist"].iloc[-2])
        mh3 = float(dfc["macd_hist"].iloc[-3])

        eq  = 50
        det = {"ema21": 0, "ob_fvg": 0, "timing": 0, "rsi": 0, "bos": 0}
        bloqueado = False

        # 1. DISTÂNCIA EMA21
        dist = abs(c - e21) / atr if atr > 0 else 0
        if dist <= 0.5:
            eq += 10; det["ema21"] = 10
        elif dist <= 1.0:
            eq += 5;  det["ema21"] = 5
        elif dist <= 1.5:
            pass;     det["ema21"] = 0
        else:
            bloqueado = True  # > 1.5 ATR — entrada esticada
            eq -= 50; det["ema21"] = -50

        # 2. ZONA INSTITUCIONAL
        ob_pts = 0
        if ob_ok:
            dentro = (direcao=="LONG" and ob_low <= c <= ob_high*1.003) or \
                     (direcao=="SHORT" and ob_low*0.997 <= c <= ob_high)
            ob_pts = 15 if dentro else 5
        fvg_pts = 0
        try:
            for i in range(-3, -8, -1):
                v1 = dfc.iloc[i-1]; v3 = dfc.iloc[i+1]
                if direcao=="LONG" and float(v3["low"])>float(v1["high"]) and c<=float(v3["low"]):
                    fvg_pts = 10; break
                if direcao=="SHORT" and float(v1["low"])>float(v3["high"]) and c>=float(v3["high"]):
                    fvg_pts = 10; break
        except: pass
        zona = max(ob_pts, fvg_pts)
        eq += zona; det["ob_fvg"] = zona

        # 3. TIMING MACD
        cruzou = (mh2<=0 and mh>0) or (mh2>=0 and mh<0)
        acelerou = (mh>mh2>mh3 and mh>0) or (mh<mh2<mh3 and mh<0)
        if cruzou:
            eq += 10; det["timing"] = 10
        elif acelerou:
            eq += 5;  det["timing"] = 5

        # 4. RSI ZONA IDEAL
        if (direcao=="LONG" and 40<=rsi<=68) or (direcao=="SHORT" and 32<=rsi<=60):
            eq += 10; det["rsi"] = 10

        # 5. IDADE DO BOS
        bos_idade = self._bos_idade(df, direcao)
        if bos_idade <= 3:
            eq += 15; det["bos"] = 15
        elif bos_idade <= 6:
            eq += 5;  det["bos"] = 5
        elif bos_idade <= 10:
            eq -= 10; det["bos"] = -10
        else:
            bloqueado = True
            eq -= 20; det["bos"] = -20

        return max(0, min(100, eq)), det, bloqueado

    def _analisar_tf(self, symbol, tf="1h", tf_contexto=None):
        try:
            ctx  = tf_contexto or ("1h" if tf=="30m" else "4h")
            df   = self._calc(self._fetch(symbol, tf, limit=300))
            df4h = self._calc(self._fetch(symbol, ctx, limit=100))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"direcao":"—","rr":0,"rvol":0}

        dfc = df.iloc[:-1]; r = dfc.iloc[-1]
        c    = float(r["close"]); atr = float(r["atr"])
        e10  = float(r["ema10"]); e21 = float(r["ema21"])
        e50  = float(r["ema50"]); e200= float(r["ema200"])
        adx  = float(r["adx"]);   rsi = float(r["rsi"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        macd_h  = float(r["macd_hist"])
        macd_h2 = float(dfc["macd_hist"].iloc[-2])
        macd_h3 = float(dfc["macd_hist"].iloc[-3])
        macd_h4 = float(dfc["macd_hist"].iloc[-4])
        rsi2 = float(dfc["rsi"].iloc[-2])
        vwap = float(r["vwap"])
        sessao, peso_sessao = sessao_atual()

        motivos = []
        confirmacoes = []
        score = 0

        # BLOQUEIO 1: ADX
        if adx < 18:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"Mercado lateral ADX {adx:.1f}"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol}

        # BLOQUEIO 2: RSI extremo
        if rsi < 25:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"RSI {rsi:.0f} sobrevendido — bounce iminente"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol}
        if rsi > 75:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"RSI {rsi:.0f} sobrecomprado — pullback iminente"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol}

        # DIREÇÃO PELO MACD
        macd_cruzou_long  = any([macd_h2<=0 and macd_h>0, macd_h3<=0 and macd_h2>0, macd_h4<=0 and macd_h3>0])
        macd_cruzou_short = any([macd_h2>=0 and macd_h<0, macd_h3>=0 and macd_h2<0, macd_h4>=0 and macd_h3<0])
        macd_acel_long    = macd_h>0 and macd_h>macd_h2 and macd_h2>macd_h3
        macd_acel_short   = macd_h<0 and macd_h<macd_h2 and macd_h2<macd_h3

        if macd_cruzou_long:
            direcao = "LONG";  confirmacoes.append("🎯 MACD cruzou para cima"); score += 25
        elif macd_cruzou_short:
            direcao = "SHORT"; confirmacoes.append("🎯 MACD cruzou para baixo"); score += 25
        elif macd_acel_long:
            ratio = abs(macd_h/macd_h4) if macd_h4!=0 else 99
            if ratio > 6.0:
                return {"symbol":symbol,"aprovado":False,"score":0,
                        "motivos_rejeicao":["MACD acelerou demais — atrasado"],"timeframe":tf,"direcao":"LONG","rr":0,"rvol":rvol}
            direcao = "LONG";  confirmacoes.append("MACD acelerando ↑"); score += 15
        elif macd_acel_short:
            ratio = abs(macd_h/macd_h4) if macd_h4!=0 else 99
            if ratio > 6.0:
                return {"symbol":symbol,"aprovado":False,"score":0,
                        "motivos_rejeicao":["MACD acelerou demais — atrasado"],"timeframe":tf,"direcao":"SHORT","rr":0,"rvol":rvol}
            direcao = "SHORT"; confirmacoes.append("MACD acelerando ↓"); score += 15
        else:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["MACD sem direção"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol}

        # EMA alinhada com direção
        if direcao=="LONG" and e10 < e21:
            motivos.append("EMA10 < EMA21 — contra LONG")
        elif direcao=="SHORT" and e10 > e21:
            motivos.append("EMA10 > EMA21 — contra SHORT")
        else:
            if (e10>e21>e50>e200 and direcao=="LONG") or (e10<e21<e50<e200 and direcao=="SHORT"):
                confirmacoes.append("EMAs 4 alinhadas"); score += 15
            elif (e10>e21>e50 and direcao=="LONG") or (e10<e21<e50 and direcao=="SHORT"):
                confirmacoes.append("EMAs 3 alinhadas"); score += 10
            else:
                confirmacoes.append("EMA10/21 ok"); score += 5

        # LIQUIDEZ / BOS / TENDÊNCIA
        sweep_ok = False
        lookback = dfc.iloc[-20:-6]
        swing_high = float(lookback["high"].max())
        swing_low  = float(lookback["low"].min())
        for i in range(-6, -1):
            vela = dfc.iloc[i]
            hv=float(vela["high"]); lv=float(vela["low"]); cv=float(vela["close"])
            if direcao=="LONG" and lv < swing_low*1.001 and cv > swing_low: sweep_ok=True
            if direcao=="SHORT" and hv > swing_high*0.999 and cv < swing_high: sweep_ok=True

        highs = float(dfc["high"].iloc[-10:-2].max())
        lows  = float(dfc["low"].iloc[-10:-2].min())
        bos_ok = (c > highs) if direcao=="LONG" else (c < lows)
        tend_forte = (e10>e21>e50 and macd_h>0 and adx>22 and direcao=="LONG") or \
                     (e10<e21<e50 and macd_h<0 and adx>22 and direcao=="SHORT")

        if sweep_ok:
            confirmacoes.append("✅ Liquidez capturada"); score += 20
        elif bos_ok:
            confirmacoes.append("✅ BOS confirmado"); score += 15
        elif tend_forte:
            confirmacoes.append("✅ Tendência forte"); score += 10
        else:
            motivos.append("Sem BOS/CHoCH/tendência")

        # ORDER BLOCK
        try:
            ob_ok, ob_low, ob_high = self._detectar_ob(df, direcao)
            if ob_ok: confirmacoes.append("🏛 Order Block"); score += 15
        except:
            ob_ok, ob_low, ob_high = False, 0, 0

        # RSI
        if (rsi>rsi2 and rsi<68 and direcao=="LONG") or (rsi<rsi2 and rsi>32 and direcao=="SHORT"):
            confirmacoes.append(f"RSI {rsi:.0f} ok"); score += 8

        # VWAP
        if (c>vwap and direcao=="LONG") or (c<vwap and direcao=="SHORT"):
            confirmacoes.append("VWAP ok"); score += 5

        # VOLUME — RFC V3
        if rvol >= 6.0:
            confirmacoes.append(f"🔥 Volume Institucional RVOL {rvol:.2f}"); score += 20
        elif rvol >= 2.0:
            confirmacoes.append(f"🔥 Volume Institucional RVOL {rvol:.2f}"); score += 18
        elif rvol >= 1.5:
            confirmacoes.append(f"🔥 Volume Forte RVOL {rvol:.2f}"); score += 14
        elif rvol >= 1.2:
            confirmacoes.append(f"⚡ Volume Alto RVOL {rvol:.2f}"); score += 8
        elif rvol >= 1.0:
            confirmacoes.append(f"✅ Volume RVOL {rvol:.2f}"); score += 4
        elif rvol >= 0.8:
            confirmacoes.append(f"Volume RVOL {rvol:.2f}"); score -= 5
        else:
            motivos.append(f"Volume insuficiente RVOL {rvol:.2f}")

        # CONTEXTO SUPERIOR
        ctx_label = "H1" if tf=="30m" else "H4"
        r4h = df4h.iloc[-1]
        macd_ctx = float(r4h["macd_hist"])
        e21_ctx  = float(r4h["ema21"]); e50_ctx = float(r4h["ema50"])
        adx_ctx  = float(r4h["adx"])
        tend_ctx = e21_ctx > e50_ctx
        macd_ctx_ok = (macd_ctx>0 and direcao=="LONG") or (macd_ctx<0 and direcao=="SHORT")
        tend_ctx_ok = (tend_ctx and direcao=="LONG") or (not tend_ctx and direcao=="SHORT")

        if not tend_ctx_ok and adx_ctx > 28:
            motivos.append(f"❌ {ctx_label} contra tendência forte")
        elif macd_ctx_ok and tend_ctx_ok:
            confirmacoes.append(f"✅ {ctx_label} MACD+EMA confirmando"); score += 18
        elif tend_ctx_ok:
            confirmacoes.append(f"{ctx_label} tendência ok"); score += 8

        # SESSÃO
        if peso_sessao == 100:
            confirmacoes.append(f"🕐 {sessao}"); score += 5
        elif peso_sessao >= 85:
            confirmacoes.append(f"🕐 {sessao}"); score += 3

        score = min(score, 100)

        # NÍVEIS
        if direcao == "LONG":
            stop_base = ob_low if ob_ok else float(dfc["low"].iloc[-6:].min())
            stop = round(stop_base - atr*0.1, 6)
            if abs(c-stop)/c > 0.06: stop = round(c*0.95, 6)
            risco = abs(c-stop)
            tp1   = round(c + risco*2.0, 6)
            tp2   = round(c + risco*3.5, 6)
            be    = round(c + risco*1.0, 6)
            if tp1 > c*1.12: tp1 = round(c*1.08, 6)
            if tp2 > c*1.20: tp2 = round(c*1.15, 6)
        else:
            stop_base = ob_high if ob_ok else float(dfc["high"].iloc[-6:].max())
            stop = round(stop_base + atr*0.1, 6)
            if abs(stop-c)/c > 0.06: stop = round(c*1.06, 6)
            risco = abs(stop-c)
            tp1   = round(c - risco*2.0, 6)
            tp2   = round(c - risco*3.5, 6)
            be    = round(c - risco*1.0, 6)
            if tp1 < c*0.88 or tp1 <= 0: tp1 = round(c*0.92, 6)
            if tp2 < c*0.82 or tp2 <= 0: tp2 = round(c*0.88, 6)

        entrada = c
        rr = round(abs(tp2-c)/abs(stop-c), 2) if stop != c else 0

        # ENTRY QUALITY V3
        try:
            eq, eq_det, eq_bloqueado = self._entry_quality(df, direcao, ob_ok, ob_low, ob_high)
        except:
            eq, eq_det, eq_bloqueado = 50, {"ema21":0,"ob_fvg":0,"timing":0,"rsi":0,"bos":0}, False

        if eq_bloqueado:
            motivos.append(f"EQ bloqueado — EMA21 muito distante ou BOS antigo (>{10} velas)")

        # OURO: score>=85, EQ>=85, RVOL>=1.5, H1/H4, BOS recente
        ouro_ok = (
            score >= 85 and eq >= 85 and rvol >= 1.5 and
            abs(c-e21)/atr <= 1.0 and
            any("H1" in x or "H4" in x for x in confirmacoes) and
            any("BOS" in x or "Liquidez" in x or "Tendência forte" in x for x in confirmacoes)
        )
        # PRATA: score>=75, EQ>=75, RVOL>=1.0
        prata_ok = score >= 75 and eq >= 75 and rvol >= 1.0

        # CHECAGEM FINAL
        if score < 75:   motivos.append(f"Score {score} < 75")
        if rr < 2.0:     motivos.append(f"RR {rr} < 2.0")
        if rvol < 1.0:   motivos.append(f"RVOL {rvol:.2f} < 1.0")
        if not (ouro_ok or prata_ok): motivos.append(f"EQ {eq}/100 insuficiente para tier")

        aprovado = len(motivos) == 0

        if ouro_ok and aprovado:    tier = "OURO"
        elif prata_ok and aprovado: tier = "PRATA"
        else:                       tier = "ABAIXO"

        conv = {"OURO":"ALTA ✅","PRATA":"BOA ⚡"}.get(tier,"—")

        if tier=="OURO" and sweep_ok:    prioridade = "🔥 LIQUIDEZ + REVERSÃO"
        elif tier=="OURO" and bos_ok:    prioridade = "🔥 BOS + CONTINUAÇÃO"
        elif tier=="OURO":               prioridade = "🔥 INSTITUCIONAL OURO"
        elif tier=="PRATA" and sweep_ok: prioridade = "⭐ REVERSÃO PRATA"
        elif tier=="PRATA":              prioridade = "⭐ ALTA QUALIDADE"
        else:                            prioridade = ""

        tem_liq = sweep_ok or bos_ok
        if direcao=="LONG":
            regime_label = "Reversão ↗" if tem_liq else "Tendência Alta ↑" if e10>e21>e50 else "Reversão ↗"
        else:
            regime_label = "Reversão ↘" if tem_liq else "Tendência Baixa ↓" if e10<e21<e50 else "Reversão ↘"

        gb_risco = round(BANCA * RISCO_PCT / 100, 2)
        dist = abs(c-stop)/c if c else 0.01
        pos  = round(min(gb_risco/dist, BANCA*3), 2) if dist > 0 else 0
        alav = 20 if tier=="OURO" else 15

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "setup_nome":       "SMC",
            "regime":           regime_label,
            "direcao":          direcao,
            "score":            score,
            "entry_quality":    eq,
            "eq_detalhes":      eq_det,
            "tier":             tier,
            "conviccao":        conv,
            "prioridade":       prioridade,
            "entrada":          entrada,
            "stop":             stop,
            "tp1":              tp1,
            "tp2":              tp2,
            "be":               be,
            "rr":               rr,
            "adx":              adx,
            "rsi":              rsi,
            "atr":              atr,
            "rvol":             rvol,
            "ema21":            e21,
            "vwap":             vwap,
            "sessao":           sessao,
            "confirmacoes_smc": confirmacoes,
            "confluencia":      len(confirmacoes),
            "motivos_rejeicao": motivos,
            "o_que_falta":      motivos,
            "timeframe":        tf,
            "tf_contexto":      ctx_label,
            "preco_atual":      entrada,
            "capital":          BANCA,
            "posicao":          pos,
            "risco_usdt":       gb_risco,
            "alavancagem":      alav,
            "banca":            BANCA,
        }

    def analisar(self, symbol, timeframe=None):
        pares = [("30m","1h"), ("1h","4h")]
        if timeframe:
            return self._analisar_tf(symbol, timeframe)
        resultados = []
        for tf, ctx in pares:
            try:
                r = self._analisar_tf(symbol, tf, tf_contexto=ctx)
                resultados.append(r)
            except: pass
        if not resultados:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["Erro"],"timeframe":"—","direcao":"—","rr":0,"rvol":0}
        aprovados = [r for r in resultados if r.get("aprovado")]
        if aprovados:
            return max(aprovados, key=lambda x: x["score"])
        return max(resultados, key=lambda x: x["score"])

    def analisar_tf(self, symbol, tf):
        return self._analisar_tf(symbol, tf)

    def obter_regime(self, symbol):
        df = self._calc(self._fetch(symbol, "1h"))
        r  = df.iloc[-1]
        return {"regime":"SMC_V3","adx":float(r["adx"]),"atr":float(r["atr"])}
