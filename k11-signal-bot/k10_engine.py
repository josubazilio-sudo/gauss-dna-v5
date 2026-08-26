"""
K12 Engine EQ V3 — Entry Quality Motor
Foco: qualidade do ponto de entrada, não quantidade de filtros
"""

import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone, timedelta
from config import (BANCA, RISCO_PCT, ENTRY_QUALITY_BLOCK, ENTRY_QUALITY_MIN, K11_OURO_MIN_EQ,
                      MODO_10_10, RVOL_MIN_10, RVOL_MIN_10_RAPIDO, SCORE_OURO_10, SCORE_PRATA_10, RR_MIN_10,
                      EXIGE_ESTRUTURA_10, EXIGE_TENDENCIA_10, EXIGE_FLOW_10, EXIGE_MOMENTUM_10,
                      EXIGE_ENTRY_50_10, ENTRY_50_PCT_10,
                      SOFT_FILTERS_MODE, QUALITY_FINAL_MIN, SOFT_PENALTY_MAX, RVOL_HARD_MIN,
                      STOP_DUPLO_ATIVO, STOP2_ATR_BUFFER, RISCO_ADAPTATIVO_ATIVO,
                      RISCO_MUITO_SAUDAVEL, RISCO_SAUDAVEL, RISCO_NORMAL, RISCO_FRACO,
                      STOP2_BUFFER_MUITO_SAUDAVEL, STOP2_BUFFER_SAUDAVEL,
                      STOP2_BUFFER_NORMAL, STOP2_BUFFER_FRACO)


def sessao_atual():
    h_utc = datetime.now(timezone.utc).hour
    h_brt = (h_utc - 3) % 24
    if 9 <= h_brt < 13:  return "LONDRES+NY", 100
    if 4 <= h_brt < 13:  return "LONDRES", 85
    if 9 <= h_brt < 18:  return "NY", 85
    return "FORA SESSÃO", 60


class K10Engine:
    def __init__(self):
        self.exchange = ccxt.mexc({
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })

    def _fetch(self, symbol, tf, limit=300):
        # RFC frequencia-sinais 23/08 (2a rodada): retry com backoff curto pra
        # erro 510 (rate limit) da MEXC. Antes, uma unica falha de rede matava
        # a analise inteira daquele symbol/tf no ciclo -- com outro processo
        # na mesma VPS tambem batendo na MEXC (mesmo IP, mesmo limite),
        # isso descartava boa parte do watchlist por ciclo sem nenhum erro de
        # logica. Nao muda nada quando a chamada ja funciona de primeira.
        ultimo_erro = None
        for tentativa in range(3):
            try:
                raw = self.exchange.fetch_ohlcv(symbol, tf, limit=limit)
                df  = pd.DataFrame(raw, columns=["ts","open","high","low","close","volume"])
                df["ts"] = pd.to_datetime(df["ts"], unit="ms")
                return df
            except Exception as e:
                ultimo_erro = e
                if "510" in str(e) or "too frequent" in str(e).lower():
                    time.sleep(0.6 * (tentativa + 1))
                    continue
                break
        raise RuntimeError(f"{symbol} {tf}: {ultimo_erro}")

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


    def _calc_ha(self, df):
        """Converte candles OHLCV para Heikin Ashi e recalcula indicadores."""
        ha = df.copy()
        ha["close"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
        ha_open = [(df["open"].iloc[0] + df["close"].iloc[0]) / 2]
        for i in range(1, len(df)):
            ha_open.append((ha_open[i-1] + ha["close"].iloc[i-1]) / 2)
        ha["open"]  = ha_open
        ha["high"]  = pd.concat([df["high"], ha["open"], ha["close"]], axis=1).max(axis=1)
        ha["low"]   = pd.concat([df["low"],  ha["open"], ha["close"]], axis=1).min(axis=1)
        ha["ts"]     = df["ts"]
        ha["volume"] = df["volume"]
        return self._calc(ha)

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

    def _entry_quality(self, df, direcao, ob_ok, ob_low, ob_high, bos_ok=False):
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
        det = {"ema21": 0, "ob_fvg": 0, "timing": 0, "rsi": 0, "bos": 0, "sr": 0}
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

        # 5. IDADE DO BOS — diferente para REVERSÃO vs CONTINUAÇÃO
        # Para REVERSÃO: componentes primários são Sweep + OB + EMA21
        #   BOS negativo pode ser esperado antes da reversão — não bloqueia
        # Para CONTINUAÇÃO: BOS é primário — penalização mantida
        bos_idade = self._bos_idade(df, direcao)
        sweep_presente = any("Liquidez" in str(c) or "Sweep" in str(c) for c in [ob_ok])
        ob_presente = ob_ok

        # Detectar se é setup de reversão (tem sweep ou OB)
        eh_reversao = ob_presente  # OB = zona institucional = reversão provável

        # RFC ajuste-b3 23/08: `bos_ok` (mesma definicao usada no cartao pra
        # "BOS confirmado", calculada em _analisar_tf) tem prioridade sobre
        # `_bos_idade()` -- que usa uma janela de swing diferente (5 velas)
        # e podia achar um rompimento "velho" mesmo com bos_ok=True agora,
        # causando a contradicao real observada: cartao mostrava "BOS
        # confirmado" (bonus) e Entry Quality mostrava "BOS -10" (penalidade)
        # pra MESMA vela. Se bos_ok=True, a estrutura esta confirmada AGORA
        # -- nunca pode penalizar.
        if bos_ok:
            eq += 15; det["bos"] = 15
        elif bos_idade <= 3:
            eq += 15; det["bos"] = 15
        elif bos_idade <= 6:
            eq += 5;  det["bos"] = 5
        elif bos_idade <= 10:
            if eh_reversao:
                # Reversão: BOS negativo é esperado — penalidade leve
                eq -= 5; det["bos"] = -5
            else:
                # Continuação: BOS é primário — penalidade normal
                eq -= 10; det["bos"] = -10
        else:
            if eh_reversao:
                # Reversão com Sweep/OB: não bloquear, só penalizar
                eq -= 10; det["bos"] = -10
            else:
                # Continuação sem BOS: bloqueio mantido
                bloqueado = True
                eq -= 20; det["bos"] = -20

        # 6. DISTÂNCIA ATÉ RESISTÊNCIA/SUPORTE PRÓXIMO
        # Penaliza entrada esticada contra S/R — não bloqueia, só reduz EQ
        try:
            lookback_sr = dfc.iloc[-20:]
            if direcao == "LONG":
                resistencia = float(lookback_sr["high"].iloc[:-2].max())
                dist_res = (resistencia - c) / atr if atr > 0 else 99
                if dist_res < 0:
                    # Preço já acima da resistência = rompimento
                    # Se RVOL forte = rompimento confirmado, bônus
                    rvol_val = float(r["rvol"]) if not __import__("numpy").isnan(r["rvol"]) else 0
                    if rvol_val >= 1.5:
                        eq += 5; det["sr"] = 5  # rompimento com volume
                    else:
                        eq -= 10; det["sr"] = -10  # rompimento sem volume
                elif dist_res < 0.5:
                    # Muito próximo da resistência — preferir pullback
                    eq -= 15; det["sr"] = -15
                elif dist_res < 1.0:
                    eq -= 5; det["sr"] = -5
                else:
                    det["sr"] = 0  # distância saudável
            else:  # SHORT
                suporte = float(lookback_sr["low"].iloc[:-2].min())
                dist_sup = (c - suporte) / atr if atr > 0 else 99
                if dist_sup < 0:
                    rvol_val = float(r["rvol"]) if not __import__("numpy").isnan(r["rvol"]) else 0
                    if rvol_val >= 1.5:
                        eq += 5; det["sr"] = 5
                    else:
                        eq -= 10; det["sr"] = -10
                elif dist_sup < 0.5:
                    eq -= 15; det["sr"] = -15
                elif dist_sup < 1.0:
                    eq -= 5; det["sr"] = -5
                else:
                    det["sr"] = 0
        except:
            det["sr"] = 0

        return max(0, min(100, eq)), det, bloqueado


    def _calcular_sr_dinamico(self, df):
        """
        Calcula Suporte e Resistência dinâmicos baseados em:
        - Pivot Points (High/Low/Close da sessão anterior)
        - Swing Highs e Lows recentes
        Similar ao AYN-Indicator
        """
        dfc = df.iloc[:-1]

        # Pivot Point clássico
        h = float(dfc["high"].iloc[-1])
        l = float(dfc["low"].iloc[-1])
        c = float(dfc["close"].iloc[-1])
        pp = (h + l + c) / 3

        r1 = 2 * pp - l
        r2 = pp + (h - l)
        s1 = 2 * pp - h
        s2 = pp - (h - l)

        # Swing Highs/Lows dos últimos 20 candles
        lookback = dfc.iloc[-20:]
        swing_h = float(lookback["high"].max())
        swing_l = float(lookback["low"].min())

        return {
            "pp": round(pp, 6),
            "r1": round(r1, 6),
            "r2": round(r2, 6),
            "s1": round(s1, 6),
            "s2": round(s2, 6),
            "swing_h": round(swing_h, 6),
            "swing_l": round(swing_l, 6),
        }

    def _analisar_tf(self, symbol, tf="1h", tf_contexto=None):
        try:
            ctx  = tf_contexto or ("1h" if tf=="30m" else "4h")
            df   = self._calc_ha(self._fetch(symbol, tf, limit=300))  # Heikin Ashi no TF principal
            df4h = self._calc(self._fetch(symbol, ctx, limit=100))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"direcao":"—","rr":0,"rvol":0}

        dfc = df.iloc[:-1]; r = dfc.iloc[-1]
        candle_ts = r["ts"].timestamp() if hasattr(r["ts"], "timestamp") else float(r["ts"])
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

        # ── K12 FILTROS ──────────────────────────────────────────────────────
        # 1. MACD TURN
        bars_since_cross = 0
        for i in range(-1, -5, -1):
            if dfc["macd_hist"].iloc[i-1] <= 0 and dfc["macd_hist"].iloc[i] > 0:
                bars_since_cross = abs(i) - 1
                break
        macd_turn_long = (bars_since_cross <= 2 and macd_h > 0 and macd_h > macd_h2)

        # 2. NOT EXTENDED
        MAX_DIST_EMA50_ATR = 1.8
        dist_ema50_atr = abs(c - e50) / max(atr, 1e-10)
        not_extended = dist_ema50_atr <= MAX_DIST_EMA50_ATR

        # 3. PULLBACK EMA21
        PULLBACK_ATR = 0.4
        recent_lows = [float(dfc["low"].iloc[i]) for i in range(-5, 0)]
        recent_closes = [float(dfc["close"].iloc[i]) for i in range(-5, 0)]
        recent_opens = [float(dfc["open"].iloc[i]) for i in range(-5, 0)]
        e21_recent = [float(dfc["ema21"].iloc[i]) for i in range(-5, 0)]
        pullback_long = any(
            l <= e21_recent[i] + atr * PULLBACK_ATR and
            recent_closes[i] >= e21_recent[i] and
            recent_closes[i] > recent_opens[i]
            for i, l in enumerate(recent_lows)
        )

        # 4. BULL CANDLE
        candle_range = max(float(r["high"]) - float(r["low"]), 1e-10)
        body_size = abs(c - float(r["open"]))
        body_ratio = body_size / candle_range
        bull_candle = (c > float(r["open"])) and body_ratio >= 0.30

        # 5. H1 QUALITY
        r4h_last = df4h.iloc[-2]
        h1_bull_bias = float(r4h_last["ema10"]) > float(r4h_last["ema21"])
        h1_momentum  = float(r4h_last["macd_hist"]) > 0
        h1_adx       = float(r4h_last["adx"]) >= 20
        h1_quality_long = (50 if h1_bull_bias else 0) + (25 if h1_momentum else 0) + (15 if h1_adx else 0)
        # ─────────────────────────────────────────────────────────────────────

        # Snapshot diagnóstico — SOMENTE observação (Shadow Outcome Tracking V1,
        # RFC 21/08). Nao decide nada, nao altera nenhum threshold/comparacao
        # existente acima. So repete valores ja calculados nas linhas acima,
        # pra que os retornos antecipados abaixo tambem carreguem o perfil
        # completo do candidato (hoje so o `rvol` sobrevivia a um bloqueio
        # antecipado). Campos que dependem da direcao ja resolvida (EQ,
        # estrutura/BOS, H1/H4) continuam indisponiveis nesses retornos —
        # o motor nunca chega a calcula-los quando bloqueia aqui, e isso nao
        # e alterado por este snapshot.
        diag_snapshot = {
            "candle_ts": candle_ts, "adx": adx, "rsi": rsi, "rvol": rvol,
            "ema10": e10, "ema21": e21, "ema50": e50, "ema200": e200,
            "macd_hist": macd_h, "vwap": vwap, "atr": atr,
            "dist_ema50_atr": round(dist_ema50_atr, 3),
            "not_extended": not_extended, "bull_candle": bull_candle,
            "pullback_long": pullback_long, "h1_quality_long": h1_quality_long,
            "macd_turn_long": macd_turn_long,
        }

        motivos = []
        confirmacoes = []
        score = 0
        # SOFT FILTERS MODE (RFC reequilibrio 22/08) — quando ligado, os
        # itens marcados SOFT abaixo tiram pontos de `soft_penalty` em vez
        # de irem pra `motivos` (que bloqueia). `motivos_soft` guarda o
        # texto pra diagnostico/card, sem impedir aprovacao sozinho.
        # Quando desligado (default), comportamento identico a antes.
        soft_penalty = 0
        motivos_soft = []

        def _bloqueio(texto: str, pontos_penalidade: int = 0, soft: bool = False):
            if soft and SOFT_FILTERS_MODE:
                nonlocal soft_penalty
                soft_penalty += pontos_penalidade
                motivos_soft.append(texto)
            else:
                motivos.append(texto)

        # BLOQUEIO 1: ADX
        if adx < 18:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"Mercado lateral ADX {adx:.1f}"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol, **diag_snapshot}

        # BLOQUEIO 2: RSI extremo
        if rsi < 25:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"RSI {rsi:.0f} sobrevendido — bounce iminente"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol, **diag_snapshot}
        if rsi > 75:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"RSI {rsi:.0f} sobrecomprado — pullback iminente"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol, **diag_snapshot}

        # BLOQUEIO 3: Preço esticado da EMA50
        if not not_extended:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"Preco esticado {dist_ema50_atr:.1f}x ATR da EMA50 (max 1.8x)"],
                    "timeframe":tf,"direcao":"—","rr":0,"rvol":rvol, **diag_snapshot}

        # BLOQUEIO 4: Candle sem corpo
        if not bull_candle and macd_h > 0:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"Candle sem confirmacao (body ratio {body_ratio:.2f} < 0.30)"],
                    "timeframe":tf,"direcao":"—","rr":0,"rvol":rvol, **diag_snapshot}

        # DIREÇÃO PELO MACD
        macd_cruzou_long  = any([macd_h2<=0 and macd_h>0, macd_h3<=0 and macd_h2>0, macd_h4<=0 and macd_h3>0])
        macd_cruzou_short = any([macd_h2>=0 and macd_h<0, macd_h3>=0 and macd_h2<0, macd_h4>=0 and macd_h3<0])
        macd_acel_long    = macd_h>0 and macd_h>macd_h2 and macd_h2>macd_h3
        macd_acel_short   = macd_h<0 and macd_h<macd_h2 and macd_h2<macd_h3

        # MACD declining filter: cruzamento válido mas histograma já caindo = entrada falsa
        macd_declining = macd_h < macd_h2 and macd_h2 < macd_h3

        if macd_cruzou_long:
            if macd_declining:
                return {"symbol":symbol,"aprovado":False,"score":0,
                        "motivos_rejeicao":[f"MACD cruzou mas histograma declinando — momentum perdido"],
                        "timeframe":tf,"direcao":"LONG","rr":0,"rvol":rvol, **diag_snapshot}
            direcao = "LONG";  confirmacoes.append("🎯 MACD cruzou para cima"); score += 25
        elif macd_cruzou_short:
            # SHORT bloqueado — WR histórico 19-22% vs LONG 38-39% (confirmado em 486 trades, 05-13/08)
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["SHORT bloqueado — WR histórico insuficiente (19%)"],
                    "timeframe":tf,"direcao":"SHORT","rr":0,"rvol":rvol, **diag_snapshot}
        elif macd_acel_long:
            ratio = abs(macd_h/macd_h4) if macd_h4!=0 else 99
            if ratio > 6.0:
                return {"symbol":symbol,"aprovado":False,"score":0,
                        "motivos_rejeicao":["MACD acelerou demais — atrasado"],"timeframe":tf,"direcao":"LONG","rr":0,"rvol":rvol, **diag_snapshot}
            direcao = "LONG";  confirmacoes.append("MACD acelerando ↑"); score += 15
        elif macd_acel_short:
            # SHORT bloqueado — WR histórico insuficiente (confirmado em 486 trades, 05-13/08)
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["SHORT bloqueado — WR histórico insuficiente (19%)"],
                    "timeframe":tf,"direcao":"SHORT","rr":0,"rvol":rvol, **diag_snapshot}
        else:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["MACD sem direção"],"timeframe":tf,"direcao":"—","rr":0,"rvol":rvol, **diag_snapshot}

        # EMA alinhada com direção
        # RFC reequilibrio-reversao 23/08: a decisao soft/hard so pode ser
        # tomada DEPOIS de saber se ha estrutura real (sweep/BOS) — por isso
        # aqui sempre bloqueia (hard) por enquanto; logo abaixo, apos a
        # estrutura ser calculada, reclassifica pra soft SE houver evidencia
        # de reversao confirmada. Dado real (3337 candidatos historicos):
        # EMA-contra COM estrutura Exp -0.28R vs SEM estrutura Exp -0.64R —
        # ainda negativo em ambos, mas a diferenca e grande o suficiente pra
        # nao tratar "cruzou a EMA" sozinho como motivo de reversao.
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
        # RFC correcao-15m5m 25/08: testado empiricamente contra dados reais
        # (25 simbolos, ambas direcoes) -- em 5m a janela original (20/6,6/1,
        # 10/2 velas) ja da a maior taxa de estrutura confirmada (88%); em
        # 15m, a MESMA janela cai pra 68%, e reduzir pela metade (10/3,3/1,
        # 5/1) sobe pra 84%. Aumentar a janela (testado antes) piorou os dois
        # -- swing mais amplo = nivel mais extremo = sweep menos provavel.
        # Sem mudanca para 30m/1h/4h/1d.
        if tf == "15m":
            lb_hi, lb_lo, sw_hi, sw_lo, bos_hi, bos_lo = 10, 3, 3, 1, 5, 1
        else:
            lb_hi, lb_lo, sw_hi, sw_lo, bos_hi, bos_lo = 20, 6, 6, 1, 10, 2

        sweep_ok = False
        sweep_extremo = 0.0  # preco do wick que varreu a liquidez (RFC stop-duplo 23/08)
        lookback = dfc.iloc[-lb_hi:-lb_lo]
        swing_high = float(lookback["high"].max())
        swing_low  = float(lookback["low"].min())
        for i in range(-sw_hi, -sw_lo):
            vela = dfc.iloc[i]
            hv=float(vela["high"]); lv=float(vela["low"]); cv=float(vela["close"])
            if direcao=="LONG" and lv < swing_low*1.001 and cv > swing_low:
                sweep_ok=True
                sweep_extremo = lv if sweep_extremo == 0.0 else min(sweep_extremo, lv)
            if direcao=="SHORT" and hv > swing_high*0.999 and cv < swing_high:
                sweep_ok=True
                sweep_extremo = hv if sweep_extremo == 0.0 else max(sweep_extremo, hv)

        highs = float(dfc["high"].iloc[-bos_hi:-bos_lo].max())
        lows  = float(dfc["low"].iloc[-bos_hi:-bos_lo].min())
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

        # EMA-contra: reclassifica de HARD pra SOFT somente se houver
        # estrutura real confirmada (sweep ou BOS) — "LONG REVERSÃO" exige
        # evidência, não só o cruzamento da EMA (RFC reequilibrio-reversao
        # 23/08). Sem estrutura, o bloqueio HARD acima permanece.
        estrutura_real = sweep_ok or bos_ok
        for _ema_motivo in ("EMA10 < EMA21 — contra LONG", "EMA10 > EMA21 — contra SHORT"):
            if SOFT_FILTERS_MODE and estrutura_real and _ema_motivo in motivos:
                motivos.remove(_ema_motivo)
                soft_penalty += 15
                motivos_soft.append(f"{_ema_motivo} (aceito: reversão com estrutura confirmada)")

        # PULLBACK score (K12)
        if pullback_long:
            confirmacoes.append("Pullback EMA21"); score += 10
        else:
            _bloqueio("Sem pullback EMA21", 10, soft=True)

        # RFC ajuste-b3 23/08: bloco "H1 QUALITY score" removido daqui --
        # duplicava a MESMA confirmacao (contexto H1/H4 alinhado) que a
        # secao "CONTEXTO SUPERIOR" abaixo ja pontua (macd_ctx_ok/tend_ctx_ok,
        # +18/+8), so que calculada de outro jeito (h1_quality_long composto).
        # Resultado real observado: "H1 MACD+EMA confirmando" aparecia 2x no
        # cartao e o score somava os dois (+10 E +18 pela mesma coisa),
        # inflando o Score artificialmente. h1_quality_long continua
        # calculado (usado no diag_snapshot/shadow tracker), so nao pontua
        # mais aqui.

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
        elif rvol >= RVOL_HARD_MIN:
            # RVOL moderado-baixo: SOFT em soft mode (penalidade, nao bloqueia
            # sozinho). Abaixo de RVOL_HARD_MIN continua bloqueio duro (RFC:
            # "RVOL muito baixo -> bloqueio", mercado sem liquidez real).
            _bloqueio(f"Volume insuficiente RVOL {rvol:.2f}", 10, soft=True)
        else:
            motivos.append(f"Volume muito baixo RVOL {rvol:.2f} < {RVOL_HARD_MIN} (sem liquidez)")

        # CONTEXTO SUPERIOR
        ctx_label = {"1h":"H1","4h":"H4","30m":"M30"}.get(ctx, ctx.upper())
        r4h = df4h.iloc[-1]
        macd_ctx = float(r4h["macd_hist"])
        e21_ctx  = float(r4h["ema21"]); e50_ctx = float(r4h["ema50"])
        adx_ctx  = float(r4h["adx"])
        tend_ctx = e21_ctx > e50_ctx
        macd_ctx_ok = (macd_ctx>0 and direcao=="LONG") or (macd_ctx<0 and direcao=="SHORT")
        tend_ctx_ok = (tend_ctx and direcao=="LONG") or (not tend_ctx and direcao=="SHORT")

        if not tend_ctx_ok and adx_ctx > 28:
            # RFC correcao-15m5m 25/08: em 30m/1h/4h/1d este bloqueio segue
            # HARD sempre (decisao RFC reequilibrio-reversao 23/08, validada
            # com dados reais daqueles timeframes: mesmo com estrutura
            # confirmada, Exp continuava negativo). Nunca revalidado para
            # 5m/15m — la, suaviza igual ao padrao ja usado em EMA-contra e
            # no GATE 10/10 "sem tendencia alinhada": SOFT somente quando ha
            # estrutura real confirmada (sweep ou BOS), senao HARD.
            if tf in ("5m", "15m") and (bos_ok or sweep_ok):
                _bloqueio(f"{ctx_label} contra tendência forte (aceito: estrutura confirmada)", 15, soft=True)
            else:
                motivos.append(f"❌ {ctx_label} contra tendência forte")
        elif macd_ctx_ok and tend_ctx_ok:
            confirmacoes.append(f"✅ {ctx_label} MACD+EMA confirmando"); score += 18
        elif tend_ctx_ok:
            confirmacoes.append(f"{ctx_label} tendência ok"); score += 8

        # SESSÃO — bônus de score mas sem mostrar no cartão
        if peso_sessao == 100:   score += 5
        elif peso_sessao >= 85:  score += 3

        score = min(score, 100)

        # NÍVEIS
        # Calcular S/R dinâmico
        try:
            sr = self._calcular_sr_dinamico(df)
        except:
            sr = {"r1": 0, "r2": 0, "s1": 0, "s2": 0, "swing_h": 0, "swing_l": 0}

        if direcao == "LONG":
            stop_base = ob_low if ob_ok else float(dfc["low"].iloc[-6:].min())
            stop = round(stop_base - atr*0.1, 6)
            if abs(c-stop)/c > 0.06: stop = round(c*0.95, 6)
            risco = abs(c-stop)
            # TP1 na R1 (próxima resistência) se for melhor que 1.5R
            tp1_sr = sr["r1"] if sr["r1"] > c * 1.005 else 0
            tp1_rr = round(c + risco*2.0, 6)
            tp1 = tp1_sr if tp1_sr > 0 and tp1_sr < tp1_rr * 1.3 and abs(tp1_sr-c)/risco >= 1.5 else tp1_rr
            # TP2 na R2 ou swing high
            tp2_sr = sr["r2"] if sr["r2"] > tp1 else sr["swing_h"]
            tp2_rr = round(c + risco*3.5, 6)
            tp2 = tp2_sr if tp2_sr > tp1 and tp2_sr < c*1.25 else tp2_rr
            be  = round(c + risco*1.0, 6)
            if tp1 > c*1.15: tp1 = round(c*1.10, 6)
            if tp2 > c*1.25: tp2 = round(c*1.18, 6)
        else:
            stop_base = ob_high if ob_ok else float(dfc["high"].iloc[-6:].max())
            stop = round(stop_base + atr*0.1, 6)
            if abs(stop-c)/c > 0.06: stop = round(c*1.06, 6)
            risco = abs(stop-c)
            # TP1 no S1 se for melhor que 1.5R
            tp1_sr = sr["s1"] if sr["s1"] < c * 0.995 else 0
            tp1_rr = round(c - risco*2.0, 6)
            tp1 = tp1_sr if tp1_sr > 0 and tp1_sr > tp1_rr * 0.7 and abs(tp1_sr-c)/risco >= 1.5 else tp1_rr
            # TP2 no S2 ou swing low
            tp2_sr = sr["s2"] if sr["s2"] < tp1 else sr["swing_l"]
            tp2_rr = round(c - risco*3.5, 6)
            tp2 = tp2_sr if 0 < tp2_sr < tp1 and tp2_sr > c*0.75 else tp2_rr
            be  = round(c - risco*1.0, 6)
            if tp1 < c*0.85 or tp1 <= 0: tp1 = round(c*0.90, 6)
            if tp2 < c*0.75 or tp2 <= 0: tp2 = round(c*0.85, 6)

        entrada = c
        rr = round(abs(tp2-c)/abs(stop-c), 2) if stop != c else 0

        # ENTRY QUALITY V3
        try:
            eq, eq_det, eq_bloqueado = self._entry_quality(df, direcao, ob_ok, ob_low, ob_high, bos_ok)
        except:
            eq, eq_det, eq_bloqueado = 50, {"ema21":0,"ob_fvg":0,"timing":0,"rsi":0,"bos":0}, False

        # GATE ENTRY QUALITY — late entry bloqueia sinal
        # RFC reequilibrio 22/08: EQ baixa + estrutura excepcional + RR alto
        # nao bloqueia mais automaticamente, so penaliza (soft). eq_bloqueado
        # (preco > 1.5 ATR da EMA21, ou continuacao sem BOS) continua HARD
        # sempre — isso e sobre extensao/estrutura, nao so "atraso".
        # RFC frequencia-sinais 23/08: removido o requisito macd_ctx_ok daqui.
        # Numa reversao real (sweep/BOS + RR bom), o MACD do H4 ainda NAO
        # virou por definicao — exigir macd_ctx_ok pra liberar o piso de EQ
        # era contraditorio com o proprio conceito de reversao (RFC pediu
        # explicitamente pra permitir EMA/H4/MACD parcialmente contra num
        # setup de reversao). RR>=3.0 + estrutura real seguem sendo o filtro
        # de seguranca — nao removidos.
        estrutura_excepcional = (bos_ok or sweep_ok) and rr >= 3.0
        eq_min_efetivo = ENTRY_QUALITY_MIN
        if SOFT_FILTERS_MODE and estrutura_excepcional:
            eq_min_efetivo = 50
        if ENTRY_QUALITY_BLOCK and (eq_bloqueado or eq < eq_min_efetivo):
            # RFC eficiencia-gate 23/08: a mensagem antiga sempre dizia "EQ X <
            # Y" mesmo quando o bloqueio veio de `eq_bloqueado` (extensao >1.5
            # ATR da EMA21, ou continuacao sem BOS recente) -- uma causa
            # totalmente diferente do valor de EQ, produzindo mensagens
            # matematicamente falsas tipo "Entry Quality 55 < 50". O bloqueio
            # em si continua legitimo (extensao extrema e risco real), so a
            # descricao agora reflete a causa de fato.
            if eq_bloqueado:
                motivos.append(f"Entrada esticada/sem estrutura recente (EQ={eq})")
            else:
                motivos.append(f"Entry Quality {eq} < {eq_min_efetivo} (late entry)")
            eq_bloqueado = True
        elif ENTRY_QUALITY_BLOCK and eq < ENTRY_QUALITY_MIN:
            _bloqueio(f"Entry Quality {eq} < {ENTRY_QUALITY_MIN} (aceito por estrutura excepcional)", 15, soft=True)

        # MODO CALIBRAÇÃO — EQ registra, não bloqueia
        # OURO V2: exige zona institucional (OB ou FVG ou reteste EMA21)
        tem_ob_fvg = any("Order Block" in x or "FVG" in x for x in confirmacoes)
        reteste_ema = abs(c - e21) / atr <= 0.5 if atr > 0 else False
        tem_zona_institucional = tem_ob_fvg or reteste_ema

        ouro_ok = (
            score >= 85 and eq >= K11_OURO_MIN_EQ and rvol >= 1.5 and
            tem_zona_institucional and  # obrigatório OB, FVG ou reteste EMA21
            any("H1" in x or "H4" in x for x in confirmacoes) and
            any("BOS" in x or "Liquidez" in x or "Tendência forte" in x for x in confirmacoes)
        )
        # PRATA: score>=75, RVOL>=1.0 — boa continuação sem zona ideal
        prata_ok = score >= 75 and rvol >= 1.0

        # ----- MODO 10/10: limiares rígidos p/ OURO/PRATA -----
        if MODO_10_10:
            ouro_ok  = (score >= SCORE_OURO_10 and rvol >= RVOL_MIN_10
                        and rr >= RR_MIN_10 and tem_zona_institucional)
            prata_ok = score >= SCORE_PRATA_10 and rvol >= RVOL_MIN_10 and rr >= RR_MIN_10

        # CHECAGEM FINAL — bloqueios críticos (base)
        # RFC reequilibrio 22/08: em soft mode, Score deixa de bloquear
        # sozinho (vira parte de quality_final abaixo); RVOL base ja foi
        # tratado com piso RVOL_HARD_MIN la na secao de volume. RR continua
        # HARD sempre (RFC explicito: "RR muito baixo" nunca vira soft).
        if not SOFT_FILTERS_MODE:
            if score < 75:   motivos.append(f"Score {score} < 75")
            if rvol < 1.0:   motivos.append(f"RVOL {rvol:.2f} < 1.0")
        if rr < 2.0:     motivos.append(f"RR {rr} < 2.0")

        # ----- GATE 10/10: qualidade sobre quantidade -----
        if MODO_10_10:
            # RFC correcao-15m5m 25/08: RVOL_MIN_10=1.80 foi calibrado para
            # 30m/1h; em 5m/15m usa-se o piso separado RVOL_MIN_10_RAPIDO,
            # calibrado sobre o RVOL real observado nesses timeframes.
            rvol_min_10_efetivo = RVOL_MIN_10_RAPIDO if tf in ("5m", "15m") else RVOL_MIN_10
            if not SOFT_FILTERS_MODE:
                if rvol < rvol_min_10_efetivo:
                    motivos.append(f"10/10 RVOL {rvol:.2f} < {rvol_min_10_efetivo}")
            elif rvol < rvol_min_10_efetivo and rvol >= RVOL_HARD_MIN:
                _bloqueio(f"10/10 RVOL {rvol:.2f} < {rvol_min_10_efetivo}", 10, soft=True)
                # RVOL < RVOL_HARD_MIN já bloqueou HARD na seção de volume acima.

            if rr < RR_MIN_10:
                motivos.append(f"10/10 RR {rr:.2f} < {RR_MIN_10}")  # HARD sempre

            if EXIGE_TENDENCIA_10 and not tend_ctx_ok:
                # RFC reequilibrio-reversao 23/08: H4 desalinhado so vira soft
                # com estrutura real confirmada (dado: com estrutura Exp
                # -0.59R vs sem estrutura Exp -0.88R). H4 CONTRA FORTE
                # (bloqueio da linha ~546) continua HARD sempre, sem excecao.
                if SOFT_FILTERS_MODE and (bos_ok or sweep_ok):
                    soft_penalty += 15
                    motivos_soft.append(f"10/10 {ctx_label} sem tendência alinhada (aceito: estrutura confirmada)")
                else:
                    motivos.append(f"10/10 {ctx_label} sem tendência alinhada")

            if EXIGE_ESTRUTURA_10 and not (bos_ok or sweep_ok):
                motivos.append("10/10 sem BOS/CHoCH confirmado")  # HARD sempre

            if EXIGE_FLOW_10 and not tem_zona_institucional:
                _bloqueio("10/10 sem zona institucional (OB/FVG/reteste)", 10, soft=True)

            if EXIGE_MOMENTUM_10 and not macd_ctx_ok:
                _bloqueio(f"10/10 MACD {ctx_label} contra direção", 10, soft=True)

            if EXIGE_ENTRY_50_10:
                org = ob_low if (direcao=="LONG" and ob_ok) else (ob_high if (direcao=="SHORT" and ob_ok) else entrada)
                run = abs(c - org) if org > 0 else 0
                dist_tp = abs(tp1 - org) if org > 0 else 0
                if dist_tp > 0 and run / dist_tp > ENTRY_50_PCT_10:
                    _bloqueio(f"10/10 entrada atrasada {run/dist_tp*100:.0f}% até TP1", 10, soft=True)

        # quality_final = score menos penalidades soft, COM TETO (RFC
        # frequencia-sinais 23/08: sem teto, penalidades simultaneas — EMA+
        # MACD+zona+RVOL — chegavam a somar 45pts e matavam candidatos de
        # score 85-99 mesmo com estrutura real confirmada. Ver SOFT_PENALTY_MAX
        # em config.py pro dado que embasou o valor. `motivos_soft` continua
        # listando TODOS os filtros soft acionados (sem teto) — só o efeito
        # no gate de aprovacao e limitado. Em modo estrito (default)
        # soft_penalty é sempre 0, então quality_final == score sempre —
        # comportamento idêntico a antes.
        quality_final = max(0, round(score - min(soft_penalty, SOFT_PENALTY_MAX)))

        if SOFT_FILTERS_MODE and quality_final < QUALITY_FINAL_MIN:
            motivos.append(f"Quality Final {quality_final} < {QUALITY_FINAL_MIN}")

        aprovado = len(motivos) == 0

        # Nova classificação de qualidade (RFC reequilibrio 22/08) — SEMPRE
        # calculada, mas só passa a determinar aprovação em SOFT_FILTERS_MODE.
        # Coexiste com o tier OURO/PRATA/ABAIXO existente (não o substitui —
        # final_selector.py, apex_engine.py e o formatter continuam lendo
        # `tier` normalmente).
        if quality_final >= 90:   tier_qualidade = "APEX"
        elif quality_final >= 80: tier_qualidade = "PRO"
        elif quality_final >= 70: tier_qualidade = "SETUP"
        else:                     tier_qualidade = "ABAIXO"

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


        # ----- AUDITORIA GATE 10/10 -----
        _audit = {
            "Score":          "PASS" if (score >= SCORE_PRATA_10 if MODO_10_10 else score >= 75) else "FAIL",
            "RR":             "PASS" if rr >= (RR_MIN_10 if MODO_10_10 else 2.0) else "FAIL",
            "RVOL":           "PASS" if rvol >= (RVOL_MIN_10 if MODO_10_10 else 1.0) else "FAIL",
            "Trend H1/H4":    "PASS" if tend_ctx_ok else "FAIL",
            "EMA Alignment":  "PASS" if (e10 > e21 and direcao == "LONG") or (e10 < e21 and direcao == "SHORT") else "FAIL",
            "BOS/CHoCH":      "PASS" if (bos_ok or sweep_ok) else "FAIL",
            "Order Block":    "PASS" if (ob_ok or reteste_ema) else "FAIL",
            "FVG":            "PASS" if tem_ob_fvg else "FAIL",
            "Liquidity Sweep":"PASS" if sweep_ok else "FAIL",
            "MACD":           "PASS" if macd_ctx_ok else "FAIL",
            "VWAP":           "PASS" if (c >= vwap and direcao == "LONG") or (c <= vwap and direcao == "SHORT") else "FAIL",
            "Entry Quality":  "PASS" if eq >= (K11_OURO_MIN_EQ if tier == "OURO" else ENTRY_QUALITY_MIN) else "FAIL",
            "Final Decision": "APPROVED" if aprovado else "REJECTED",
        }

        # ==== STOP 1 / STOP 2 + RISCO ADAPTATIVO (RFC stop-duplo 23/08) ====
        # Calculado por ULTIMO, depois de aprovado/motivos/tier/rr/TPs ja
        # resolvidos com o `stop` original (agora chamado STOP1) — nao
        # influencia gate nenhum, so o que sai no cartao/registro e (se os
        # flags estiverem ligados) o `stop` final e o position sizing.

        # Regime de saude reaproveita a classificacao de qualidade JA
        # EXISTENTE (tier_qualidade, RFC reequilibrio 22/08) — nao cria
        # criterio novo, so mapeia pra risco% E pro buffer do STOP2. RFC
        # protecao-liquidez 23/08 (2a rodada): pedido explicito do usuario
        # pra que mercado forte tenha stop mais largo (mais chance de
        # alcancar o alvo) e mercado fraco tenha stop mais apertado (menos
        # risco) -- antes o buffer do STOP2 era fixo (1x ATR) pra qualquer
        # sinal, independente da forca do setup.
        _SAUDE_MAP = {
            "APEX":   ("MUITO_SAUDAVEL", RISCO_MUITO_SAUDAVEL, STOP2_BUFFER_MUITO_SAUDAVEL),
            "PRO":    ("SAUDAVEL",       RISCO_SAUDAVEL,       STOP2_BUFFER_SAUDAVEL),
            "SETUP":  ("NORMAL",         RISCO_NORMAL,         STOP2_BUFFER_NORMAL),
            "ABAIXO": ("FRACO",          RISCO_FRACO,          STOP2_BUFFER_FRACO),
        }
        saude_mercado, risco_pct_sugerido, stop2_buffer_sugerido = _SAUDE_MAP.get(
            tier_qualidade, ("NORMAL", RISCO_NORMAL, STOP2_BUFFER_NORMAL))
        risco_pct_aplicado = risco_pct_sugerido if RISCO_ADAPTATIVO_ATIVO else RISCO_PCT
        stop2_buffer_aplicado = stop2_buffer_sugerido if RISCO_ADAPTATIVO_ATIVO else STOP2_ATR_BUFFER

        stop1 = stop
        dist_stop1 = abs(c - stop1)
        if direcao == "LONG":
            # RFC protecao-liquidez 23/08: quando houve sweep confirmado,
            # `sweep_extremo` (o pavio real que varreu a liquidez) entra
            # como referencia explicita -- antes o STOP2 so olhava
            # `swing_low` (a zona ampla) e ficava abaixo do pavio real só
            # por proximidade (sweep_ok exige lv < swing_low*1.001, uma
            # diferenca de no maximo 0.1%), nao por garantia. Agora e
            # garantido: STOP2 sempre fica alem do pavio observado.
            referencias = [swing_low, stop1]
            if sweep_ok and sweep_extremo:
                referencias.append(sweep_extremo)
            stop2_base = min(referencias)
            stop2 = round(stop2_base - atr * stop2_buffer_aplicado, 6)
            stop2 = min(stop2, stop1)               # STOP2 nunca mais apertado que STOP1
            if abs(c - stop2) / c > 0.12:
                stop2 = round(c * 0.90, 6)           # protecao de emergencia — teto 12%
            liquidez_relevante = sweep_extremo if (sweep_ok and sweep_extremo) else swing_low
        else:
            referencias = [swing_high, stop1]
            if sweep_ok and sweep_extremo:
                referencias.append(sweep_extremo)
            stop2_base = max(referencias)
            stop2 = round(stop2_base + atr * stop2_buffer_aplicado, 6)
            stop2 = max(stop2, stop1)
            if abs(stop2 - c) / c > 0.12:
                stop2 = round(c * 1.10, 6)
            liquidez_relevante = sweep_extremo if (sweep_ok and sweep_extremo) else swing_high
        dist_stop2 = abs(c - stop2)

        stop_final = stop2 if STOP_DUPLO_ATIVO else stop1
        dist_final = abs(c - stop_final)

        gb_risco = round(BANCA * risco_pct_aplicado / 100, 2)
        dist = dist_final/c if c else 0.01
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
            "audit_10of10":     _audit,
            "tier":             tier,
            "conviccao":        conv,
            "prioridade":       prioridade,
            "entrada":          entrada,
            "stop":             stop_final,
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
            "sr":               sr,
            "capital":          BANCA,
            "posicao":          pos,
            "risco_usdt":       gb_risco,
            "alavancagem":      alav,
            "candle_ts":        candle_ts,
            "banca":            BANCA,
            # RFC reequilibrio 22/08 — aditivo, coexiste com `score`/`tier`.
            "quality_final":    quality_final,
            "tier_qualidade":   tier_qualidade,
            "soft_penalty":     soft_penalty,
            "motivos_soft":     motivos_soft,
            "soft_filters_mode": SOFT_FILTERS_MODE,
            # RFC stop-duplo 23/08 — aditivo. stop1/stop2 sempre calculados
            # (observacao); `stop` acima so vira stop2 se STOP_DUPLO_ATIVO.
            "stop1":                stop1,
            "stop2":                stop2,
            "dist_stop1":           round(dist_stop1, 6),
            "dist_stop2":           round(dist_stop2, 6),
            "sweep_extremo":        sweep_extremo if sweep_extremo else None,
            "liquidez_relevante":   liquidez_relevante,
            "saude_mercado":        saude_mercado,
            "risco_pct_aplicado":   risco_pct_aplicado,
            "stop2_buffer_aplicado": stop2_buffer_aplicado,
            "stop_duplo_ativo":     STOP_DUPLO_ATIVO,
            "risco_adaptativo_ativo": RISCO_ADAPTATIVO_ATIVO,
            **diag_snapshot,
        }

    def analisar(self, symbol, timeframe=None):
        pares = [("15m","1h"), ("5m","30m")]
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
