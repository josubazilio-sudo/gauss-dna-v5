"""
K11 Engine — CHoCH + Liquidity Capture + Volume
Sequência: Tendência → Quebra (CHoCH) → Sweep → Volume → Entrada no reteste
Nunca entrar no topo/fundo óbvio. Entrar após confirmação institucional.
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

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO 1 — IDENTIFICAR TENDÊNCIA ANTERIOR
    # ─────────────────────────────────────────────────────────────────────────
    def _tendencia_anterior(self, df):
        """Identifica a tendência dos últimos 20-50 candles."""
        closes = df["close"].iloc[-50:-5]
        e21    = df["ema21"].iloc[-50:-5]
        # Tendência de alta: preço consistentemente acima da EMA21
        acima = (closes > e21).sum()
        abaixo= (closes < e21).sum()
        if acima > 25:   return "ALTA"
        if abaixo > 25:  return "BAIXA"
        # Usar EMA como desempate
        e50_atual = float(df["ema50"].iloc[-1])
        e200_atual = float(df["ema200"].iloc[-1])
        if e50_atual > e200_atual: return "ALTA"
        if e50_atual < e200_atual: return "BAIXA"
        return "LATERAL"

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO 2 — DETECTAR CHoCH (Change of Character)
    # ─────────────────────────────────────────────────────────────────────────
    def _detectar_choch(self, df, tendencia):
        """
        Detecta CHoCH RECENTE — máximo 4 velas atrás.
        Se o CHoCH foi há mais tempo, sinal atrasado — ignorar.
        """
        df_c = df.iloc[:-1]
        atr  = float(df_c["atr"].iloc[-1])

        # Swing points dos últimos 30 candles (excluindo os 5 mais recentes)
        lookback = df_c.iloc[-30:-5]
        swing_high = float(lookback["high"].max())
        swing_low  = float(lookback["low"].min())

        # Verificar se CHoCH aconteceu nas últimas 4 velas
        janela = df_c.iloc[-4:]

        if tendencia == "ALTA":
            # CHoCH DOWN: alguma das últimas 4 velas fechou abaixo do swing low
            for i in range(len(janela)):
                c_vela = float(janela["close"].iloc[i])
                if c_vela < swing_low * 1.002:
                    # CHoCH confirmado — verificar se não atrasou demais
                    # Preço atual não pode estar muito longe do ponto de CHoCH
                    c_atual = float(df_c["close"].iloc[-1])
                    dist_choch = abs(c_atual - swing_low) / atr if atr > 0 else 99
                    if dist_choch <= 5.0:  # máximo 5 ATR do ponto de quebra
                        return "DOWN", swing_low, swing_high

        if tendencia == "BAIXA":
            # CHoCH UP: alguma das últimas 4 velas fechou acima do swing high
            for i in range(len(janela)):
                c_vela = float(janela["close"].iloc[i])
                if c_vela > swing_high * 0.998:
                    c_atual = float(df_c["close"].iloc[-1])
                    dist_choch = abs(c_atual - swing_high) / atr if atr > 0 else 99
                    if dist_choch <= 5.0:
                        return "UP", swing_low, swing_high

        return None, swing_low, swing_high

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO 3 — VERIFICAR CAPTURA DE LIQUIDEZ + VOLUME
    # ─────────────────────────────────────────────────────────────────────────
    def _captura_liquidez(self, df, choch_dir):
        """
        Após o CHoCH, verifica se houve captura de liquidez:
        - Sombra longa (spike) na direção do sweep
        - Volume acima da média no candle do sweep
        - Fechamento de volta para zona segura
        """
        df_c = df.iloc[:-1]
        r    = df_c.iloc[-1]   # última vela fechada
        r2   = df_c.iloc[-2]
        atr  = float(r["atr"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        rvol2= float(r2["rvol"]) if not np.isnan(r2["rvol"]) else 0

        c_r  = float(r["close"]); o_r = float(r["open"])
        h_r  = float(r["high"]);  l_r = float(r["low"])
        corpo = abs(c_r - o_r)
        total = h_r - l_r

        sombra_inf = min(o_r,c_r) - l_r
        sombra_sup = h_r - max(o_r,c_r)

        confirmacoes = []
        score = 0

        if choch_dir == "UP":
            # Captura de liquidez para LONG:
            # Candle ou candles recentes tiveram sombra inferior longa
            sweep_ok = sombra_inf > atr * 0.4 or (float(r2["low"]) < float(df_c["low"].iloc[-10:-2].min()))
            if sweep_ok:
                confirmacoes.append("Captura de liquidez ↓")
                score += 30
            # Volume no candle de reversão
            if rvol >= 1.0 or rvol2 >= 1.0:
                confirmacoes.append(f"Volume institucional RVOL {max(rvol,rvol2):.2f}")
                score += 25
            # Fechou verde (compradores assumiram)
            if c_r > o_r:
                confirmacoes.append("Candle comprador fechado")
                score += 20
            # MACD virando para cima
            macd_h = float(r["macd_hist"])
            macd_h2= float(df_c["macd_hist"].iloc[-3])
            if macd_h > macd_h2:
                confirmacoes.append("MACD virando para cima")
                score += 15
            # RSI saindo do fundo
            rsi = float(r["rsi"])
            if rsi < 50 and rsi > float(df_c["rsi"].iloc[-3]):
                confirmacoes.append(f"RSI saindo do fundo {rsi:.1f}")
                score += 10

        elif choch_dir == "DOWN":
            # Captura de liquidez para SHORT:
            sweep_ok = sombra_sup > atr * 0.4 or (float(r2["high"]) > float(df_c["high"].iloc[-10:-2].max()))
            if sweep_ok:
                confirmacoes.append("Captura de liquidez ↑")
                score += 30
            if rvol >= 1.0 or rvol2 >= 1.0:
                confirmacoes.append(f"Volume institucional RVOL {max(rvol,rvol2):.2f}")
                score += 25
            if c_r < o_r:
                confirmacoes.append("Candle vendedor fechado")
                score += 20
            macd_h = float(r["macd_hist"])
            macd_h2= float(df_c["macd_hist"].iloc[-3])
            if macd_h < macd_h2:
                confirmacoes.append("MACD virando para baixo")
                score += 15
            rsi = float(r["rsi"])
            if rsi > 50 and rsi < float(df_c["rsi"].iloc[-3]):
                confirmacoes.append(f"RSI saindo do topo {rsi:.1f}")
                score += 10

        return min(score, 100), confirmacoes

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO 4 — VERIFICAR RETESTE (entrada não óbvia)
    # ─────────────────────────────────────────────────────────────────────────
    def _verificar_reteste(self, df, choch_dir, swing_low, swing_high):
        """
        Verifica se o preço está no reteste da zona de CHoCH
        (não no topo/fundo — entrada não óbvia).
        """
        c_atual = float(df.iloc[-1]["close"])
        atr     = float(df.iloc[-1]["atr"])

        if choch_dir == "UP":
            # Preço deve estar perto do swing low quebrado (reteste do suporte virou resistência)
            # Não entrar muito longe — máximo 3 ATR acima do swing
            dist = abs(c_atual - swing_low) / atr if atr > 0 else 99
            return dist <= 5.0, dist

        elif choch_dir == "DOWN":
            dist = abs(c_atual - swing_high) / atr if atr > 0 else 99
            return dist <= 5.0, dist

        return False, 99

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO 5 — NÍVEIS
    # ─────────────────────────────────────────────────────────────────────────
    def _calcular_niveis(self, df, direcao, swing_low, swing_high):
        c   = float(df.iloc[-1]["close"])
        atr = float(df.iloc[-1]["atr"])

        if direcao == "LONG":
            # Stop abaixo do swing low (onde a captura de liquidez aconteceu)
            stop = round(swing_low - atr * 0.2, 6)
            if abs(c-stop)/c > 0.06: stop = round(c * 0.94, 6)
            risco = abs(c-stop)
            tp1   = round(c + risco * 2.5, 6)
            if tp1 > c * 1.12: tp1 = round(c * 1.10, 6)
        else:
            stop = round(swing_high + atr * 0.2, 6)
            if abs(stop-c)/c > 0.06: stop = round(c * 1.06, 6)
            risco = abs(stop-c)
            tp1   = round(c - risco * 2.5, 6)
            if tp1 < c * 0.88: tp1 = round(c * 0.90, 6)
            if tp1 <= 0: tp1 = round(c * 0.90, 6)

        rr = round(abs(tp1-c)/abs(stop-c), 2) if stop != c else 0
        return c, stop, tp1, atr, rr

    # ─────────────────────────────────────────────────────────────────────────
    # ANÁLISE PRINCIPAL
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

        motivos = []

        # PASSO 1: Tendência anterior
        tendencia = self._tendencia_anterior(df)
        if tendencia == "LATERAL":
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["Mercado lateral — sem tendência para quebrar"],
                    "timeframe":tf,"direcao":"—","rr":0,"rvol":0}

        # PASSO 2: CHoCH
        choch_dir, swing_low, swing_high = self._detectar_choch(df, tendencia)
        if not choch_dir:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"Sem CHoCH detectado (tendência {tendencia})"],
                    "timeframe":tf,"direcao":"—","rr":0,"rvol":0}

        direcao = "LONG" if choch_dir == "UP" else "SHORT"

        # PASSO 3: Captura de liquidez + Volume
        score_captura, confirmacoes = self._captura_liquidez(df, choch_dir)
        if score_captura < 40:
            return {"symbol":symbol,"aprovado":False,"score":score_captura,
                    "motivos_rejeicao":[f"Captura de liquidez insuficiente ({score_captura}pts)"],
                    "timeframe":tf,"direcao":direcao,"rr":0,
                    "rvol":float(df.iloc[-2]["rvol"]) if not np.isnan(df.iloc[-2]["rvol"]) else 0}

        # PASSO 4: Reteste
        reteste_ok, dist_reteste = self._verificar_reteste(df, choch_dir, swing_low, swing_high)
        if not reteste_ok:
            motivos.append(f"Preço muito longe do reteste ({dist_reteste:.1f} ATR)")
        else:
            confirmacoes.append(f"Reteste da zona ({dist_reteste:.1f} ATR)")

        # PASSO 5: Níveis
        entrada, stop, tp1, atr, rr = self._calcular_niveis(df, direcao, swing_low, swing_high)
        rvol = float(df.iloc[-2]["rvol"]) if not np.isnan(df.iloc[-2]["rvol"]) else 0
        adx  = float(df.iloc[-1]["adx"])
        rsi  = float(df.iloc[-1]["rsi"])

        # H4 contexto — não entrar contra tendência muito forte
        r4h    = df4h.iloc[-1]
        adx_4h = float(r4h["adx"])
        tend_h4= float(r4h["ema21"]) > float(r4h["ema50"])
        contra_forte = (
            (direcao=="LONG"  and not tend_h4 and adx_4h > 35) or
            (direcao=="SHORT" and tend_h4     and adx_4h > 35)
        )
        if contra_forte:
            motivos.append(f"H4 tendência forte contra ADX={adx_4h:.0f}")
        else:
            confirmacoes.append("H4 favorável")

        # Score final
        score = score_captura
        if reteste_ok:    score += 10
        if rr >= 2.5:     score += 5
        if rvol >= 2.0:   score += 8
        elif rvol >= 1.0: score += 4
        score = min(score, 100)

        if score < 60:
            motivos.append(f"Score {score} insuficiente")
        if rr < 2.0:
            motivos.append(f"RR {rr} < 2.0")

        aprovado = len(motivos) == 0

        if score >= 85:   tier = "OURO"
        elif score >= 75: tier = "PRATA"
        elif score >= 65: tier = "BRONZE"
        else:             tier = "ABAIXO"

        conv = {"OURO":"ALTA ✅","PRATA":"BOA ⚡","BRONZE":"MODERADA 🔶"}.get(tier,"MODERADA 🔶")

        if score >= 85 and "Volume institucional" in str(confirmacoes):
            prioridade = "🔥 INSTITUCIONAL"
        elif score >= 75:
            prioridade = "⭐ CHoCH CONFIRMADO"
        else:
            prioridade = ""

        gb_risco = round(BANCA * RISCO_PCT / 100, 2)
        dist = abs(entrada-stop)/entrada if entrada else 0.01
        pos  = round(min(gb_risco/dist, BANCA*3), 2) if dist > 0 else 0
        alav = 20 if score>=85 else 15 if score>=75 else 10

        regime_label = {
            ("ALTA","DOWN"):  "Quebra de Alta ↘",
            ("ALTA","UP"):    "Continuação Alta ↑",
            ("BAIXA","UP"):   "Quebra de Baixa ↗",
            ("BAIXA","DOWN"): "Continuação Baixa ↓",
        }.get((tendencia, choch_dir), "CHoCH")

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "setup_nome":       "CHoCH",
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
            "vwap":             float(df.iloc[-1]["vwap"]) if "vwap" in df.columns else entrada,
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
        tend = self._tendencia_anterior(df)
        return {"regime":f"CHoCH_{tend}","adx":float(df.iloc[-1]["adx"]),"atr":float(df.iloc[-1]["atr"])}
