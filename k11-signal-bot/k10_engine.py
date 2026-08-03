"""
K10 Engine — Entrada na Virada ou Início do Movimento
Foco: MACD cruzando, RSI saindo do extremo, espaço limpo até TP1
"""

import ccxt
import pandas as pd
import numpy as np
from config import BANCA, RISCO_PCT, ALAVANCAGEM_POR_REGIME


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
            raise RuntimeError(f"Fetch {symbol} {tf}: {e}")

    def _calc(self, df):
        c, h, l, v = df["close"], df["high"], df["low"], df["volume"]

        for p in [10, 21, 50, 200]:
            df[f"ema{p}"] = c.ewm(span=p, adjust=False).mean()

        df["vwap"] = (v * (h + l + c) / 3).cumsum() / v.cumsum()

        tr   = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()], axis=1).max(axis=1)
        df["atr"] = tr.ewm(span=14, adjust=False).mean()

        dm_p  = h.diff().clip(lower=0).where(h.diff() > (-l.diff()), 0.0)
        dm_n  = (-l.diff()).clip(lower=0).where((-l.diff()) > h.diff(), 0.0)
        atr14 = tr.ewm(span=14, adjust=False).mean()
        di_p  = 100 * dm_p.ewm(span=14, adjust=False).mean() / atr14
        di_n  = 100 * dm_n.ewm(span=14, adjust=False).mean() / atr14
        dx    = 100*(di_p-di_n).abs()/(di_p+di_n).replace(0, np.nan)
        df["adx"] = dx.ewm(span=14, adjust=False).mean()

        delta = c.diff()
        gain  = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
        df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

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
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma20.replace(0, np.nan)

        df["vol_ma"] = v.rolling(20).mean()
        df["rvol"]   = v / df["vol_ma"].replace(0, np.nan)

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # DETECÇÃO DA VIRADA / INÍCIO DO MOVIMENTO
    # ─────────────────────────────────────────────────────────────────────────
    def _detectar_virada(self, df):
        """
        Detecta se o momento atual é uma virada ou início de movimento.
        Retorna: (direcao, tipo_entrada, score_virada, motivos)
        """
        r    = df.iloc[-1]
        c    = float(r["close"])
        rsi  = float(r["rsi"])
        adx  = float(r["adx"])
        atr  = float(r["atr"])
        e21  = float(r["ema21"])
        e50  = float(r["ema50"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0

        macd_hist_0 = float(df["macd_hist"].iloc[-1])
        macd_hist_1 = float(df["macd_hist"].iloc[-2])
        macd_hist_2 = float(df["macd_hist"].iloc[-3])
        macd_0      = float(df["macd"].iloc[-1])
        macd_sig_0  = float(df["macd_signal"].iloc[-1])
        macd_0_ant  = float(df["macd"].iloc[-2])
        macd_sig_ant= float(df["macd_signal"].iloc[-2])

        rsi_0 = float(df["rsi"].iloc[-1])
        rsi_1 = float(df["rsi"].iloc[-2])
        rsi_2 = float(df["rsi"].iloc[-3])
        rsi_3 = float(df["rsi"].iloc[-4])

        score = 0
        sinais_long  = []
        sinais_short = []

        # ── MACD: cruzamento recente ou acabou de cruzar ──────────────────────
        # LONG: macd cruzou signal para cima agora ou 1-2 velas atrás
        macd_cruz_long  = (macd_0 > macd_sig_0 and macd_0_ant <= macd_sig_ant)
        macd_cruz_short = (macd_0 < macd_sig_0 and macd_0_ant >= macd_sig_ant)

        # Histograma: virou de negativo para positivo (LONG) ou contrário (SHORT)
        hist_virou_long  = macd_hist_1 < 0 and macd_hist_0 > 0
        hist_virou_short = macd_hist_1 > 0 and macd_hist_0 < 0

        # Histograma crescendo após cruzamento (início do movimento)
        hist_acelerando_long  = macd_hist_0 > macd_hist_1 > macd_hist_2 and macd_hist_0 > 0
        hist_acelerando_short = macd_hist_0 < macd_hist_1 < macd_hist_2 and macd_hist_0 < 0

        if macd_cruz_long or hist_virou_long:
            sinais_long.append("MACD cruzou para cima")
            score += 30
        elif hist_acelerando_long:
            sinais_long.append("MACD acelerando para cima")
            score += 20

        if macd_cruz_short or hist_virou_short:
            sinais_short.append("MACD cruzou para baixo")
            score += 30
        elif hist_acelerando_short:
            sinais_short.append("MACD acelerando para baixo")
            score += 20

        # ── RSI: saindo do extremo, não no topo/fundo ─────────────────────────
        # LONG: RSI vinha abaixo de 40 e está subindo
        rsi_virada_long  = rsi_2 < 38 and rsi_1 < rsi_0 and rsi_0 < 60
        # SHORT: RSI vinha acima de 60 e está caindo
        rsi_virada_short = rsi_2 > 62 and rsi_1 > rsi_0 and rsi_0 > 40

        # RSI no meio com força (45-65 para LONG, 35-55 para SHORT)
        rsi_bom_long  = 42 <= rsi_0 <= 65 and rsi_0 > rsi_1
        rsi_bom_short = 35 <= rsi_0 <= 58 and rsi_0 < rsi_1

        if rsi_virada_long:
            sinais_long.append("RSI saindo da sobrevenda")
            score += 25
        elif rsi_bom_long:
            sinais_long.append("RSI com força para cima")
            score += 15

        if rsi_virada_short:
            sinais_short.append("RSI saindo da sobrecompra")
            score += 25
        elif rsi_bom_short:
            sinais_short.append("RSI com força para baixo")
            score += 15

        # ── Pullback na EMA21 (entrada no reteste) ────────────────────────────
        dist_ema21 = abs(c - e21) / atr if atr > 0 else 99
        pullback_long  = dist_ema21 <= 1.0 and c > e21
        pullback_short = dist_ema21 <= 1.0 and c < e21

        if pullback_long:
            sinais_long.append("Pullback na EMA21")
            score += 20
        if pullback_short:
            sinais_short.append("Pullback na EMA21")
            score += 20

        # ── Volume confirmando ────────────────────────────────────────────────
        if rvol >= 1.0:
            if sinais_long:  sinais_long.append(f"Volume confirmado RVOL {rvol:.2f}")
            if sinais_short: sinais_short.append(f"Volume confirmado RVOL {rvol:.2f}")
            score += 15
        elif rvol < 0.7:
            score -= 15

        # ── Espaço até o TP1 (ATR) — sem obstáculos ──────────────────────────
        bb_mid = float(r["bb_mid"])
        dist_resistencia = abs(c - bb_mid) / atr if atr > 0 else 0

        # ── Decidir direção ───────────────────────────────────────────────────
        # Preferir LONG se mais sinais LONG, SHORT se mais SHORT
        n_long  = len(sinais_long)
        n_short = len(sinais_short)

        if n_long == 0 and n_short == 0:
            return None, "SEM_VIRADA", 0, ["Sem virada ou início de movimento detectado"]

        if n_long >= n_short:
            direcao = "LONG"
            confirmacoes = sinais_long
        else:
            direcao = "SHORT"
            confirmacoes = sinais_short

        # Score mínimo para considerar válido
        score_final = min(score, 100)

        return direcao, "VIRADA", score_final, confirmacoes

    # ─────────────────────────────────────────────────────────────────────────
    # NÍVEIS: Stop atrás da estrutura, TP com espaço real
    # ─────────────────────────────────────────────────────────────────────────
    def _calcular_niveis(self, df, direcao):
        r   = df.iloc[-1]
        c   = float(r["close"])
        atr = float(r["atr"])

        if direcao == "LONG":
            # Stop: mínimo dos últimos 5 candles - 0.1 ATR (stop justo)
            swing_low  = float(df["low"].iloc[-5:].min())
            stop = round(swing_low - atr*0.1, 6)
            # Se stop ficou muito longe, usar 1.0 ATR fixo
            if abs(c - stop) > atr * 1.5:
                stop = round(c - atr*1.0, 6)
            # TP1: 2.5x o risco real
            risco = abs(c - stop)
            tp1 = round(c + risco * 2.5, 6)
        else:
            swing_high = float(df["high"].iloc[-5:].max())
            stop = round(swing_high + atr*0.1, 6)
            if abs(stop - c) > atr * 1.5:
                stop = round(c + atr*1.0, 6)
            risco = abs(stop - c)
            tp1 = round(c - risco * 2.5, 6)

        rr = round(abs(tp1 - c) / abs(stop - c), 2) if stop != c else 0
        return c, stop, tp1, atr

    # ─────────────────────────────────────────────────────────────────────────
    # SCORE FINAL
    # ─────────────────────────────────────────────────────────────────────────
    def _score_final(self, score_virada, rr, rvol, adx, n_confs):
        """
        Score realista — máximo ~80 para sinal comum, ~88 para excelente
        Pesos por tipo de virada:
          MACD cruzou = 30pts base
          RSI virada  = 25pts
          Pullback    = 20pts
          Volume      = 15pts
          Total base max = 90pts (raro ter todos)
        Bônus/penais limitados para não inflar
        """
        score = score_virada  # já vem calculado pelo _detectar_virada

        # RR — sem bônus, só penaliza se ruim
        if rr < 1.5:
            score -= 15

        # Volume — penaliza fraco, bônus pequeno se bom
        if rvol >= 1.5:
            score += 3
        elif rvol < 0.8:
            score -= 8

        # ADX — penaliza sem força
        if adx < 15:
            score -= 8

        # Confirmações extras — máximo +6
        score += min(n_confs, 3) * 2

        # Cap: nunca passa de 90
        score = max(0, min(90, score))

        # Tier exigente
        if score >= 82:   tier = "OURO"
        elif score >= 72: tier = "PRATA"
        elif score >= 62: tier = "BRONZE"
        else:             tier = "ABAIXO"

        return score, tier

    # ─────────────────────────────────────────────────────────────────────────
    # GESTÃO DE BANCA
    # ─────────────────────────────────────────────────────────────────────────
    def _gestao_banca(self, score, entrada, stop, atr):
        if score >= 82:   alav = 20
        elif score >= 72: alav = 15
        elif score >= 62: alav = 10
        else:             alav = 8
        risco = round(BANCA * RISCO_PCT / 100, 2)
        dist  = abs(entrada - stop) / entrada if entrada else 0.01
        # Posição = risco / distância, limitada a 3x a banca
        pos   = round(risco / dist, 2) if dist > 0 else 0
        pos   = min(pos, BANCA * 3)  # nunca mais que 3x a banca
        return {"alavancagem": alav, "capital": BANCA, "posicao": pos,
                "risco_usdt": risco, "banca": BANCA}

    # ─────────────────────────────────────────────────────────────────────────
    # ANÁLISE POR TIMEFRAME
    # ─────────────────────────────────────────────────────────────────────────
    def _analisar_tf(self, symbol, tf="1h"):
        lim = 200 if tf in ("4h","1d") else 300
        try:
            df = self._calc(self._fetch(symbol, tf, limit=lim))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"direcao":"—","rr":0}

        r    = df.iloc[-1]
        adx  = float(r["adx"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0

        direcao, tipo, score_virada, confirmacoes = self._detectar_virada(df)

        if direcao is None:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":confirmacoes,"timeframe":tf,"direcao":"—","rr":0}

        entrada, stop, tp1, atr = self._calcular_niveis(df, direcao)
        rr = round(abs(tp1 - entrada) / abs(stop - entrada), 2) if stop != entrada else 0
        score, tier = self._score_final(score_virada, rr, rvol, adx, len(confirmacoes))

        motivos = []
        if rr < 1.5:          motivos.append(f"RR {rr} insuficiente")
        if rvol < 0.4:        motivos.append(f"Volume ausente RVOL {rvol:.2f}")
        if score < 62:        motivos.append(f"Score {score} insuficiente")

        aprovado = len(motivos) == 0

        e10_v = float(r["ema10"]); e21_v = float(r["ema21"]); e50_v = float(r["ema50"])
        if e10_v > e21_v > e50_v and direcao == "LONG":
            regime_label = "Tendência Alta ↑"
        elif e10_v < e21_v < e50_v and direcao == "SHORT":
            regime_label = "Tendência Baixa ↓"
        elif e10_v < e21_v < e50_v and direcao == "LONG":
            regime_label = "Reversão ↗ (contra tendência)"
        elif e10_v > e21_v > e50_v and direcao == "SHORT":
            regime_label = "Reversão ↘ (contra tendência)"
        elif adx < 18:
            regime_label = "Lateral ↔"
        else:
            regime_label = "Transição"

        conv_map = {"OURO":"ALTA ✅","PRATA":"BOA ⚡","BRONZE":"MODERADA 🔶"}
        gb = self._gestao_banca(score, entrada, stop, atr)

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "setup_nome":       tipo,
            "regime":           regime_label,
            "direcao":          direcao,
            "score":            score,
            "tier":             tier,
            "conviccao":        conv_map.get(tier,"MODERADA 🔶"),
            "entrada":          entrada,
            "stop":             stop,
            "tp1":              tp1,
            "tp2":              tp1,
            "rr":               rr,
            "adx":              adx,
            "rsi":              float(r["rsi"]),
            "atr":              atr,
            "rvol":             rvol,
            "vwap":             float(r["vwap"]),
            "ema21":            float(r["ema21"]),
            "confirmacoes_smc": confirmacoes,
            "motivos_rejeicao": motivos,
            "o_que_falta":      motivos,
            "timeframe":        tf,
            "preco_atual":      entrada,
            **gb,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # ANÁLISE PRINCIPAL — testa 30m, 1h, 4h
    # ─────────────────────────────────────────────────────────────────────────
    def analisar(self, symbol, timeframe=None):
        tfs = [timeframe] if timeframe else ["30m","1h","4h"]
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
        return {"regime":"K10","adx":float(r["adx"]),"atr":float(r["atr"])}
