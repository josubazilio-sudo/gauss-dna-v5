"""
K11 Engine — Entrada de Precisão
Regras:
1. Liquidez já consumida (sweep aconteceu)
2. MACD cruzando AGORA (não cruzou há 5 velas)
3. EMA10 cruzando EMA21 AGORA
4. Volume no cruzamento
5. Preço não esticado — máximo 1 ATR do cruzamento
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
        df["adx"] = (100*(dm_p.ewm(span=14,adjust=False).mean()/atr14 -
                         dm_n.ewm(span=14,adjust=False).mean()/atr14).abs() /
                    (dm_p.ewm(span=14,adjust=False).mean()/atr14 +
                     dm_n.ewm(span=14,adjust=False).mean()/atr14).replace(0,np.nan)
                    ).ewm(span=14,adjust=False).mean()
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

    def _analisar_tf(self, symbol, tf="1h", tf_contexto=None):
        try:
            # Contexto: TF superior confirma direção
            ctx = tf_contexto or ("1h" if tf=="30m" else "4h" if tf=="1h" else "1d")
            df   = self._calc(self._fetch(symbol, tf, limit=300))
            df4h = self._calc(self._fetch(symbol, ctx, limit=100))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"direcao":"—","rr":0,"rvol":0}

        dfc = df.iloc[:-1]  # só velas fechadas
        r   = dfc.iloc[-1]
        r2  = dfc.iloc[-2]
        r3  = dfc.iloc[-3]
        r4  = dfc.iloc[-4]

        c    = float(r["close"])
        atr  = float(r["atr"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0

        # Indicadores atuais e anteriores
        macd_h  = float(r["macd_hist"])
        macd_h2 = float(r2["macd_hist"])
        macd_h3 = float(r3["macd_hist"])
        macd_h4 = float(r4["macd_hist"])

        e10  = float(r["ema10"]);  e10_2 = float(r2["ema10"])
        e21  = float(r["ema21"]);  e21_2 = float(r2["ema21"])
        e50  = float(r["ema50"])
        e200 = float(r["ema200"])
        rsi  = float(r["rsi"]);    rsi2  = float(r2["rsi"])
        adx  = float(r["adx"])

        motivos = []
        confirmacoes = []
        score = 0
        flexibilizacao = ""

        # ── PASSO 1: MACD CRUZANDO AGORA ─────────────────────────────────────
        # Cruzamento nas últimas 2 velas fechadas
        macd_cruzou_long  = macd_h2 <= 0 and macd_h > 0  # cruzou na última vela
        macd_cruzou_short = macd_h2 >= 0 and macd_h < 0
        macd_acele_long   = macd_h > 0 and macd_h > macd_h2 and macd_h2 > macd_h3  # acelerando
        macd_acele_short  = macd_h < 0 and macd_h < macd_h2 and macd_h2 < macd_h3

        if macd_cruzou_long:
            direcao = "LONG"
            confirmacoes.append("🎯 MACD cruzou para cima AGORA")
            score += 30
        elif macd_cruzou_short:
            direcao = "SHORT"
            confirmacoes.append("🎯 MACD cruzou para baixo AGORA")
            score += 30
        elif macd_acele_long:
            direcao = "LONG"
            confirmacoes.append("MACD acelerando para cima")
            score += 18
        elif macd_acele_short:
            direcao = "SHORT"
            confirmacoes.append("MACD acelerando para baixo")
            score += 18
        else:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["MACD sem cruzamento ou aceleração recente"],
                    "timeframe":tf,"direcao":"—","rr":0,"rvol":rvol}

        # ── PASSO 2: LIQUIDEZ JÁ CONSUMIDA ───────────────────────────────────
        # Verificar nas últimas 6 velas se houve sweep + rejeição
        janela = dfc.iloc[-6:]
        swing_high = float(dfc.iloc[-20:-6]["high"].max())
        swing_low  = float(dfc.iloc[-20:-6]["low"].min())

        sweep_long  = False  # varreu stops de baixo e voltou
        sweep_short = False  # varreu stops de cima e voltou

        for i in range(len(janela)-1):
            vela = janela.iloc[i]
            vela_c = float(vela["close"])
            vela_l = float(vela["low"])
            vela_h = float(vela["high"])

            # Sweep de baixa: furou o swing low mas fechou acima
            if vela_l < swing_low * 1.001 and vela_c > swing_low:
                sweep_long = True

            # Sweep de alta: furou o swing high mas fechou abaixo
            if vela_h > swing_high * 0.999 and vela_c < swing_high:
                sweep_short = True

        # BOS confirmado — rompimento forte da estrutura
        bos_long  = float(dfc["close"].iloc[-1]) > float(dfc["high"].iloc[-10:-2].max())
        bos_short = float(dfc["close"].iloc[-1]) < float(dfc["low"].iloc[-10:-2].min())

        if direcao == "LONG":
            if sweep_long:
                confirmacoes.append("✅ Liquidez consumida — sweep do fundo")
                score += 25
            elif bos_long and rvol >= 0.8:
                confirmacoes.append("✅ BOS confirmado — rompimento forte (sem sweep)")
                score += 15
                flexibilizacao = "Sweep ausente compensado por BOS + volume"
            else:
                motivos.append("Sem sweep de liquidez nem BOS confirmado")

        if direcao == "SHORT":
            if sweep_short:
                confirmacoes.append("✅ Liquidez consumida — sweep do topo")
                score += 25
            elif bos_short and rvol >= 0.8:
                confirmacoes.append("✅ BOS confirmado — rompimento forte (sem sweep)")
                score += 15
                flexibilizacao = "Sweep ausente compensado por BOS + volume"
            else:
                motivos.append("Sem sweep de liquidez nem BOS confirmado")

        # ── PASSO 3: EMA10 CRUZANDO EMA21 ────────────────────────────────────
        ema_cruzou_long  = e10_2 <= e21_2 and e10 > e21
        ema_cruzou_short = e10_2 >= e21_2 and e10 < e21
        ema_alinha_long  = e10 > e21 and e50 > e200
        ema_alinha_short = e10 < e21 and e50 < e200

        if direcao == "LONG":
            if ema_cruzou_long:
                confirmacoes.append("🎯 EMA10 cruzou EMA21 para cima AGORA")
                score += 20
            elif ema_alinha_long:
                confirmacoes.append("EMAs alinhadas para cima")
                score += 10
            else:
                motivos.append("EMAs não favoráveis para LONG")
        else:
            if ema_cruzou_short:
                confirmacoes.append("🎯 EMA10 cruzou EMA21 para baixo AGORA")
                score += 20
            elif ema_alinha_short:
                confirmacoes.append("EMAs alinhadas para baixo")
                score += 10
            else:
                motivos.append("EMAs não favoráveis para SHORT")

        # ── PASSO 4: VOLUME NO CRUZAMENTO ────────────────────────────────────
        if rvol >= 1.5:
            confirmacoes.append(f"🔥 Volume forte RVOL {rvol:.2f}")
            score += 20
        elif rvol >= 0.8:
            confirmacoes.append(f"Volume RVOL {rvol:.2f}")
            score += 10
        elif rvol >= 0.65:
            confirmacoes.append(f"Volume RVOL {rvol:.2f}")
            score += 5
            # Score alto — flexibilização RVOL (avaliado no final)
        else:
            motivos.append(f"Volume fraco RVOL {rvol:.2f}")

        # ── PASSO 5: PREÇO NÃO ESTICADO ──────────────────────────────────────
        # Preço deve estar próximo do cruzamento — máximo 1.5 ATR da EMA21
        dist_ema21 = abs(c - e21) / atr if atr > 0 else 99
        if dist_ema21 <= 1.0:
            confirmacoes.append("Entrada no início do movimento")
            score += 10
        elif dist_ema21 <= 1.5:
            confirmacoes.append(f"Entrada próxima ({dist_ema21:.1f} ATR)")
            score += 5
        else:
            motivos.append(f"Preço esticado {dist_ema21:.1f} ATR — movimento já andou")

        # ── RSI ───────────────────────────────────────────────────────────────
        rsi_long  = rsi > rsi2 and rsi < 68
        rsi_short = rsi < rsi2 and rsi > 32
        if direcao == "LONG" and rsi_long:
            confirmacoes.append(f"RSI {rsi:.0f} subindo")
            score += 5
        elif direcao == "SHORT" and rsi_short:
            confirmacoes.append(f"RSI {rsi:.0f} caindo")
            score += 5

        # ── H4 ───────────────────────────────────────────────────────────────
        r4h    = df4h.iloc[-1]
        adx_4h = float(r4h["adx"])
        tend_h4= float(r4h["ema21"]) > float(r4h["ema50"])
        macd_h4_v = float(r4h["macd_hist"])
        h4_ok = (tend_h4 and direcao=="LONG") or (not tend_h4 and direcao=="SHORT")
        ctx_label = tf_contexto or ("H1" if tf=="30m" else "H4" if tf=="1h" else "D1")
        if h4_ok:
            # Bônus extra se contexto superior também tem MACD na direção
            macd_ctx = float(r4h["macd_hist"])
            macd_ctx_ok = (macd_ctx > 0 and direcao=="LONG") or (macd_ctx < 0 and direcao=="SHORT")
            if macd_ctx_ok:
                confirmacoes.append(f"✅ {ctx_label} MACD + tendência confirmando")
                score += 15
            else:
                confirmacoes.append(f"{ctx_label} tendência favorável")
                score += 5
        elif adx_4h > 30:
            motivos.append(f"{ctx_label} tendência forte contra ADX={adx_4h:.0f}")

        score = min(score, 100)

        # ── NÍVEIS ────────────────────────────────────────────────────────────
        if direcao == "LONG":
            # Stop abaixo da mínima do sweep
            stop_base = float(dfc["low"].iloc[-6:].min())
            stop = round(stop_base - atr*0.1, 6)
            if abs(c-stop)/c > 0.05: stop = round(c*0.95, 6)
            risco = abs(c-stop)
            tp1   = round(c + risco*2.5, 6)
            if tp1 > c*1.12: tp1 = round(c*1.10, 6)
        else:
            stop_base = float(dfc["high"].iloc[-6:].max())
            stop = round(stop_base + atr*0.1, 6)
            if abs(stop-c)/c > 0.05: stop = round(c*1.05, 6)
            risco = abs(stop-c)
            tp1   = round(c - risco*2.5, 6)
            if tp1 < c*0.88 or tp1 <= 0: tp1 = round(c*0.90, 6)

        rr = round(abs(tp1-c)/abs(stop-c), 2) if stop != c else 0

        # ── CHECAGEM FINAL ────────────────────────────────────────────────────
        # RVOL adaptativo por score
        rvol_min = 0.65 if score >= 90 else 0.80 if score >= 80 else 0.90
        motivos_rvol = [m for m in motivos if "Volume fraco" in m]
        if motivos_rvol and rvol >= rvol_min:
            # Flexibilização aplicada
            motivos = [m for m in motivos if "Volume fraco" not in m]
            confirmacoes.append(f"⚡ Flexibilização: RVOL {rvol:.2f} aceito (score {score})")

        # Score mínimo — nunca reprovar score >=90 por filtro único fraco
        if score >= 90 and len(motivos) == 1:
            motivo_unico = motivos[0]
            # Se o único motivo não é crítico, flexibilizar
            nao_criticos = ["Volume fraco", "esticado", "Flexibilização"]
            if any(nc in motivo_unico for nc in nao_criticos):
                confirmacoes.append(f"⚡ Score {score} — flexibilização aplicada")
                motivos = []

        if score < 65:   motivos.append(f"Score {score} < 65")
        if rr < 2.0:     motivos.append(f"RR {rr} < 2.0")

        aprovado = len(motivos) == 0

        if score >= 85:   tier = "OURO"
        elif score >= 75: tier = "PRATA"
        elif score >= 65: tier = "BRONZE"
        else:             tier = "ABAIXO"

        conv = {"OURO":"ALTA ✅","PRATA":"BOA ⚡","BRONZE":"MODERADA 🔶"}.get(tier,"MODERADA 🔶")

        if macd_cruzou_long or macd_cruzou_short:
            prioridade = "🎯 CRUZAMENTO AGORA"
        elif score >= 85:
            prioridade = "🔥 ALTA QUALIDADE"
        else:
            prioridade = ""

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
            "flexibilizacao":    flexibilizacao,
            "o_que_falta":      motivos,
            "timeframe":        tf,
            "tf_contexto":      ctx_label,
            "preco_atual":      c,
            "capital":          BANCA,
            "posicao":          pos,
            "risco_usdt":       gb_risco,
            "alavancagem":      alav,
            "banca":            BANCA,
        }

    def analisar(self, symbol, timeframe=None):
        """
        Hierarquia de timeframes:
        30m  → contexto H1
        1h   → contexto H4
        4h   → contexto Diário
        1d   → contexto Semanal (só EMA/MACD)
        """
        if timeframe:
            return self._analisar_tf(symbol, timeframe)

        # Mapa: TF entrada → TF contexto
        pares = [
            ("30m", "1h"),
            ("1h",  "4h"),
            ("4h",  "1d"),
        ]

        resultados = []
        for tf_entrada, tf_contexto in pares:
            try:
                r = self._analisar_tf(symbol, tf_entrada, tf_contexto=tf_contexto)
                resultados.append(r)
            except:
                pass

        if not resultados:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["Erro ao analisar"],"timeframe":"—","direcao":"—","rr":0,"rvol":0}

        aprovados = [r for r in resultados if r.get("aprovado")]
        if aprovados:
            return max(aprovados, key=lambda x: x["score"])
        return max(resultados, key=lambda x: x["score"])

    def analisar_tf(self, symbol, tf):
        return self._analisar_tf(symbol, tf)

    def obter_regime(self, symbol):
        df = self._calc(self._fetch(symbol, "1h"))
        r  = df.iloc[-1]
        return {"regime":"K11","adx":float(r["adx"]),"atr":float(r["atr"])}
