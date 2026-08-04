"""
K11 Engine — SMC Completo
Order Block + FVG + Liquidity Sweep + CHoCH + Sessões
Entrada só após captura de liquidez confirmada.
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from config import BANCA, RISCO_PCT


# Sessões de mercado (UTC)
SESSOES = {
    "ASIA":     (0,  8),   # 00h-08h UTC
    "LONDRES":  (7,  16),  # 07h-16h UTC — melhor
    "NOVA_YORK":(12, 21),  # 12h-21h UTC — melhor
    "MORTO":    (21, 0),   # 21h-00h UTC — evitar
}

def sessao_atual():
    h_utc = datetime.now(timezone.utc).hour
    h_brt = (h_utc - 3) % 24  # Brasília UTC-3

    # Sessões em horário de Brasília (BRT)
    # Londres: 04h-13h BRT | NY: 09h-18h BRT
    londre_brt = 4 <= h_brt < 13
    ny_brt     = 9 <= h_brt < 18
    asia_brt   = 21 <= h_brt or h_brt < 4

    if londre_brt and ny_brt:
        return f"LONDRES+NY ({h_brt:02d}h BRT)", 100
    if ny_brt:
        return f"NOVA YORK ({h_brt:02d}h BRT)", 85
    if londre_brt:
        return f"LONDRES ({h_brt:02d}h BRT)", 85
    if asia_brt:
        return f"ÁSIA ({h_brt:02d}h BRT)", 60
    # Entre sessões
    return f"TRANSIÇÃO ({h_brt:02d}h BRT)", 70


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
    # SMC 1 — ORDER BLOCK
    # ─────────────────────────────────────────────────────────────────────────
    def _detectar_order_block(self, df, direcao):
        """
        Order Block: última vela de direção oposta antes de movimento forte.
        LONG: última vela vermelha antes de subida forte = OB de compra
        SHORT: última vela verde antes de queda forte = OB de venda
        """
        dfc = df.iloc[:-1]
        atr = float(dfc["atr"].iloc[-1])
        c_atual = float(dfc["close"].iloc[-1])

        for i in range(-3, -15, -1):
            try:
                vela     = dfc.iloc[i]
                proxima  = dfc.iloc[i+1]
                o = float(vela["open"]); c = float(vela["close"])
                h_p = float(proxima["high"]); l_p = float(proxima["low"])
                vol_p = float(proxima["rvol"]) if not np.isnan(proxima["rvol"]) else 0

                if direcao == "LONG":
                    # Vela vermelha seguida de vela verde forte com volume
                    eh_ob = (c < o and                          # vela vermelha
                             float(proxima["close"]) > float(proxima["open"]) and  # próxima verde
                             vol_p >= 1.0 and                   # volume forte
                             float(proxima["close"]) - float(proxima["open"]) > atr * 0.5)  # movimento forte
                    if eh_ob:
                        ob_high = float(vela["high"])
                        ob_low  = float(vela["low"])
                        # Preço atual deve estar próximo do OB (retestando)
                        if ob_low <= c_atual <= ob_high * 1.005:
                            return True, ob_low, ob_high, abs(i)

                else:  # SHORT
                    # Vela verde seguida de vela vermelha forte
                    eh_ob = (c > o and
                             float(proxima["close"]) < float(proxima["open"]) and
                             vol_p >= 1.0 and
                             float(proxima["open"]) - float(proxima["close"]) > atr * 0.5)
                    if eh_ob:
                        ob_high = float(vela["high"])
                        ob_low  = float(vela["low"])
                        if ob_low * 0.995 <= c_atual <= ob_high:
                            return True, ob_low, ob_high, abs(i)
            except:
                continue

        return False, 0, 0, 0

    # ─────────────────────────────────────────────────────────────────────────
    # SMC 2 — FAIR VALUE GAP
    # ─────────────────────────────────────────────────────────────────────────
    def _detectar_fvg(self, df, direcao):
        """
        FVG: gap entre máxima da vela 1 e mínima da vela 3 (ou vice-versa).
        Mercado tende a preencher o gap = alvo natural.
        """
        dfc = df.iloc[:-1]
        c_atual = float(dfc["close"].iloc[-1])

        for i in range(-2, -20, -1):
            try:
                v1 = dfc.iloc[i-1]
                v3 = dfc.iloc[i+1]

                if direcao == "LONG":
                    # FVG de alta: mínima v3 > máxima v1
                    fvg_low  = float(v1["high"])
                    fvg_high = float(v3["low"])
                    if fvg_high > fvg_low and c_atual <= fvg_high:
                        return True, fvg_low, fvg_high

                else:
                    # FVG de baixa: máxima v3 < mínima v1
                    fvg_high = float(v1["low"])
                    fvg_low  = float(v3["high"])
                    if fvg_low < fvg_high and c_atual >= fvg_low:
                        return True, fvg_low, fvg_high
            except:
                continue

        return False, 0, 0

    # ─────────────────────────────────────────────────────────────────────────
    # SMC 3 — LIQUIDITY SWEEP
    # ─────────────────────────────────────────────────────────────────────────
    def _detectar_sweep(self, df, direcao):
        """Captura de liquidez nas últimas 6 velas."""
        dfc = df.iloc[:-1]
        lookback = dfc.iloc[-20:-6]
        swing_high = float(lookback["high"].max())
        swing_low  = float(lookback["low"].min())

        for i in range(-6, -1):
            vela = dfc.iloc[i]
            h_v = float(vela["high"]); l_v = float(vela["low"])
            c_v = float(vela["close"]); o_v = float(vela["open"])

            if direcao == "LONG":
                if l_v < swing_low * 1.001 and c_v > swing_low:
                    return True, swing_low
            else:
                if h_v > swing_high * 0.999 and c_v < swing_high:
                    return True, swing_high

        return False, 0

    # ─────────────────────────────────────────────────────────────────────────
    # ANÁLISE PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────
    def _analisar_tf(self, symbol, tf="1h", tf_contexto=None):
        try:
            ctx  = tf_contexto or ("1h" if tf=="30m" else "4h" if tf=="1h" else "1d")
            df   = self._calc(self._fetch(symbol, tf, limit=300))
            df4h = self._calc(self._fetch(symbol, ctx, limit=100))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[str(e)],"timeframe":tf,"direcao":"—","rr":0,"rvol":0}

        dfc = df.iloc[:-1]
        r   = dfc.iloc[-1]; r2 = dfc.iloc[-2]; r3 = dfc.iloc[-3]; r4 = dfc.iloc[-4]

        c    = float(r["close"]); atr = float(r["atr"])
        e10  = float(r["ema10"]); e21 = float(r["ema21"])
        e50  = float(r["ema50"]); e200= float(r["ema200"])
        adx  = float(r["adx"]);   rsi = float(r["rsi"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        macd_h  = float(r["macd_hist"])
        macd_h2 = float(r2["macd_hist"])
        macd_h3 = float(r3["macd_hist"])
        vwap    = float(r["vwap"])
        rsi2    = float(r2["rsi"])

        motivos = []
        confirmacoes = []
        score = 0

        # ── SESSÃO DE MERCADO ─────────────────────────────────────────────────
        sessao, peso_sessao = sessao_atual()

        # Verificar se é ativo tradicional (respeita horário) ou cripto (24h)
        sym_base = symbol.replace("/USDT:USDT","").upper()
        eh_tradicional = any(t in sym_base for t in [
            "XAU","XAUT","SILVER","USOIL","SPX","NDX","GOLD",
            "SPCX","SNDK","SOXL","SOXS","STOCK","OIL","SILVER"
        ])

        # Tradicionais respeitam horário de mercado
        if eh_tradicional and peso_sessao < 60:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":[f"Mercado fechado — {sessao} (melhor: Londres 04h-13h BRT / NY 09h-18h BRT)"],
                    "timeframe":tf,"direcao":"—","rr":0,"rvol":rvol,
                    "sessao":sessao}

        # Cripto 24h — NUNCA bloqueia por sessão
        # Sessão só serve como informação e bônus de score

        # ── DIREÇÃO PELO MACD ─────────────────────────────────────────────────
        macd_cruzou_long  = macd_h2 <= 0 and macd_h > 0
        macd_cruzou_short = macd_h2 >= 0 and macd_h < 0
        macd_acele_long   = macd_h > 0 and macd_h > macd_h2 and macd_h2 > macd_h3
        macd_acele_short  = macd_h < 0 and macd_h < macd_h2 and macd_h2 < macd_h3

        if macd_cruzou_long:
            direcao = "LONG"; confirmacoes.append("🎯 MACD cruzou agora"); score += 30
        elif macd_cruzou_short:
            direcao = "SHORT"; confirmacoes.append("🎯 MACD cruzou agora"); score += 30
        elif macd_acele_long:
            macd_ratio = abs(macd_h/macd_h3) if macd_h3 != 0 else 99
            if macd_ratio > 3.0:
                return {"symbol":symbol,"aprovado":False,"score":0,
                        "motivos_rejeicao":["MACD acelerou demais — entrada atrasada"],
                        "timeframe":tf,"direcao":"LONG","rr":0,"rvol":rvol}
            direcao = "LONG"; confirmacoes.append("MACD acelerando"); score += 18
        elif macd_acele_short:
            macd_ratio = abs(macd_h/macd_h3) if macd_h3 != 0 else 99
            if macd_ratio > 3.0:
                return {"symbol":symbol,"aprovado":False,"score":0,
                        "motivos_rejeicao":["MACD acelerou demais — entrada atrasada"],
                        "timeframe":tf,"direcao":"SHORT","rr":0,"rvol":rvol}
            direcao = "SHORT"; confirmacoes.append("MACD acelerando"); score += 18
        else:
            return {"symbol":symbol,"aprovado":False,"score":0,
                    "motivos_rejeicao":["MACD sem direção"],
                    "timeframe":tf,"direcao":"—","rr":0,"rvol":rvol}

        # ── SMC 1: LIQUIDITY SWEEP ────────────────────────────────────────────
        sweep_ok, sweep_nivel = self._detectar_sweep(df, direcao)
        if sweep_ok:
            confirmacoes.append("✅ Liquidez capturada")
            score += 25
        else:
            # BOS como alternativa
            highs = float(dfc["high"].iloc[-10:-2].max())
            lows  = float(dfc["low"].iloc[-10:-2].min())
            bos_ok = (c > highs and rvol >= 0.8) if direcao=="LONG" else (c < lows and rvol >= 0.8)
            if bos_ok:
                confirmacoes.append("✅ BOS confirmado")
                score += 15
            else:
                motivos.append("Sem captura de liquidez nem BOS")

        # ── SMC 2: ORDER BLOCK ────────────────────────────────────────────────
        ob_ok, ob_low, ob_high, ob_dist = self._detectar_order_block(df, direcao)
        if ob_ok:
            confirmacoes.append(f"🏛 Order Block ({ob_dist} velas atrás)")
            score += 20

        # ── SMC 3: FAIR VALUE GAP ─────────────────────────────────────────────
        fvg_ok, fvg_low, fvg_high = self._detectar_fvg(df, direcao)
        if fvg_ok:
            confirmacoes.append(f"📊 FVG detectado")
            score += 10

        # ── VWAP ──────────────────────────────────────────────────────────────
        vwap_ok = (c > vwap and direcao=="LONG") or (c < vwap and direcao=="SHORT")
        if vwap_ok:
            confirmacoes.append("VWAP favorável")
            score += 8

        # ── RSI ───────────────────────────────────────────────────────────────
        rsi_long  = rsi > rsi2 and rsi < 68
        rsi_short = rsi < rsi2 and rsi > 32
        if (direcao=="LONG" and rsi_long) or (direcao=="SHORT" and rsi_short):
            confirmacoes.append(f"RSI {rsi:.0f} favorável")
            score += 8

        # ── EMAs ──────────────────────────────────────────────────────────────
        ema_long  = e10 > e21 and e50 > e200
        ema_short = e10 < e21 and e50 < e200
        if (direcao=="LONG" and ema_long) or (direcao=="SHORT" and ema_short):
            confirmacoes.append("EMAs alinhadas")
            score += 12
        elif (direcao=="LONG" and e10 > e21) or (direcao=="SHORT" and e10 < e21):
            confirmacoes.append("EMA10/21 favorável")
            score += 6

        # ── VOLUME ────────────────────────────────────────────────────────────
        if rvol >= 1.5:
            confirmacoes.append(f"🔥 Volume RVOL {rvol:.2f}")
            score += 15
        elif rvol >= 0.8:
            confirmacoes.append(f"Volume RVOL {rvol:.2f}")
            score += 8
        else:
            motivos.append(f"Volume insuficiente RVOL {rvol:.2f}")

        # ── CONTEXTO SUPERIOR ─────────────────────────────────────────────────
        ctx_label = "H1" if tf=="30m" else "H4" if tf=="1h" else "D1"
        r4h = df4h.iloc[-1]
        macd_ctx = float(r4h["macd_hist"])
        macd_ctx2= float(df4h["macd_hist"].iloc[-3])
        e21_ctx  = float(r4h["ema21"]); e50_ctx = float(r4h["ema50"])
        tend_ctx = e21_ctx > e50_ctx
        macd_ctx_ok = (macd_ctx > 0 and direcao=="LONG") or (macd_ctx < 0 and direcao=="SHORT")
        tend_ctx_ok = (tend_ctx and direcao=="LONG") or (not tend_ctx and direcao=="SHORT")

        if macd_ctx_ok and tend_ctx_ok:
            confirmacoes.append(f"✅ {ctx_label} confirmando")
            score += 15
        elif tend_ctx_ok:
            confirmacoes.append(f"{ctx_label} tendência ok")
            score += 5
        else:
            adx_ctx = float(r4h["adx"])
            if adx_ctx > 30:
                motivos.append(f"{ctx_label} contra tendência forte")

        # ── SESSÃO bônus ──────────────────────────────────────────────────────
        if peso_sessao == 100:
            confirmacoes.append(f"🕐 {sessao} — máximo volume")
            score += 10
        elif peso_sessao >= 85:
            confirmacoes.append(f"🕐 {sessao}")
            score += 5

        score = min(score, 100)

        # ── NÍVEIS ────────────────────────────────────────────────────────────
        if direcao == "LONG":
            # Stop atrás do Order Block ou sweep
            stop_base = ob_low if ob_ok else float(dfc["low"].iloc[-6:].min())
            stop = round(stop_base - atr*0.1, 6)
            if abs(c-stop)/c > 0.06: stop = round(c*0.94, 6)
            risco = abs(c-stop)
            # TP no FVG ou 2.5x risco
            tp1 = round(fvg_high if (fvg_ok and direcao=="LONG" and fvg_high > c) else c+risco*2.5, 6)
            if tp1 > c*1.15: tp1 = round(c*1.12, 6)
        else:
            stop_base = ob_high if ob_ok else float(dfc["high"].iloc[-6:].max())
            stop = round(stop_base + atr*0.1, 6)
            if abs(stop-c)/c > 0.06: stop = round(c*1.06, 6)
            risco = abs(stop-c)
            tp1 = round(fvg_low if (fvg_ok and direcao=="SHORT" and fvg_low < c) else c-risco*2.5, 6)
            if tp1 < c*0.85 or tp1 <= 0: tp1 = round(c*0.88, 6)

        rr = round(abs(tp1-c)/abs(stop-c), 2) if stop != c else 0

        # ── CHECAGEM FINAL ────────────────────────────────────────────────────
        if score < 70:   motivos.append(f"Score {score} < 70")
        if rr < 2.0:     motivos.append(f"RR {rr} < 2.0")

        aprovado = len(motivos) == 0

        if score >= 85:   tier = "OURO"
        elif score >= 75: tier = "PRATA"
        elif score >= 70: tier = "BRONZE"
        else:             tier = "ABAIXO"

        conv = {"OURO":"ALTA ✅","PRATA":"BOA ⚡","BRONZE":"MODERADA 🔶"}.get(tier,"MODERADA 🔶")

        if score >= 90:   prioridade = "🔥 INSTITUCIONAL"
        elif score >= 80: prioridade = "⭐ ALTA QUALIDADE"
        else:             prioridade = ""

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
            "vwap":             vwap,
            "sessao":           sessao,
            "ob_detectado":     ob_ok,
            "fvg_detectado":    fvg_ok,
            "confirmacoes_smc": confirmacoes,
            "confluencia":      len(confirmacoes),
            "motivos_rejeicao": motivos,
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
        # 30m confirmado por H1, 1h confirmado por H4
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
