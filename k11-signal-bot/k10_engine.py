"""
K11 Engine — Estratégia Completa
LONG: Captura liquidez + CHoCH + MACD positivo + RSI subindo + EMAs alinhadas + Volume + RR
SHORT: Tudo ao contrário
"""

import ccxt
import pandas as pd
import numpy as np
from config import BANCA, RISCO_PCT


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
        return df

    def _analisar_tf(self, symbol, tf="1h"):
        try:
            df   = self._calc(self._fetch(symbol, tf, limit=300))
            df4h = self._calc(self._fetch(symbol, "4h", limit=100))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"direcao":"—","rr":0,"rvol":0}

        # Usar velas fechadas
        dfc  = df.iloc[:-1]
        r    = dfc.iloc[-1]
        r2   = dfc.iloc[-2]
        r3   = dfc.iloc[-3]

        c    = float(r["close"])
        o    = float(r["open"])
        h_r  = float(r["high"])
        l_r  = float(r["low"])
        atr  = float(r["atr"])
        e10  = float(r["ema10"])
        e21  = float(r["ema21"])
        e50  = float(r["ema50"])
        e200 = float(r["ema200"])
        adx  = float(r["adx"])
        rsi  = float(r["rsi"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        macd_h  = float(r["macd_hist"])
        macd_h2 = float(dfc["macd_hist"].iloc[-3])
        macd_h3 = float(dfc["macd_hist"].iloc[-4])
        rsi2 = float(dfc["rsi"].iloc[-3])
        vol_atual = float(dfc["volume"].iloc[-1])
        vol_ma    = float(r["vol_ma"]) if not np.isnan(r["vol_ma"]) else 1

        corpo = abs(c-o); total = h_r-l_r
        sombra_inf = min(o,c)-l_r
        sombra_sup = h_r-max(o,c)

        # Swing points últimos 20 candles
        lookback = dfc.iloc[-20:-3]
        swing_high = float(lookback["high"].max())
        swing_low  = float(lookback["low"].min())

        motivos = []
        confirmacoes = []
        score = 0

        # ── DETECTAR DIREÇÃO ──────────────────────────────────────────────────
        # LONG: MACD positivo OU virando para cima
        macd_long  = macd_h > 0 or (macd_h > macd_h2 and macd_h > macd_h3)
        # SHORT: MACD negativo OU virando para baixo
        macd_short = macd_h < 0 or (macd_h < macd_h2 and macd_h < macd_h3)

        rsi_long  = rsi > rsi2 and rsi < 68
        rsi_short = rsi < rsi2 and rsi > 32

        ema_long  = e10 > e21 and e50 > e200
        ema_short = e10 < e21 and e50 < e200

        # Decidir direção pela confluência
        pts_long  = sum([macd_long, rsi_long, ema_long])
        pts_short = sum([macd_short, rsi_short, ema_short])

        if pts_long >= 2 and pts_long > pts_short:
            direcao = "LONG"
        elif pts_short >= 2 and pts_short > pts_long:
            direcao = "SHORT"
        else:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["Sem direção clara — MACD/RSI/EMA conflitantes"],
                    "timeframe":tf,"direcao":"—","rr":0,"rvol":rvol}

        # ── 1. MACD ───────────────────────────────────────────────────────────
        if direcao == "LONG":
            if macd_h > 0 and macd_h > macd_h2:
                confirmacoes.append("MACD positivo e acelerando")
                score += 20
            elif macd_h > macd_h2:
                confirmacoes.append("MACD virando para cima")
                score += 12
            else:
                motivos.append(f"MACD fraco para LONG ({macd_h:.4f})")
        else:
            if macd_h < 0 and macd_h < macd_h2:
                confirmacoes.append("MACD negativo e acelerando")
                score += 20
            elif macd_h < macd_h2:
                confirmacoes.append("MACD virando para baixo")
                score += 12
            else:
                motivos.append(f"MACD fraco para SHORT ({macd_h:.4f})")

        # ── 2. RSI ────────────────────────────────────────────────────────────
        if direcao == "LONG":
            if rsi_long and 40 <= rsi <= 65:
                confirmacoes.append(f"RSI {rsi:.0f} subindo zona favorável")
                score += 15
            elif rsi_long:
                confirmacoes.append(f"RSI {rsi:.0f} subindo")
                score += 8
            else:
                motivos.append(f"RSI {rsi:.0f} não favorável para LONG")
        else:
            if rsi_short and 35 <= rsi <= 60:
                confirmacoes.append(f"RSI {rsi:.0f} caindo zona favorável")
                score += 15
            elif rsi_short:
                confirmacoes.append(f"RSI {rsi:.0f} caindo")
                score += 8
            else:
                motivos.append(f"RSI {rsi:.0f} não favorável para SHORT")

        # ── 3. MÉDIAS MÓVEIS ──────────────────────────────────────────────────
        if direcao == "LONG":
            if e10 > e21 > e50 > e200:
                confirmacoes.append("EMAs 10>21>50>200 alinhadas")
                score += 15
            elif e10 > e21 and e50 > e200:
                confirmacoes.append("EMAs alinhadas")
                score += 10
            elif e10 > e21:
                confirmacoes.append("EMA10 > EMA21")
                score += 5
        else:
            if e10 < e21 < e50 < e200:
                confirmacoes.append("EMAs 10<21<50<200 alinhadas")
                score += 15
            elif e10 < e21 and e50 < e200:
                confirmacoes.append("EMAs alinhadas")
                score += 10
            elif e10 < e21:
                confirmacoes.append("EMA10 < EMA21")
                score += 5

        # ── 4. CAPTURA DE LIQUIDEZ ────────────────────────────────────────────
        if direcao == "LONG":
            # Sombra inferior longa + fechou acima = sweep do fundo
            sweep = sombra_inf > atr * 0.3 and c > o
            # OU preço furou abaixo do swing low e voltou
            sweep2 = l_r < swing_low * 1.001 and c > swing_low
            if sweep or sweep2:
                confirmacoes.append("Captura de liquidez ↓ (sweep do fundo)")
                score += 20
        else:
            # Sombra superior longa + fechou abaixo = sweep do topo
            sweep = sombra_sup > atr * 0.3 and c < o
            sweep2 = h_r > swing_high * 0.999 and c < swing_high
            if sweep or sweep2:
                confirmacoes.append("Captura de liquidez ↑ (sweep do topo)")
                score += 20

        # ── 5. PULLBACK NA ZONA ───────────────────────────────────────────────
        dist_ema21 = abs(c - e21) / atr if atr > 0 else 99
        if dist_ema21 <= 1.5:
            confirmacoes.append(f"Pullback na EMA21")
            score += 10

        # ── 6. VOLUME ─────────────────────────────────────────────────────────
        if rvol >= 1.5:
            confirmacoes.append(f"Volume institucional RVOL {rvol:.2f}")
            score += 15
        elif rvol >= 0.8:
            confirmacoes.append(f"Volume RVOL {rvol:.2f}")
            score += 8
        elif rvol < 0.5:
            motivos.append(f"Volume ausente RVOL {rvol:.2f}")

        # ── 7. CHoCH (bônus) ──────────────────────────────────────────────────
        if direcao == "LONG":
            choch = c > swing_high * 0.998
            if choch:
                confirmacoes.append("CHoCH confirmado")
                score += 10
        else:
            choch = c < swing_low * 1.002
            if choch:
                confirmacoes.append("CHoCH confirmado")
                score += 10

        # ── H4 contexto ───────────────────────────────────────────────────────
        r4h    = df4h.iloc[-1]
        adx_4h = float(r4h["adx"])
        tend_h4= float(r4h["ema21"]) > float(r4h["ema50"])
        macd_h4= float(r4h["macd_hist"])
        h4_ok  = (tend_h4 and direcao=="LONG" and macd_h4 > 0) or \
                 (not tend_h4 and direcao=="SHORT" and macd_h4 < 0)
        if h4_ok:
            confirmacoes.append("H4 confirmando")
            score += 10
        elif adx_4h > 35:
            motivos.append(f"H4 tendência forte contra ADX={adx_4h:.0f}")

        score = min(score, 100)

        # ── NÍVEIS ────────────────────────────────────────────────────────────
        if direcao == "LONG":
            stop = round(float(dfc["low"].iloc[-5:].min()) - atr*0.15, 6)
            if abs(c-stop)/c > 0.05: stop = round(c*0.95, 6)
            risco = abs(c-stop)
            tp1   = round(c + risco*2.5, 6)
            if tp1 > c*1.12: tp1 = round(c*1.10, 6)
        else:
            stop = round(float(dfc["high"].iloc[-5:].max()) + atr*0.15, 6)
            if abs(stop-c)/c > 0.05: stop = round(c*1.05, 6)
            risco = abs(stop-c)
            tp1   = round(c - risco*2.5, 6)
            if tp1 < c*0.88 or tp1 <= 0: tp1 = round(c*0.90, 6)

        rr = round(abs(tp1-c)/abs(stop-c), 2) if stop != c else 0

        # ── CHECAGEM FINAL ────────────────────────────────────────────────────
        if score < 60:   motivos.append(f"Score {score} < 60")
        if rr < 2.0:     motivos.append(f"RR {rr} < 2.0")
        if len(confirmacoes) < 3: motivos.append(f"Confluência fraca — {len(confirmacoes)} confirmações")

        aprovado = len(motivos) == 0

        if score >= 85:   tier = "OURO"
        elif score >= 75: tier = "PRATA"
        elif score >= 65: tier = "BRONZE"
        else:             tier = "ABAIXO"

        conv = {"OURO":"ALTA ✅","PRATA":"BOA ⚡","BRONZE":"MODERADA 🔶"}.get(tier,"MODERADA 🔶")

        if score >= 85 and rvol >= 1.5:   prioridade = "🔥 INSTITUCIONAL"
        elif score >= 80:                  prioridade = "⭐ ALTA QUALIDADE"
        else:                              prioridade = ""

        regime_label = "Tendência Alta ↑" if direcao=="LONG" and e10>e21>e50 else \
                       "Tendência Baixa ↓" if direcao=="SHORT" and e10<e21<e50 else \
                       "Reversão ↗" if direcao=="LONG" else "Reversão ↘"

        gb_risco = round(BANCA * RISCO_PCT / 100, 2)
        dist = abs(c-stop)/c if c else 0.01
        pos  = round(min(gb_risco/dist, BANCA*3), 2) if dist > 0 else 0
        alav = 20 if score>=85 else 15 if score>=75 else 10

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "setup_nome":       "K11",
            "regime":           regime_label,
            "direcao":          direcao,
            "score":            score,
            "tier":             tier,
            "conviccao":        conv,
            "prioridade":       prioridade,
            "entrada":          c,
            "stop":             stop,
            "tp1":              tp1,
            "tp2":              tp1,
            "rr":               rr,
            "adx":              adx,
            "rsi":              rsi,
            "atr":              atr,
            "rvol":             rvol,
            "ema21":            e21,
            "confirmacoes_smc": confirmacoes,
            "confluencia":      len(confirmacoes),
            "motivos_rejeicao": motivos,
            "o_que_falta":      motivos,
            "timeframe":        tf,
            "preco_atual":      c,
            "capital":          BANCA,
            "posicao":          pos,
            "risco_usdt":       gb_risco,
            "alavancagem":      alav,
            "banca":            BANCA,
        }

    def analisar(self, symbol, timeframe=None):
        tfs = [timeframe] if timeframe else ["30m","1h"]
        resultados = [self._analisar_tf(symbol, tf) for tf in tfs]
        aprovados  = [r for r in resultados if r.get("aprovado")]
        if aprovados:
            return max(aprovados, key=lambda x: x["score"])
        return max(resultados, key=lambda x: x["score"])

    def analisar_tf(self, symbol, tf):
        return self._analisar_tf(symbol, tf)

    def obter_regime(self, symbol):
        df = self._calc(self._fetch(symbol, "1h"))
        r  = df.iloc[-1]
        return {"regime":"K11","adx":float(r["adx"]),"atr":float(r["atr"])}
