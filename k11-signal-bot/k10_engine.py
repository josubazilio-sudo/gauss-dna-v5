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

        # RVOL auditado — RFC V4.0
        # SMA20 usando apenas velas fechadas, sem divisão por zero, sem NaN
        vol_sma20 = v.rolling(20, min_periods=10).mean()
        vol_valido = vol_sma20 > 0
        rvol_raw = v / vol_sma20.where(vol_valido, np.nan)
        # Clamp para evitar valores absurdos
        df["vol_ma"] = vol_sma20
        df["rvol"]   = rvol_raw.clip(lower=0, upper=50)

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
    def _score_final(self, score_virada, rr, rvol, adx, n_confs,
                      eh_reversao=False, bos_ok=False, pullback_ok=False):
        """
        Score RFC V4 — penalidade de reversão + bônus RVOL institucional
        """
        score = score_virada

        # RR
        if rr < 1.5:
            score -= 15

        # RVOL — bônus por volume institucional (RFC V4)
        if rvol >= 3.0:
            score += 8    # bônus máximo
        elif rvol >= 2.0:
            score += 5    # bônus qualidade
        elif rvol >= 1.2:
            score += 2
        elif rvol < 0.8:
            score -= 8

        # ADX
        if adx < 15:
            score -= 8

        # Confirmações extras
        score += min(n_confs, 3) * 2

        # Penalidade de reversão (RFC V4)
        if eh_reversao:
            penalidade = 4  # padrão 3-5 pts
            # Remover penalidade se BOS/CHoCH + Pullback + RVOL >= 2.0
            if bos_ok and pullback_ok and rvol >= 2.0:
                penalidade = 0
            score -= penalidade

        score = max(0, min(90, score))

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




    # ─────────────────────────────────────────────────────────────────────────
    # RFC K11 V4.0 — RVOL AUDITADO + ADAPTATIVO
    # ─────────────────────────────────────────────────────────────────────────

    def _calcular_rvol_auditado(self, df, symbol, tf):
        """
        Calcula RVOL com validações completas.
        Retorna (rvol, valido, detalhes)
        """
        try:
            v        = df["close"].copy()  # usar volume
            vol_ser  = df["volume"]
            
            # Usar penúltima vela (fechada), não a atual (em formação)
            vol_atual = float(vol_ser.iloc[-2])
            sma20     = float(vol_ser.iloc[-21:-1].mean())  # 20 velas fechadas

            # Validações
            if sma20 <= 0 or np.isnan(sma20):
                return 1.0, False, "SMA20=0 ou NaN — RVOL_INVALID"
            if vol_atual <= 0 or np.isnan(vol_atual):
                return 1.0, False, "Volume=0 ou NaN — RVOL_INVALID"
            if len(vol_ser) < 21:
                return 1.0, False, "Menos de 21 velas — RVOL_INVALID"

            rvol = round(vol_atual / sma20, 3)
            detalhes = {
                "vol_atual": round(vol_atual, 0),
                "sma20":     round(sma20, 0),
                "rvol":      rvol,
            }
            return rvol, True, detalhes

        except Exception as e:
            return 1.0, False, f"Erro RVOL: {e}"

    def _filtro_tf_institucional(self, df, direcao, entrada, tp1, df4h=None, rr=0,
                                  rvol_auditado=None, rvol_valido=True,
                                  market_low_volume=False):
        r       = df.iloc[-1]
        motivos = []

        c       = float(r["close"])
        e10     = float(r["ema10"])
        e21     = float(r["ema21"])
        e50     = float(r["ema50"])
        atr     = float(r["atr"])
        adx     = float(r["adx"])
        rsi     = float(r["rsi"])
        rvol    = rvol_auditado if rvol_auditado is not None else (
                  float(r["rvol"]) if not np.isnan(r["rvol"]) else 1.0)
        macd_h  = float(r["macd_hist"])
        macd_h2 = float(df["macd_hist"].iloc[-3])
        rsi_ant = float(df["rsi"].iloc[-3])

        # ── CONFLUÊNCIA BASE ─────────────────────────────────────────────────
        conf = 0
        ema_virando  = (e10 > e21) if direcao=="LONG" else (e10 < e21)
        macd_ok      = (macd_h > 0 and macd_h > macd_h2) if direcao=="LONG" else (macd_h < 0 and macd_h < macd_h2)
        rsi_ok       = (rsi > rsi_ant) if direcao=="LONG" else (rsi < rsi_ant)
        highs        = float(df["high"].rolling(10).max().iloc[-5])
        lows         = float(df["low"].rolling(10).min().iloc[-5])
        bos_ok       = (c > highs) if direcao=="LONG" else (c < lows)
        dist_ema21   = abs(c - e21) / atr if atr > 0 else 99
        pullback_ok  = dist_ema21 <= 1.5
        vol_crescente= float(df["volume"].iloc[-1]) > float(df["volume"].iloc[-2])

        if ema_virando:   conf += 1
        if macd_ok:       conf += 1
        if rsi_ok:        conf += 1
        if bos_ok:        conf += 1
        if pullback_ok:   conf += 1
        if vol_crescente: conf += 1

        forte_conf = conf >= 4

        # Score estimado para regra de decisão RVOL
        score_alto = False  # será preenchido pelo caller se score >= 80

        # ── 1. RVOL ADAPTATIVO ───────────────────────────────────────────────
        tendencia_local = (e10 > e21 > e50) if direcao=="LONG" else (e10 < e21 < e50)
        eh_reversao = not tendencia_local

        # Limite base
        rvol_base = 1.15 if eh_reversao else 0.90
        # Reduzir 20% em MARKET_LOW_VOLUME, nunca abaixo de 0.60
        if market_low_volume:
            rvol_base = max(0.60, rvol_base * 0.80)
        # Alta confluência reduz o exigido
        if forte_conf:
            rvol_base = max(0.60, rvol_base * 0.75)

        # Se RVOL inválido — não reprovar
        if not rvol_valido:
            pass  # RVOL_INVALID — não reprovar
        elif rvol < rvol_base:
            # RFC V4.0 regra 6: nunca bloquear se score alto + confluências fortes
            qualidade_alta = (forte_conf and bos_ok and pullback_ok and macd_ok and rsi_ok and adx >= 20)
            if qualidade_alta:
                pass  # penalidade de score aplicada pelo caller (-5 pts)
            elif conf < 3:
                motivos.append(f"RVOL {rvol:.2f} < {rvol_base:.2f} com confluência fraca ({conf}/6)")

        # ── 2. ADX ──────────────────────────────────────────────────────────
        di_p = float(r["di_p"]) if "di_p" in df.columns else 0
        di_n = float(r["di_n"]) if "di_n" in df.columns else 0
        di_sem_dir = abs(di_p - di_n) < 5
        if adx < 18 and di_sem_dir and conf < 3:
            motivos.append(f"Mercado lateral (ADX {adx:.1f}) sem confluência")

        # ── 3. EMAs ──────────────────────────────────────────────────────────
        emas_inversas = (e10 < e21 and e21 < e50) if direcao=="LONG" else (e10 > e21 and e21 > e50)
        if emas_inversas and adx > 28 and not forte_conf:
            motivos.append(f"Tendência contrária forte (ADX {adx:.1f})")

        # ── 4. MACD ──────────────────────────────────────────────────────────
        if not macd_ok and conf < 3:
            motivos.append("MACD sem direção e confluência insuficiente")

        # ── 5. TIMING ────────────────────────────────────────────────────────
        if tp1 != entrada:
            pct = abs(c - entrada) / abs(tp1 - entrada) * 100
            if pct > 30:
                motivos.append(f"Sinal atrasado {pct:.0f}%")

        # ── 6. H4 ───────────────────────────────────────────────────────────
        if df4h is not None:
            r4h    = df4h.iloc[-1]
            adx_4h = float(r4h["adx"])
            tend_h4= float(r4h["ema21"]) > float(r4h["ema50"])
            if direcao=="LONG" and not tend_h4 and adx_4h > 30 and not forte_conf:
                motivos.append(f"H4 queda forte (ADX {adx_4h:.0f})")
            if direcao=="SHORT" and tend_h4 and adx_4h > 30 and not forte_conf:
                motivos.append(f"H4 alta forte (ADX {adx_4h:.0f})")

        return motivos, conf

    def _analisar_tf(self, symbol, tf="1h", market_low_volume=False):
        lim = 200 if tf in ("4h","1d") else 300
        try:
            df   = self._calc(self._fetch(symbol, tf, limit=lim))
            df4h = self._calc(self._fetch(symbol, "4h", limit=100))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"direcao":"—","rr":0,
                    "rvol":0,"adx":0,"vol_atual":0,"sma20_vol":0}

        r    = df.iloc[-1]
        adx  = float(r["adx"])

        # RVOL auditado
        rvol, rvol_valido, rvol_det = self._calcular_rvol_auditado(df, symbol, tf)

        direcao, tipo, score_virada, confirmacoes = self._detectar_virada(df)
        if direcao is None:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":confirmacoes,"timeframe":tf,"direcao":"—","rr":0,
                    "rvol":rvol,"adx":adx,"vol_atual":0,"sma20_vol":0}

        entrada, stop, tp1, atr = self._calcular_niveis(df, direcao)
        rr = round(abs(tp1 - entrada) / abs(stop - entrada), 2) if stop != entrada else 0
        # RFC V4: detectar reversão e BOS/Pullback para score
        e10_s = float(df.iloc[-1]["ema10"])
        e21_s = float(df.iloc[-1]["ema21"])
        e50_s = float(df.iloc[-1]["ema50"])
        atr_s = float(df.iloc[-1]["atr"])
        c_s   = float(df.iloc[-1]["close"])
        tendencia_local = (e10_s > e21_s > e50_s) if direcao=="LONG" else (e10_s < e21_s < e50_s)
        eh_reversao_s   = not tendencia_local
        highs_s = float(df["high"].rolling(10).max().iloc[-5])
        lows_s  = float(df["low"].rolling(10).min().iloc[-5])
        bos_s   = (c_s > highs_s) if direcao=="LONG" else (c_s < lows_s)
        pull_s  = abs(c_s - e21_s) / atr_s <= 1.5 if atr_s > 0 else False
        score, tier = self._score_final(score_virada, rr, rvol, adx, len(confirmacoes),
                                        eh_reversao=eh_reversao_s, bos_ok=bos_s, pullback_ok=pull_s)

        motivos = []

        # Filtro V4.0
        falhas, conf = self._filtro_tf_institucional(
            df, direcao, entrada, tp1, df4h, rr=rr,
            rvol_auditado=rvol, rvol_valido=rvol_valido,
            market_low_volume=market_low_volume
        )
        # Processar marcadores RFC V4.3.1
        penalidade_extra = 0
        falhas_reais     = []
        nivel_decisao    = 0
        log_reversao     = ""

        for f in falhas:
            if f == "__PENALIDADE_REVERSAO_5__":
                penalidade_extra += 5
            elif f.startswith("__NIVEL_1__"):
                falhas_reais.append(f.replace("__NIVEL_1__ ",""))
                nivel_decisao = 1
            elif f == "__NIVEL_2_OK__":
                nivel_decisao = 2   # aprovado
            elif f == "__NIVEL_3_OK__":
                nivel_decisao = 3   # aprovado
            elif f.startswith("__LOG_REVERSAO__"):
                log_reversao = f    # guardar para retorno
            else:
                falhas_reais.append(f)

        motivos.extend(falhas_reais)

        if penalidade_extra > 0:
            score = max(0, score - penalidade_extra)
            nivel_decisao = 4
            if score >= 82:   tier = "OURO"
            elif score >= 72: tier = "PRATA"
            elif score >= 62: tier = "BRONZE"
            else:             tier = "ABAIXO"

        # Penalidade de score se RVOL baixo mas qualidade alta
        if rvol < 0.70 and rvol_valido:
            score = max(0, score - 5)

        if score < 70:
            motivos.append(f"Score {score} < 70")
        if rr < 2.0:
            motivos.append(f"RR {rr} < 2.0")

        aprovado = len(motivos) == 0

        e10_v = float(r["ema10"]); e21_v = float(r["ema21"]); e50_v = float(r["ema50"])
        if   e10_v > e21_v > e50_v and direcao=="LONG":   regime_label = "Tendência Alta ↑"
        elif e10_v < e21_v < e50_v and direcao=="SHORT":  regime_label = "Tendência Baixa ↓"
        elif e10_v < e21_v < e50_v and direcao=="LONG":   regime_label = "Reversão ↗"
        elif e10_v > e21_v > e50_v and direcao=="SHORT":  regime_label = "Reversão ↘"
        elif adx < 18:                                     regime_label = "Lateral ↔"
        else:                                              regime_label = "Transição"

        if score >= 80:   prioridade = "🔥 PREMIUM"
        elif score >= 75: prioridade = "⭐ PRIORITÁRIO"
        else:             prioridade = ""

        conv_map = {"OURO":"ALTA ✅","PRATA":"BOA ⚡","BRONZE":"MODERADA 🔶"}
        gb = self._gestao_banca(score, entrada, stop, atr)

        vol_det = rvol_det if isinstance(rvol_det, dict) else {}

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "setup_nome":       tipo,
            "regime":           regime_label,
            "prioridade":       prioridade,
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
            "rvol_valido":      rvol_valido,
            "vol_atual":        vol_det.get("vol_atual", 0),
            "sma20_vol":        vol_det.get("sma20", 0),
            "confluencia":      conf,
            "vwap":             float(r["vwap"]),
            "ema21":            float(r["ema21"]),
            "confirmacoes_smc": confirmacoes,
            "nivel_decisao":    nivel_decisao,
            "log_reversao":     log_reversao,
            "timing_pct":       0,
            "confluencia":      len(confirmacoes),
            "rvol_bonus":       rvol >= 2.0,
            "motivos_rejeicao": motivos,
            "o_que_falta":      motivos,
            "timeframe":        tf,
            "preco_atual":      entrada,
            **gb,
        }


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
