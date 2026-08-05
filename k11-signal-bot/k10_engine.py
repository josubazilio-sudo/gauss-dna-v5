"""
K11 Engine — Versão Definitiva
Entrada só quando TUDO estiver alinhado:
1. Tendência clara (ADX >= 20)
2. MACD cruzando na direção
3. Liquidez capturada OU tendência forte
4. Volume confirmado (RVOL >= 0.7)
5. Contexto H1/H4 confirmando
6. Timing bom (não entrar atrasado)
7. RR >= 2.0
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
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

    def _detectar_sweep(self, df, direcao):
        dfc = df.iloc[:-1]
        lookback = dfc.iloc[-20:-6]
        swing_high = float(lookback["high"].max())
        swing_low  = float(lookback["low"].min())
        for i in range(-6, -1):
            vela = dfc.iloc[i]
            h_v = float(vela["high"]); l_v = float(vela["low"]); c_v = float(vela["close"])
            if direcao == "LONG" and l_v < swing_low * 1.001 and c_v > swing_low:
                return True
            if direcao == "SHORT" and h_v > swing_high * 0.999 and c_v < swing_high:
                return True
        return False

    def _detectar_ob(self, df, direcao):
        dfc = df.iloc[:-1]
        atr = float(dfc["atr"].iloc[-1])
        c_atual = float(dfc["close"].iloc[-1])
        for i in range(-2, -12, -1):
            try:
                vela = dfc.iloc[i]; prox = dfc.iloc[i+1]
                o=float(vela["open"]); cv=float(vela["close"])
                rvol_p = float(prox["rvol"]) if not np.isnan(prox["rvol"]) else 0
                mov_forte = abs(float(prox["close"])-float(prox["open"])) > atr*0.5
                if direcao=="LONG" and cv<o and float(prox["close"])>float(prox["open"]) and rvol_p>=1.0 and mov_forte:
                    if float(vela["low"]) <= c_atual <= float(vela["high"])*1.005:
                        return True, float(vela["low"]), float(vela["high"])
                if direcao=="SHORT" and cv>o and float(prox["close"])<float(prox["open"]) and rvol_p>=1.0 and mov_forte:
                    if float(vela["low"])*0.995 <= c_atual <= float(vela["high"]):
                        return True, float(vela["low"]), float(vela["high"])
            except: continue
        return False, 0, 0

    def _timing_score(self, df, direcao, stop, tp1):
        try:
            dfc = df.iloc[:-1]
            r   = dfc.iloc[-1]
            atr = float(r["atr"]); rsi = float(r["rsi"])
            e21 = float(r["ema21"]); c = float(r["close"])
            macd_hist = dfc["macd_hist"]
            score = 100

            # Velas desde cruzamento
            velas = 0
            for i in range(-1, -10, -1):
                h1 = float(macd_hist.iloc[i]); h2 = float(macd_hist.iloc[i-1])
                if direcao=="LONG" and h2<=0 and h1>0: break
                if direcao=="SHORT" and h2>=0 and h1<0: break
                velas += 1

            if   velas == 0: pass
            elif velas <= 2: score -= 5
            elif velas <= 4: score -= 20
            else:            score -= 40

            # Movimento realizado
            if tp1 != stop and stop != c:
                realizado = abs(c-stop)/abs(tp1-stop)*100 if abs(tp1-stop)>0 else 0
                if   realizado <= 15: pass
                elif realizado <= 30: score -= 15
                elif realizado <= 50: score -= 30
                else:                 score -= 50

            # Distância EMA21
            dist = abs(c-e21)/atr if atr>0 else 0
            if   dist <= 0.5: pass
            elif dist <= 1.0: score -= 10
            elif dist <= 1.5: score -= 20
            else:             score -= 35

            # RSI espaço
            if direcao=="LONG":
                esp = 70-rsi
                if esp < 10: score -= 25
                elif esp < 20: score -= 10
            else:
                esp = rsi-30
                if esp < 10: score -= 25
                elif esp < 20: score -= 10

            return max(0, min(100, score))
        except:
            return 70

    def _analisar_tf(self, symbol, tf="1h", tf_contexto=None):
        try:
            ctx  = tf_contexto or ("1h" if tf=="30m" else "4h")
            df   = self._calc(self._fetch(symbol, tf, limit=300))
            df4h = self._calc(self._fetch(symbol, ctx, limit=100))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"direcao":"—","rr":0,"rvol":0}

        dfc = df.iloc[:-1]
        r   = dfc.iloc[-1]

        c    = float(r["close"]); atr = float(r["atr"])
        e10  = float(r["ema10"]); e21 = float(r["ema21"])
        e50  = float(r["ema50"]); e200= float(r["ema200"])
        adx  = float(r["adx"]);   rsi = float(r["rsi"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        macd_h  = float(r["macd_hist"])
        macd_h2 = float(dfc["macd_hist"].iloc[-2])
        macd_h3 = float(dfc["macd_hist"].iloc[-3])
        macd_h4 = float(dfc["macd_hist"].iloc[-4])
        macd_h5 = float(dfc["macd_hist"].iloc[-5])
        rsi2 = float(dfc["rsi"].iloc[-2])
        vwap = float(r["vwap"])
        sessao, peso_sessao = sessao_atual()

        motivos = []
        confirmacoes = []
        score = 0

        # ── FILTRO 1: ADX — mercado lateral bloqueado ─────────────────────────
        if adx < 18:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"Mercado lateral ADX {adx:.1f} < 18"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol}

        # ── FILTRO 2: MACD — cruzamento ou aceleração recente ────────────────
        macd_cruzou_long  = any([
            macd_h2<=0 and macd_h>0,
            macd_h3<=0 and macd_h2>0,
            macd_h4<=0 and macd_h3>0,
        ])
        macd_cruzou_short = any([
            macd_h2>=0 and macd_h<0,
            macd_h3>=0 and macd_h2<0,
            macd_h4>=0 and macd_h3<0,
        ])
        macd_acel_long  = macd_h>0 and macd_h>macd_h2 and macd_h2>macd_h3
        macd_acel_short = macd_h<0 and macd_h<macd_h2 and macd_h2<macd_h3

        if macd_cruzou_long:
            direcao = "LONG"; confirmacoes.append("🎯 MACD cruzou para cima"); score += 30
        elif macd_cruzou_short:
            direcao = "SHORT"; confirmacoes.append("🎯 MACD cruzou para baixo"); score += 30
        elif macd_acel_long:
            # Não entrar se acelerou demais (ratio > 6x)
            ratio = abs(macd_h/macd_h4) if macd_h4 != 0 else 99
            if ratio > 6.0:
                return {"symbol":symbol,"aprovado":False,"score":0,
                        "motivos_rejeicao":["MACD acelerou demais — atrasado"],"timeframe":tf,"direcao":"LONG","rr":0,"rvol":rvol}
            direcao = "LONG"; confirmacoes.append("MACD acelerando ↑"); score += 18
        elif macd_acel_short:
            ratio = abs(macd_h/macd_h4) if macd_h4 != 0 else 99
            if ratio > 6.0:
                return {"symbol":symbol,"aprovado":False,"score":0,
                        "motivos_rejeicao":["MACD acelerou demais — atrasado"],"timeframe":tf,"direcao":"SHORT","rr":0,"rvol":rvol}
            direcao = "SHORT"; confirmacoes.append("MACD acelerando ↓"); score += 18
        else:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["MACD sem direção"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol}

        # ── FILTRO 3: LIQUIDEZ / TENDÊNCIA ────────────────────────────────────
        sweep_ok = self._detectar_sweep(df, direcao)
        highs = float(dfc["high"].iloc[-10:-2].max())
        lows  = float(dfc["low"].iloc[-10:-2].min())
        bos_ok = (c > highs) if direcao=="LONG" else (c < lows)
        tend_forte = (
            (e10>e21>e50 and macd_h>0 and adx>22 and direcao=="LONG") or
            (e10<e21<e50 and macd_h<0 and adx>22 and direcao=="SHORT")
        )

        if sweep_ok:
            confirmacoes.append("✅ Liquidez capturada"); score += 25
        elif bos_ok and rvol >= 0.7:
            confirmacoes.append("✅ BOS confirmado"); score += 15
        elif tend_forte:
            confirmacoes.append("✅ Tendência forte confirmada"); score += 12
        else:
            motivos.append("Sem liquidez/BOS/tendência forte")

        # ── FILTRO 4: VOLUME ──────────────────────────────────────────────────
        if rvol >= 1.5:
            confirmacoes.append(f"🔥 RVOL {rvol:.2f}"); score += 15
        elif rvol >= 0.8:
            confirmacoes.append(f"Volume RVOL {rvol:.2f}"); score += 8
        elif rvol >= 0.6:
            confirmacoes.append(f"Volume RVOL {rvol:.2f}"); score += 4
        else:
            motivos.append(f"Volume insuficiente RVOL {rvol:.2f}")

        # ── ORDER BLOCK ───────────────────────────────────────────────────────
        try:
            ob_ok, ob_low, ob_high = self._detectar_ob(df, direcao)
            if ob_ok:
                confirmacoes.append("🏛 Order Block"); score += 15
        except:
            ob_ok, ob_low, ob_high = False, 0, 0

        # ── EMAs ──────────────────────────────────────────────────────────────
        if (e10>e21>e50>e200 and direcao=="LONG") or (e10<e21<e50<e200 and direcao=="SHORT"):
            confirmacoes.append("EMAs 4 alinhadas"); score += 12
        elif (e10>e21 and direcao=="LONG") or (e10<e21 and direcao=="SHORT"):
            confirmacoes.append("EMA10/21 ok"); score += 6

        # ── RSI ───────────────────────────────────────────────────────────────
        rsi_ok = (rsi>rsi2 and rsi<68 and direcao=="LONG") or (rsi<rsi2 and rsi>32 and direcao=="SHORT")
        if rsi_ok:
            confirmacoes.append(f"RSI {rsi:.0f} ok"); score += 8

        # ── VWAP ──────────────────────────────────────────────────────────────
        if (c>vwap and direcao=="LONG") or (c<vwap and direcao=="SHORT"):
            confirmacoes.append("VWAP ok"); score += 5

        # ── CONTEXTO SUPERIOR ─────────────────────────────────────────────────
        ctx_label = "H1" if tf=="30m" else "H4"
        r4h = df4h.iloc[-1]
        macd_ctx = float(r4h["macd_hist"])
        e21_ctx  = float(r4h["ema21"]); e50_ctx = float(r4h["ema50"])
        tend_ctx = e21_ctx > e50_ctx
        ctx_ok = (tend_ctx and macd_ctx>0 and direcao=="LONG") or (not tend_ctx and macd_ctx<0 and direcao=="SHORT")
        ctx_tend = (tend_ctx and direcao=="LONG") or (not tend_ctx and direcao=="SHORT")

        if ctx_ok:
            confirmacoes.append(f"✅ {ctx_label} MACD+EMA confirmando"); score += 15
        elif ctx_tend:
            confirmacoes.append(f"{ctx_label} tendência ok"); score += 5
        else:
            adx_ctx = float(r4h["adx"])
            if adx_ctx > 28:
                motivos.append(f"{ctx_label} contra tendência forte")

        # ── SESSÃO ────────────────────────────────────────────────────────────
        if peso_sessao == 100:
            confirmacoes.append(f"🕐 {sessao}"); score += 8
        elif peso_sessao >= 85:
            confirmacoes.append(f"🕐 {sessao}"); score += 4

        score = min(score, 100)

        # ── NÍVEIS ────────────────────────────────────────────────────────────
        if direcao == "LONG":
            stop_base = ob_low if ob_ok else float(dfc["low"].iloc[-6:].min())
            stop = round(stop_base - atr*0.1, 6)
            if abs(c-stop)/c > 0.06: stop = round(c*0.95, 6)
            risco = abs(c-stop)
            tp1   = round(c + risco*2.5, 6)
            if tp1 > c*1.12: tp1 = round(c*1.10, 6)
        else:
            stop_base = ob_high if ob_ok else float(dfc["high"].iloc[-6:].max())
            stop = round(stop_base + atr*0.1, 6)
            if abs(stop-c)/c > 0.06: stop = round(c*1.06, 6)
            risco = abs(stop-c)
            tp1   = round(c - risco*2.5, 6)
            if tp1 < c*0.88 or tp1 <= 0: tp1 = round(c*0.90, 6)

        entrada = c
        rr = round(abs(tp1-c)/abs(stop-c), 2) if stop != c else 0

        # ── TIMING ────────────────────────────────────────────────────────────
        score_timing = self._timing_score(df, direcao, stop, tp1)
        if score_timing < 40:
            motivos.append(f"⏱ Timing {score_timing}/100 — entrada tardia")

        # ── CHECAGEM FINAL ────────────────────────────────────────────────────
        if score < 70:  motivos.append(f"Score {score} < 70")
        if rr < 2.0:    motivos.append(f"RR {rr} < 2.0")

        aprovado = len(motivos) == 0

        if score >= 85:   tier = "OURO"
        elif score >= 75: tier = "PRATA"
        elif score >= 70: tier = "BRONZE"
        else:             tier = "ABAIXO"

        conv = {"OURO":"ALTA ✅","PRATA":"BOA ⚡","BRONZE":"MODERADA 🔶"}.get(tier,"MODERADA 🔶")

        if score >= 90 and rvol >= 1.5:   prioridade = "🔥 INSTITUCIONAL"
        elif score >= 85:                  prioridade = "⭐ ALTA QUALIDADE"
        else:                              prioridade = ""

        regime_label = "Tendência Alta ↑" if e10>e21>e50 else \
                       "Tendência Baixa ↓" if e10<e21<e50 else \
                       "Reversão ↗" if direcao=="LONG" else "Reversão ↘"

        gb_risco = round(BANCA * RISCO_PCT / 100, 2)
        dist = abs(c-stop)/c if c else 0.01
        pos  = round(min(gb_risco/dist, BANCA*3), 2) if dist > 0 else 0
        alav = 20 if score>=85 else 15 if score>=75 else 10

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "setup_nome":       "SMC",
            "regime":           regime_label,
            "direcao":          direcao,
            "score":            score,
            "tier":             tier,
            "conviccao":        conv,
            "prioridade":       prioridade,
            "entrada":          entrada,
            "stop":             stop,
            "tp1":              tp1,
            "tp2":              tp1,
            "rr":               rr,
            "adx":              adx,
            "rsi":              rsi,
            "atr":              atr,
            "rvol":             rvol,
            "ema21":            e21,
            "vwap":             vwap,
            "sessao":           sessao,
            "score_timing":     score_timing,
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
        return {"regime":"SMC","adx":float(r["adx"]),"atr":float(r["atr"])}
