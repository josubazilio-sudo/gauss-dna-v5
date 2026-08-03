"""
K11 Engine — Motor Adaptativo por Setup V1
5 setups: Continuação | Reversão | Cruzamento | Lateral | Transição
Cada regime ativa filtros e pesos diferentes.
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

    # ─────────────────────────────────────────────────────────────────────────
    # DADOS
    # ─────────────────────────────────────────────────────────────────────────
    def _fetch(self, symbol, tf, limit=300):
        try:
            raw = self.exchange.fetch_ohlcv(symbol, tf, limit=limit)
            df  = pd.DataFrame(raw, columns=["ts","open","high","low","close","volume"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            return df
        except Exception as e:
            raise RuntimeError(f"Fetch {symbol} {tf}: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # INDICADORES
    # ─────────────────────────────────────────────────────────────────────────
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
        df["adx"]  = dx.ewm(span=14, adjust=False).mean()
        df["di_p"] = di_p
        df["di_n"] = di_n

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

        vol_sma20 = v.rolling(20, min_periods=10).mean()
        df["vol_ma"] = vol_sma20
        # RVOL usando vela fechada (shift 1) — não usar vela em formação
        vol_fechada = v.shift(1)
        df["rvol"]   = (vol_fechada / vol_sma20.replace(0, np.nan)).clip(lower=0, upper=50)

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO 1 — IDENTIFICAR REGIME
    # ─────────────────────────────────────────────────────────────────────────
    def _identificar_regime(self, df):
        r    = df.iloc[-1]
        adx  = float(r["adx"])
        e10  = float(r["ema10"])
        e21  = float(r["ema21"])
        e50  = float(r["ema50"])
        e200 = float(r["ema200"])
        macd_h  = float(r["macd_hist"])
        macd_h2 = float(df["macd_hist"].iloc[-4])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        vol_cresc = float(df["volume"].iloc[-1]) > float(df["volume"].iloc[-3:-1].mean())

        emas_long  = e10 > e21 and e50 > e200
        emas_short = e10 < e21 and e50 < e200
        ema_alinha = emas_long or emas_short

        macd_virando = (macd_h > 0 and macd_h2 <= 0) or (macd_h < 0 and macd_h2 >= 0)
        adx_subindo  = adx > float(df["adx"].iloc[-5])

        # EMA10 cruzando EMA21 recentemente
        e10_ant = float(df["ema10"].iloc[-4])
        e21_ant = float(df["ema21"].iloc[-4])
        ema_cruzou = (e10_ant <= e21_ant and e10 > e21) or (e10_ant >= e21_ant and e10 < e21)

        # SETUP 4 — LATERAL
        if adx < 18 and not ema_alinha:
            return "LATERAL"

        # SETUP 5 — TRANSIÇÃO
        if adx_subindo and macd_virando and not ema_alinha:
            return "TRANSICAO"

        # SETUP 3 — CRUZAMENTO
        if ema_cruzou and vol_cresc:
            return "CRUZAMENTO"

        # SETUP 2 — REVERSÃO
        c   = float(r["close"])
        atr = float(r["atr"])
        highs = float(df["high"].iloc[-16:-1].max())
        lows  = float(df["low"].iloc[-16:-1].min())
        bos = (c > highs * 0.998) or (c < lows * 1.002)
        rsi = float(r["rsi"])
        rsi_extremo = rsi > 65 or rsi < 35
        if bos and macd_virando and rsi_extremo:
            return "REVERSAO"

        # SETUP 1 — CONTINUAÇÃO
        if adx >= 25 and ema_alinha and vol_cresc:
            return "CONTINUACAO"

        return "REVERSAO"  # default

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO 2 — DIREÇÃO
    # ─────────────────────────────────────────────────────────────────────────
    def _definir_direcao(self, df, regime):
        r   = df.iloc[-1]
        e10 = float(r["ema10"])
        e21 = float(r["ema21"])
        e50 = float(r["ema50"])
        rsi = float(r["rsi"])
        macd_h = float(r["macd_hist"])

        if regime == "CONTINUACAO":
            return "LONG" if e10 > e21 > e50 else "SHORT"

        if regime in ("REVERSAO", "CRUZAMENTO", "TRANSICAO"):
            # Direção da virada
            macd_h_ant = float(df["macd_hist"].iloc[-4])
            if macd_h > 0 and macd_h > macd_h_ant:
                return "LONG"
            if macd_h < 0 and macd_h < macd_h_ant:
                return "SHORT"
            return "LONG" if e10 > e21 else "SHORT"

        if regime == "LATERAL":
            # Direção do rompimento
            c = float(r["close"])
            highs = float(df["high"].rolling(20).max().iloc[-3])
            lows  = float(df["low"].rolling(20).min().iloc[-3])
            return "LONG" if c > highs else "SHORT"

        return "LONG" if e10 > e21 else "SHORT"

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO 3 — FILTROS POR SETUP
    # ─────────────────────────────────────────────────────────────────────────
    def _filtrar_por_setup(self, df, df4h, regime, direcao):
        r    = df.iloc[-1]
        c    = float(r["close"])
        e10  = float(r["ema10"])
        e21  = float(r["ema21"])
        e50  = float(r["ema50"])
        e200 = float(r["ema200"])
        adx  = float(r["adx"])
        rsi  = float(r["rsi"])
        atr  = float(r["atr"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        macd_h  = float(r["macd_hist"])
        macd_h2 = float(df["macd_hist"].iloc[-4])
        vol_cresc = float(df["volume"].iloc[-1]) > float(df["volume"].iloc[-3:-1].mean())
        pullback  = abs(c - e21) / atr <= 1.5 if atr > 0 else False
        # BOS: preço superou máxima/mínima recente (últimos 15 candles, excluindo o atual)
        highs = float(df["high"].iloc[-16:-1].max())
        lows  = float(df["low"].iloc[-16:-1].min())
        bos   = (c > highs * 0.998) if direcao=="LONG" else (c < lows * 1.002)
        macd_ok = (macd_h > 0 and macd_h > macd_h2) if direcao=="LONG" else (macd_h < 0 and macd_h < macd_h2)
        rsi_ok  = (rsi > float(df["rsi"].iloc[-4])) if direcao=="LONG" else (rsi < float(df["rsi"].iloc[-4]))

        motivos = []
        confirmacoes = []

        # ── SETUP 1: CONTINUAÇÃO ─────────────────────────────────────────────
        if regime == "CONTINUACAO":
            emas_ok = (e10>e21>e50>e200) if direcao=="LONG" else (e10<e21<e50<e200)
            if not emas_ok:    motivos.append("EMAs não alinhadas para continuação")
            else:              confirmacoes.append("EMAs alinhadas")
            if adx < 25:       motivos.append(f"ADX {adx:.1f} < 25")
            else:              confirmacoes.append(f"ADX {adx:.1f} forte")
            if not pullback:   motivos.append("Sem pullback na EMA21")
            else:              confirmacoes.append("Pullback EMA21")
            if not macd_ok:    motivos.append("MACD não confirmando")
            else:              confirmacoes.append("MACD confirmado")
            if rvol < 0.8:     motivos.append(f"RVOL {rvol:.2f} < 0.8")
            else:              confirmacoes.append(f"RVOL {rvol:.2f}")
            score_min = 68
            rvol_min  = 0.7

        # ── SETUP 2: REVERSÃO ────────────────────────────────────────────────
        elif regime == "REVERSAO":
            if bos:            confirmacoes.append("BOS/CHoCH confirmado")
            if not macd_ok:    motivos.append("MACD não virou")
            else:              confirmacoes.append("MACD virando")
            if not rsi_ok:     motivos.append("RSI não alinhado")
            else:              confirmacoes.append("RSI alinhado")
            if not pullback:   motivos.append("Sem pullback EMA21")
            else:              confirmacoes.append("Pullback EMA21")

            # Reversão forte — RVOL >= 3.0 tem prioridade
            reversao_forte = rvol >= 3.0 and macd_ok and rsi_ok and pullback
            if reversao_forte:
                confirmacoes.append(f"REVERSÃO FORTE RVOL {rvol:.2f}")
                motivos = []  # limpa motivos — aprovação direta
            elif rvol < 0.7:
                motivos.append(f"RVOL {rvol:.2f} < 0.7")
            else:
                confirmacoes.append(f"RVOL {rvol:.2f}")

            # Bloqueio extremo H4
            if df4h is not None:
                r4h    = df4h.iloc[-1]
                adx_4h = float(r4h["adx"])
                tend_h4= float(r4h["ema21"]) > float(r4h["ema50"])
                h1_contra = (e10 < e21) if direcao=="LONG" else (e10 > e21)
                contra_h4 = (direcao=="LONG" and not tend_h4) or (direcao=="SHORT" and tend_h4)
                if contra_h4 and adx_4h > 35 and h1_contra and not bos and rvol < 1.2:
                    motivos.append(f"Bloqueio extremo H4 ADX={adx_4h:.0f}")

            score_min = 68
            rvol_min  = 0.7

        # ── SETUP 3: CRUZAMENTO ──────────────────────────────────────────────
        elif regime == "CRUZAMENTO":
            e10_ant = float(df["ema10"].iloc[-4])
            e21_ant = float(df["ema21"].iloc[-4])
            cruzou = (e10_ant<=e21_ant and e10>e21) if direcao=="LONG" else (e10_ant>=e21_ant and e10<e21)
            if not cruzou:     motivos.append("EMA10/21 não cruzou recentemente")
            else:              confirmacoes.append("EMA10 cruzou EMA21")
            if not macd_ok:    motivos.append("MACD não acelerando")
            else:              confirmacoes.append("MACD acelerando")
            if not vol_cresc:  motivos.append("Volume não crescente")
            else:              confirmacoes.append("Volume crescente")
            if rvol < 0.8:     motivos.append(f"RVOL {rvol:.2f} < 0.8")
            else:              confirmacoes.append(f"RVOL {rvol:.2f}")
            # Timing — máximo 3 velas após cruzamento
            dist_ema = abs(c - e21) / atr if atr > 0 else 0
            if dist_ema > 2.0: motivos.append(f"Entrada atrasada {dist_ema:.1f} ATR da EMA21")
            score_min = 70
            rvol_min  = 0.8

        # ── SETUP 4: LATERAL ─────────────────────────────────────────────────
        elif regime == "LATERAL":
            if not bos:        motivos.append("Sem rompimento confirmado (BOS)")
            else:              confirmacoes.append("Rompimento BOS")
            if not vol_cresc:  motivos.append("Volume fraco para rompimento")
            else:              confirmacoes.append("Volume forte")
            if rvol < 2.0:     motivos.append(f"RVOL {rvol:.2f} < 2.0 (lateral exige volume)")
            else:              confirmacoes.append(f"RVOL {rvol:.2f}")
            score_min = 80
            rvol_min  = 2.0

        # ── SETUP 5: TRANSIÇÃO ───────────────────────────────────────────────
        else:  # TRANSICAO
            if not bos:        motivos.append("Aguardar BOS/CHoCH de confirmação")
            else:              confirmacoes.append("BOS confirmado")
            if not vol_cresc:  motivos.append("Aguardar volume")
            else:              confirmacoes.append("Volume aumentando")
            if rvol < 1.2:     motivos.append(f"RVOL {rvol:.2f} insuficiente")
            else:              confirmacoes.append(f"RVOL {rvol:.2f}")
            score_min = 72
            rvol_min  = 1.2

        return motivos, confirmacoes, score_min, rvol_min

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO 4 — NÍVEIS
    # ─────────────────────────────────────────────────────────────────────────
    def _calcular_niveis(self, df, direcao):
        r   = df.iloc[-1]
        c   = float(r["close"])
        atr = float(r["atr"])

        if direcao == "LONG":
            swing_low = float(df["low"].iloc[-5:].min())
            stop = round(swing_low - atr*0.1, 6)
            if abs(c - stop) > atr*1.5: stop = round(c - atr*1.0, 6)
            risco = abs(c - stop)
            tp1 = round(c + risco*2.5, 6)
        else:
            swing_high = float(df["high"].iloc[-5:].max())
            stop = round(swing_high + atr*0.1, 6)
            if abs(stop - c) > atr*1.5: stop = round(c + atr*1.0, 6)
            risco = abs(stop - c)
            tp1 = round(c - risco*2.5, 6)

        rr = round(abs(tp1-c)/abs(stop-c), 2) if stop != c else 0
        return c, stop, tp1, atr, rr

    # ─────────────────────────────────────────────────────────────────────────
    # PASSO 5 — SCORE
    # ─────────────────────────────────────────────────────────────────────────
    def _calcular_score(self, df, regime, direcao, rvol, adx, rr, n_confs):
        r   = df.iloc[-1]
        rsi = float(r["rsi"])
        macd_h  = float(r["macd_hist"])
        macd_h2 = float(df["macd_hist"].iloc[-4])

        # Base por confirmações
        score = n_confs * 12

        # Bônus RVOL
        if rvol >= 3.0:   score += 10
        elif rvol >= 2.0: score += 7
        elif rvol >= 1.5: score += 4
        elif rvol >= 1.2: score += 2

        # Bônus ADX
        if adx >= 30:     score += 8
        elif adx >= 25:   score += 5
        elif adx < 15:    score -= 8

        # Bônus RR
        if rr >= 2.5:     score += 5
        elif rr < 2.0:    score -= 10

        # MACD acelerando
        macd_acel = (macd_h > macd_h2 and macd_h > 0) if direcao=="LONG" else (macd_h < macd_h2 and macd_h < 0)
        if macd_acel: score += 5

        # RSI zona certa
        if direcao=="LONG"  and 40 <= rsi <= 65: score += 3
        if direcao=="SHORT" and 35 <= rsi <= 60: score += 3

        score = max(0, min(90, score))

        if score >= 85:   tier = "OURO"
        elif score >= 75: tier = "PRATA"
        elif score >= 70: tier = "BRONZE"
        else:             tier = "ABAIXO"

        return score, tier

    # ─────────────────────────────────────────────────────────────────────────
    # GESTÃO DE BANCA
    # ─────────────────────────────────────────────────────────────────────────
    def _gestao_banca(self, score, entrada, stop, atr):
        if score >= 85:   alav = 20
        elif score >= 75: alav = 15
        elif score >= 70: alav = 10
        else:             alav = 8
        risco = round(BANCA * RISCO_PCT / 100, 2)
        dist  = abs(entrada - stop) / entrada if entrada else 0.01
        pos   = round(min(risco / dist, BANCA * 3), 2) if dist > 0 else 0
        return {"alavancagem":alav,"capital":BANCA,"posicao":pos,"risco_usdt":risco,"banca":BANCA}

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
        lim = 300
        try:
            df   = self._calc(self._fetch(symbol, tf, limit=lim))
            df4h = self._calc(self._fetch(symbol, "4h", limit=100))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"direcao":"—","rr":0,"rvol":0}

        r    = df.iloc[-1]
        adx  = float(r["adx"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0

        # PASSO 1: Regime
        regime = self._identificar_regime(df)

        # Transição: modo observação — não emitir sinal
        if regime == "TRANSICAO":
            return {"symbol":symbol,"aprovado":False,"score":0,"regime":regime,
                    "motivos_rejeicao":["Transição — aguardar confirmação"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol}

        # PASSO 2: Direção
        direcao = self._definir_direcao(df, regime)

        # PASSO 3: Filtros do setup
        motivos, confirmacoes, score_min, rvol_min = self._filtrar_por_setup(df, df4h, regime, direcao)

        # PASSO 4: Níveis
        entrada, stop, tp1, atr, rr = self._calcular_niveis(df, direcao)

        # PASSO 5: Score
        score, tier = self._calcular_score(df, regime, direcao, rvol, adx, rr, len(confirmacoes))

        # Checagem final
        if score < score_min:
            motivos.append(f"Score {score} < {score_min} ({regime})")
        if rr < 2.0:
            motivos.append(f"RR {rr} < 2.0")

        aprovado = len(motivos) == 0

        # Labels
        regime_labels = {
            "CONTINUACAO": "Continuação ↑" if direcao=="LONG" else "Continuação ↓",
            "REVERSAO":    "Reversão ↗" if direcao=="LONG" else "Reversão ↘",
            "CRUZAMENTO":  "Cruzamento EMA",
            "LATERAL":     "Lateral ↔",
            "TRANSICAO":   "Transição",
        }
        conv_map = {"OURO":"ALTA ✅","PRATA":"BOA ⚡","BRONZE":"MODERADA 🔶"}

        if score >= 85 and rvol >= 3.0:   prioridade = "🔥 REVERSÃO FORTE"
        elif score >= 85:                  prioridade = "🔥 PREMIUM"
        elif score >= 75:                  prioridade = "⭐ PRIORITÁRIO"
        else:                              prioridade = ""

        gb = self._gestao_banca(score, entrada, stop, atr)

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "setup_nome":       regime,
            "regime":           regime_labels.get(regime, regime),
            "direcao":          direcao,
            "score":            score,
            "tier":             tier,
            "conviccao":        conv_map.get(tier,"MODERADA 🔶"),
            "prioridade":       prioridade,
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
            "confluencia":      len(confirmacoes),
            "motivos_rejeicao": motivos,
            "o_que_falta":      motivos,
            "timeframe":        tf,
            "preco_atual":      entrada,
            **gb,
        }

    def analisar_tf(self, symbol, tf):
        return self._analisar_tf(symbol, tf)

    def obter_regime(self, symbol):
        df = self._calc(self._fetch(symbol, "1h"))
        r  = df.iloc[-1]
        regime = self._identificar_regime(df)
        return {"regime":regime,"adx":float(r["adx"]),"atr":float(r["atr"])}
