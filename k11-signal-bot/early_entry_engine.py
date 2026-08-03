"""
K11 Early Entry Engine V1 — SHADOW MODE
Captura início do movimento com qualidade institucional.
Roda em paralelo ao engine principal — não envia sinal, só registra.
"""

import ccxt
import pandas as pd
import numpy as np
from config import BANCA, RISCO_PCT, ALAVANCAGEM_POR_REGIME


class EarlyEntryEngine:
    """
    Shadow Mode: analisa mas não envia sinal ao Telegram.
    Compara com engine principal para validar win rate.
    """

    SHADOW_MODE = False  # True = só registra, False = envia sinal

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
            raise RuntimeError(f"Fetch {symbol} {tf}: {e}")

    def _calc(self, df):
        c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
        for p in [10, 21, 50, 200]:
            df[f"ema{p}"] = c.ewm(span=p, adjust=False).mean()
        df["vwap"] = (v*(h+l+c)/3).cumsum()/v.cumsum()
        tr = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
        df["atr"] = tr.ewm(span=14,adjust=False).mean()
        dm_p = h.diff().clip(lower=0).where(h.diff()>(-l.diff()),0.0)
        dm_n = (-l.diff()).clip(lower=0).where((-l.diff())>h.diff(),0.0)
        atr14 = tr.ewm(span=14,adjust=False).mean()
        di_p  = 100*dm_p.ewm(span=14,adjust=False).mean()/atr14
        di_n  = 100*dm_n.ewm(span=14,adjust=False).mean()/atr14
        dx = 100*(di_p-di_n).abs()/(di_p+di_n).replace(0,np.nan)
        df["adx"] = dx.ewm(span=14,adjust=False).mean()
        delta = c.diff()
        gain  = delta.clip(lower=0).ewm(span=14,adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(span=14,adjust=False).mean()
        df["rsi"] = 100 - 100/(1+gain/loss.replace(0,np.nan))
        ema12 = c.ewm(span=12,adjust=False).mean()
        ema26 = c.ewm(span=26,adjust=False).mean()
        df["macd"]        = ema12-ema26
        df["macd_signal"] = df["macd"].ewm(span=9,adjust=False).mean()
        df["macd_hist"]   = df["macd"]-df["macd_signal"]
        vol_sma20 = v.rolling(20,min_periods=10).mean()
        df["vol_ma"] = vol_sma20
        vol_fechada = v.shift(1)
        df["rvol"] = (vol_fechada/vol_sma20.replace(0,np.nan)).clip(lower=0,upper=50)
        return df

    def analisar(self, symbol, timeframe=None):
        tfs = [timeframe] if timeframe else ["30m","1h"]
        resultados = [self._analisar_tf(symbol, tf) for tf in tfs]
        aprovados  = [r for r in resultados if r.get("aprovado")]
        if aprovados:
            return max(aprovados, key=lambda x: x["score"])
        return max(resultados, key=lambda x: x["score"])

    def _analisar_tf(self, symbol, tf="1h"):
        try:
            df   = self._calc(self._fetch(symbol, tf, limit=300))
            df4h = self._calc(self._fetch(symbol, "4h", limit=100))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"shadow":True}

        r    = df.iloc[-1]
        c    = float(r["close"])
        e10  = float(r["ema10"]); e21 = float(r["ema21"])
        e50  = float(r["ema50"]); e200= float(r["ema200"])
        adx  = float(r["adx"])
        rsi  = float(r["rsi"])
        atr  = float(r["atr"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        macd_h  = float(r["macd_hist"])
        macd_h2 = float(df["macd_hist"].iloc[-4])
        macd_h3 = float(df["macd_hist"].iloc[-3])

        # Direção pelo MACD
        direcao = "LONG" if macd_h > macd_h2 else "SHORT"

        # ── FILTROS EARLY ENTRY V1 ───────────────────────────────────────────

        motivos = []
        confirmacoes = []
        penalidade = 0

        # 1. EMA21 — não é bloqueio, permite até 1 ATR
        dist_ema21 = abs(c - e21) / atr if atr > 0 else 99
        if dist_ema21 <= 1.0:
            confirmacoes.append("Próximo EMA21")
        elif dist_ema21 > 2.5:
            motivos.append(f"Muito esticado da EMA21: {dist_ema21:.1f} ATR")

        # Tendência EMA50/200 alinhada (obrigatório)
        tend_ok = (e50 > e200) if direcao=="LONG" else (e50 < e200)
        if tend_ok:
            confirmacoes.append("EMA50/200 alinhadas")
        else:
            penalidade += 5  # penalidade, não bloqueio

        # 2. MACD — penalidade em vez de veto
        macd_favor = (macd_h > 0) if direcao=="LONG" else (macd_h < 0)
        macd_acel  = (macd_h > macd_h2) if direcao=="LONG" else (macd_h < macd_h2)
        macd_div_forte = (macd_h < 0 and macd_h < macd_h2 and macd_h < macd_h3) if direcao=="LONG" else                          (macd_h > 0 and macd_h > macd_h2 and macd_h > macd_h3)
        if macd_div_forte:
            motivos.append("Divergência MACD forte")
        elif not macd_favor:
            penalidade += 8  # penalidade -8
        else:
            if macd_acel: confirmacoes.append("MACD acelerando")
            else:         confirmacoes.append("MACD positivo")

        # 3. RSI
        rsi_ok = (rsi > float(df["rsi"].iloc[-4]) and rsi < 68) if direcao=="LONG" else                  (rsi < float(df["rsi"].iloc[-4]) and rsi > 32)
        if rsi_ok: confirmacoes.append("RSI alinhado")

        # 4. Volume
        vol_cresc = float(df["volume"].iloc[-1]) > float(df["volume"].iloc[-3:-1].mean())
        if rvol >= 0.8:
            confirmacoes.append(f"RVOL {rvol:.2f}")
        elif rvol < 0.5:
            motivos.append(f"RVOL {rvol:.2f} muito baixo")

        if vol_cresc: confirmacoes.append("Volume crescente")

        # 5. BOS/CHoCH
        highs = float(df["high"].iloc[-16:-1].max())
        lows  = float(df["low"].iloc[-16:-1].min())
        bos   = (c > highs*0.998) if direcao=="LONG" else (c < lows*1.002)
        if bos: confirmacoes.append("BOS/CHoCH")

        # 6. H4 contexto
        r4h    = df4h.iloc[-1]
        tend_h4= float(r4h["ema21"]) > float(r4h["ema50"])
        h1_ali = (e10 > e21) if direcao=="LONG" else (e10 < e21)
        h4_h1_ali = (tend_h4 and direcao=="LONG") or (not tend_h4 and direcao=="SHORT")

        if h4_h1_ali and h1_ali:
            confirmacoes.append("H4+H1 alinhados")
        elif not h4_h1_ali:
            adx_4h = float(r4h["adx"])
            if adx_4h > 35:
                motivos.append(f"Tendência H4 forte contra ({adx_4h:.0f})")
            else:
                penalidade += 5

        # 7. Confluência Early Entry V1
        n_confs = len(confirmacoes)
        rvol_ok = rvol >= 0.80
        h1_tend = h1_ali

        if n_confs >= 4:
            pass  # aprovação normal
        elif n_confs >= 2 and rvol_ok and h1_tend:
            pass  # Early Entry: 2/4 com RVOL>=0.8 e H1 alinhado
        else:
            motivos.append(f"Early Entry: {n_confs}/4 confs insuficiente (RVOL={rvol:.2f})")

        # ── SCORE ─────────────────────────────────────────────────────────────
        score = n_confs * 12 + (8 if rvol >= 1.5 else 5 if rvol >= 1.0 else 2 if rvol >= 0.8 else 0)
        score = max(0, min(90, score - penalidade))

        # Niveis
        if direcao == "LONG":
            swing_low = float(df["low"].iloc[-5:].min())
            stop = round(swing_low - atr*0.1, 6)
            if abs(c-stop) > atr*1.5: stop = round(c-atr*1.0, 6)
            tp1  = round(c + abs(c-stop)*2.5, 6)
        else:
            swing_high = float(df["high"].iloc[-5:].max())
            stop = round(swing_high + atr*0.1, 6)
            if abs(stop-c) > atr*1.5: stop = round(c+atr*1.0, 6)
            tp1  = round(c - abs(stop-c)*2.5, 6)
        rr = round(abs(tp1-c)/abs(stop-c), 2) if stop != c else 0

        if score < 70:   motivos.append(f"Score {score} < 70")
        if rr < 2.0:     motivos.append(f"RR {rr} < 2.0")
        if rvol < 0.5:   motivos.append(f"RVOL {rvol:.2f} < 0.5")

        aprovado = len(motivos) == 0

        tier = "OURO" if score>=85 else "PRATA" if score>=75 else "BRONZE" if score>=70 else "ABAIXO"
        gb_risco = round(BANCA * RISCO_PCT / 100, 2)
        dist = abs(c-stop)/c if c else 0.01
        pos  = round(min(gb_risco/dist, BANCA*3), 2) if dist > 0 else 0
        alav = 20 if score>=85 else 15 if score>=75 else 10

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "shadow":           self.SHADOW_MODE,
            "engine":           "EARLY_ENTRY_V1",
            "setup_nome":       "EARLY_ENTRY",
            "regime":           "Early Entry ↗" if direcao=="LONG" else "Early Entry ↘",
            "direcao":          direcao,
            "score":            score,
            "tier":             tier,
            "penalidade":       penalidade,
            "entrada":          c,
            "stop":             stop,
            "tp1":              tp1,
            "tp2":              tp1,
            "rr":               rr,
            "adx":              adx,
            "rsi":              rsi,
            "atr":              atr,
            "rvol":             rvol,
            "confirmacoes_smc": confirmacoes,
            "confluencia":      n_confs,
            "motivos_rejeicao": motivos,
            "timeframe":        tf,
            "preco_atual":      c,
            "capital":          BANCA,
            "posicao":          pos,
            "risco_usdt":       gb_risco,
            "alavancagem":      alav,
        }
