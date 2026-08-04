"""
K11 Smart Money Entry Engine
Filosofia: não entrar onde todos entram.
Entrar APÓS o sweep institucional — quando o tubarão já comeu as sardinhas.

Setup ideal:
1. Liquidity Sweep — preço falso acima/abaixo de estrutura
2. Rejeição imediata — candle de reversão forte
3. BOS na nova direção — confirmação que inverteu
4. Volume no sweep — institucional estava lá
5. Retorno para zona — entrada no reteste, não no topo/fundo
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
        df["vwap"]   = (v*(h+l+c)/3).cumsum()/v.cumsum()
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # DETECTOR DE SWEEP DE LIQUIDEZ
    # ─────────────────────────────────────────────────────────────────────────
    def _detectar_sweep(self, df):
        """
        Detecta se houve sweep de liquidez recente seguido de reversão.
        
        Sweep LONG (compra após sweep de baixa):
        - Preço furou abaixo de suporte recente (equal lows / swing low)
        - Voltou acima imediatamente (rejeição)
        - Candle de reversão forte (sombra longa abaixo, corpo verde)
        
        Sweep SHORT (venda após sweep de alta):
        - Preço furou acima de resistência recente (equal highs / swing high)
        - Voltou abaixo imediatamente
        - Candle de reversão forte (sombra longa acima, corpo vermelho)
        
        Retorna: (direcao, score_sweep, confirmacoes, detalhes)
        """
        # Usar velas fechadas — não a atual em formação
        df_closed = df.iloc[:-1].copy()
        r  = df_closed.iloc[-1]   # última vela fechada
        r2 = df_closed.iloc[-2]   # penúltima
        r3 = df_closed.iloc[-3]

        c   = float(r["close"]); o = float(r["open"])
        h_r = float(r["high"]); l_r = float(r["low"])
        atr = float(r["atr"])
        rvol= float(r["rvol"]) if not np.isnan(r["rvol"]) else 0

        corpo = abs(c - o)
        total = h_r - l_r
        sombra_inf = (min(o,c) - l_r)
        sombra_sup = (h_r - max(o,c))

        # Suportes e resistências dos últimos 20 candles (excluindo os 3 últimos)
        lookback = df_closed.iloc[-23:-3]
        swing_high = float(lookback["high"].max())
        swing_low  = float(lookback["low"].min())

        # Equal highs/lows (clusters de preço ± 0.2 ATR)
        recent_highs = df_closed["high"].iloc[-15:-2]
        recent_lows  = df_closed["low"].iloc[-15:-2]
        eq_high = float(recent_highs.max())
        eq_low  = float(recent_lows.min())

        confirmacoes = []
        score = 0
        direcao = None

        # ── SWEEP DE BAIXA (setup para LONG) ─────────────────────────────────
        # 1. Preço da vela fechada furou abaixo do swing low / equal low
        furou_baixo = l_r < eq_low * 0.999

        # 2. Fechou acima do suporte (rejeição — não continuou)
        rejeitou_baixo = c > eq_low

        # 3. Sombra inferior longa (tubarão atuou lá embaixo)
        sombra_longa_inf = sombra_inf > corpo * 0.8 and sombra_inf > atr * 0.3

        # 4. Candle de reversão — fechou verde ou quase
        candle_rev_long = c >= o * 0.999

        # 5. Volume no sweep — institucional estava presente
        vol_sweep = rvol >= 1.0

        if furou_baixo and rejeitou_baixo:
            if sombra_longa_inf:
                confirmacoes.append("Sombra longa no sweep")
                score += 25
            if candle_rev_long:
                confirmacoes.append("Candle de reversão fechado")
                score += 20
            if vol_sweep:
                confirmacoes.append(f"Volume no sweep RVOL {rvol:.2f}")
                score += 20
            confirmacoes.append(f"Sweep de baixa confirmado ({eq_low:.6f})")
            score += 20
            direcao = "LONG"

        # ── SWEEP DE ALTA (setup para SHORT) ─────────────────────────────────
        furou_alto = h_r > eq_high * 1.001
        rejeitou_alto = c < eq_high
        sombra_longa_sup = sombra_sup > corpo * 0.8 and sombra_sup > atr * 0.3
        candle_rev_short = c <= o * 1.001

        if furou_alto and rejeitou_alto:
            if sombra_longa_sup:
                confirmacoes.append("Sombra longa no sweep")
                score += 25
            if candle_rev_short:
                confirmacoes.append("Candle de reversão fechado")
                score += 20
            if vol_sweep:
                confirmacoes.append(f"Volume no sweep RVOL {rvol:.2f}")
                score += 20
            confirmacoes.append(f"Sweep de alta confirmado ({eq_high:.6f})")
            score += 20
            direcao = "SHORT"

        # ── BOS após sweep ────────────────────────────────────────────────────
        if direcao == "LONG":
            # BOS: fechou acima da máxima de 2 velas anteriores
            bos = c > max(float(r2["high"]), float(r3["high"]))
            if bos:
                confirmacoes.append("BOS confirmado após sweep")
                score += 15
        elif direcao == "SHORT":
            bos = c < min(float(r2["low"]), float(r3["low"]))
            if bos:
                confirmacoes.append("BOS confirmado após sweep")
                score += 15

        # ── Contexto macro ────────────────────────────────────────────────────
        if direcao:
            e50  = float(r["ema50"]); e200 = float(r["ema200"])
            tend_ok = (e50 > e200) if direcao=="LONG" else (e50 < e200)
            if tend_ok:
                confirmacoes.append("Tendência H1 favorável")
                score += 10
            rsi = float(r["rsi"])
            rsi_ok = (rsi < 60) if direcao=="LONG" else (rsi > 40)
            if rsi_ok:
                confirmacoes.append(f"RSI {rsi:.1f} favorável")
                score += 10

        return direcao, min(score, 100), confirmacoes

    # ─────────────────────────────────────────────────────────────────────────
    # NÍVEIS — Stop ATRÁS do sweep, TP baseado na estrutura
    # ─────────────────────────────────────────────────────────────────────────
    def _calcular_niveis(self, df, direcao):
        df_closed = df.iloc[:-1]
        r   = df_closed.iloc[-1]
        c   = float(df.iloc[-1]["close"])  # preço atual
        atr = float(r["atr"])

        if direcao == "LONG":
            # Stop: abaixo da mínima do sweep (com margem)
            stop = round(float(df_closed["low"].iloc[-3:].min()) - atr*0.15, 6)
            if abs(c-stop)/c > 0.05: stop = round(c*0.95, 6)
            risco = abs(c-stop)
            tp1   = round(c + risco*2.5, 6)
            if tp1 > c*1.12: tp1 = round(c*1.08, 6)
        else:
            stop = round(float(df_closed["high"].iloc[-3:].max()) + atr*0.15, 6)
            if abs(stop-c)/c > 0.05: stop = round(c*1.05, 6)
            risco = abs(stop-c)
            tp1   = round(c - risco*2.5, 6)
            if tp1 < c*0.88: tp1 = round(c*0.92, 6)
            if tp1 <= 0: tp1 = round(c*0.92, 6)

        rr = round(abs(tp1-c)/abs(stop-c), 2) if stop != c else 0
        return c, stop, tp1, atr, rr

    # ─────────────────────────────────────────────────────────────────────────
    # ANÁLISE
    # ─────────────────────────────────────────────────────────────────────────
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
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"direcao":"—","rr":0,"rvol":0}

        # Detectar sweep
        direcao, score_sweep, confirmacoes = self._detectar_sweep(df)

        if not direcao:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["Sem sweep de liquidez detectado"],
                    "timeframe":tf,"direcao":"—","rr":0,
                    "rvol":float(df.iloc[-1]["rvol"]) if not np.isnan(df.iloc[-1]["rvol"]) else 0}

        # Níveis
        entrada, stop, tp1, atr, rr = self._calcular_niveis(df, direcao)
        rvol = float(df.iloc[-2]["rvol"]) if not np.isnan(df.iloc[-2]["rvol"]) else 0
        adx  = float(df.iloc[-1]["adx"])
        rsi  = float(df.iloc[-1]["rsi"])

        motivos = []

        # Score mínimo
        if score_sweep < 55:
            motivos.append(f"Score sweep {score_sweep} insuficiente")

        # RR mínimo
        if rr < 2.0:
            motivos.append(f"RR {rr} < 2.0")

        # Contexto H4 — não entrar contra tendência muito forte
        r4h    = df4h.iloc[-1]
        adx_4h = float(r4h["adx"])
        tend_h4= float(r4h["ema21"]) > float(r4h["ema50"])
        contra_forte = (
            (direcao=="LONG" and not tend_h4 and adx_4h > 35) or
            (direcao=="SHORT" and tend_h4 and adx_4h > 35)
        )
        if contra_forte:
            motivos.append(f"Contra tendência H4 muito forte ADX={adx_4h:.0f}")

        aprovado = len(motivos) == 0

        # Tier
        if score_sweep >= 85:   tier = "OURO"
        elif score_sweep >= 75: tier = "PRATA"
        elif score_sweep >= 65: tier = "BRONZE"
        else:                   tier = "ABAIXO"

        conv = {"OURO":"ALTA ✅","PRATA":"BOA ⚡","BRONZE":"MODERADA 🔶"}.get(tier,"MODERADA 🔶")

        if score_sweep >= 85 and rvol >= 2.0: prioridade = "🔥 SWEEP INSTITUCIONAL"
        elif score_sweep >= 75:               prioridade = "⭐ SWEEP CONFIRMADO"
        else:                                 prioridade = ""

        gb_risco = round(BANCA * RISCO_PCT / 100, 2)
        dist = abs(entrada-stop)/entrada if entrada else 0.01
        pos  = round(min(gb_risco/dist, BANCA*3), 2) if dist > 0 else 0
        alav = 20 if score_sweep>=85 else 15 if score_sweep>=75 else 10

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "setup_nome":       "SWEEP",
            "regime":           "Sweep ↗" if direcao=="LONG" else "Sweep ↘",
            "direcao":          direcao,
            "score":            score_sweep,
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
            "vwap":             float(df.iloc[-1]["vwap"]),
            "ema21":            float(df.iloc[-1]["ema21"]),
            "confirmacoes_smc": confirmacoes,
            "confluencia":      len(confirmacoes),
            "motivos_rejeicao": motivos,
            "o_que_falta":      motivos,
            "timeframe":        tf,
            "preco_atual":      entrada,
            "capital":          BANCA,
            "posicao":          pos,
            "risco_usdt":       gb_risco,
            "alavancagem":      alav,
            "banca":            BANCA,
        }

    def analisar_tf(self, symbol, tf):
        return self._analisar_tf(symbol, tf)

    def obter_regime(self, symbol):
        df = self._calc(self._fetch(symbol, "1h"))
        return {"regime":"SWEEP","adx":float(df.iloc[-1]["adx"]),"atr":float(df.iloc[-1]["atr"])}
