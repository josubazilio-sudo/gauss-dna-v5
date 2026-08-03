"""
K10 Engine — Modo Adaptativo Institucional V1.0
RFC: Regime → Estratégia → Filtros → Score → Sinal
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

        df["vol_ma"] = v.rolling(20).mean()
        df["rvol"]   = v / df["vol_ma"].replace(0, np.nan)

        # Chande Momentum
        up = delta.clip(lower=0).rolling(14).sum()
        dn = (-delta.clip(upper=0)).rolling(14).sum()
        df["cmo"] = 100 * (up - dn) / (up + dn).replace(0, np.nan)

        # StochRSI
        rsi_min = df["rsi"].rolling(14).min()
        rsi_max = df["rsi"].rolling(14).max()
        df["stoch_rsi"] = (df["rsi"] - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan)

        # ROC (Rate of Change 10)
        df["roc"] = c.pct_change(10) * 100

        # Choppiness Index
        atr_sum = tr.rolling(14).sum()
        hl_range = h.rolling(14).max() - l.rolling(14).min()
        df["chop"] = 100 * np.log10(atr_sum / hl_range.replace(0, np.nan)) / np.log10(14)

        # Volume delta aproximado
        df["delta"] = (c - l) / (h - l).replace(0, np.nan) * v * 2 - v

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # 1. DETECÇÃO DE REGIME
    # ─────────────────────────────────────────────────────────────────────────
    def _detectar_regime(self, df):
        r    = df.iloc[-1]
        adx  = float(r["adx"])
        chop = float(r["chop"]) if not np.isnan(r["chop"]) else 50
        bw   = float(r["bb_width"]) if not np.isnan(r["bb_width"]) else 0
        bw_ma = float(df["bb_width"].rolling(20).mean().iloc[-1]) if not np.isnan(df["bb_width"].rolling(20).mean().iloc[-1]) else bw
        atr  = float(r["atr"])
        atr_ma = float(df["atr"].rolling(20).mean().iloc[-1])
        c    = float(r["close"])
        e50  = float(r["ema50"])
        e200 = float(r["ema200"])
        rsi  = float(r["rsi"])

        # Exaustão — RSI nos extremos com ADX caindo
        adx_caindo = adx < float(df["adx"].iloc[-5])
        if (rsi > 78 or rsi < 22) and adx_caindo:
            return "EXAUSTÃO"

        # Rompimento — ATR expandindo forte + BOS
        if atr > atr_ma * 1.4 and bw > bw_ma * 1.3 and adx > 20:
            return "ROMPIMENTO"

        # Compressão — BB muito estreita + ADX baixo
        if bw < bw_ma * 0.7 and adx < 18 and chop > 61:
            return "COMPRESSÃO"

        # Lateralização — chop alto + adx baixo
        if chop > 58 and adx < 22:
            return "LATERAL"

        # Tendência forte
        if adx > 28 and chop < 50:
            if e50 > e200 and c > e50:
                return "TENDÊNCIA_ALTA"
            if e50 < e200 and c < e50:
                return "TENDÊNCIA_BAIXA"

        # Tendência fraca
        if adx > 18 and chop < 58:
            if e50 > e200:
                return "TENDÊNCIA_FRACA_ALTA"
            return "TENDÊNCIA_FRACA_BAIXA"

        return "INDEFINIDO"

    # ─────────────────────────────────────────────────────────────────────────
    # 2. ESTRATÉGIA POR REGIME
    # ─────────────────────────────────────────────────────────────────────────
    def _estrategia_por_regime(self, regime):
        mapa = {
            "TENDÊNCIA_ALTA":        ("TREND_FOLLOWING", "LONG"),
            "TENDÊNCIA_BAIXA":       ("TREND_FOLLOWING", "SHORT"),
            "TENDÊNCIA_FRACA_ALTA":  ("TREND_FOLLOWING", "LONG"),
            "TENDÊNCIA_FRACA_BAIXA": ("TREND_FOLLOWING", "SHORT"),
            "LATERAL":               ("RANGE_TRADING",   None),
            "ROMPIMENTO":            ("BREAKOUT",        None),
            "EXAUSTÃO":              ("MEAN_REVERSION",  None),
            "COMPRESSÃO":            ("AGUARDAR",        None),
            "INDEFINIDO":            ("REJEITAR",        None),
        }
        return mapa.get(regime, ("REJEITAR", None))

    # ─────────────────────────────────────────────────────────────────────────
    # 3. FILTROS POR ESTRATÉGIA
    # ─────────────────────────────────────────────────────────────────────────
    def _filtro_tendencia(self, df, direcao):
        r   = df.iloc[-1]
        c   = float(r["close"])
        e50 = float(r["ema50"])
        e200= float(r["ema200"])
        vwap= float(r["vwap"])
        falhas = []
        if direcao == "LONG":
            if not e50 > e200:   falhas.append("EMA50 < EMA200 (sem tendência de alta)")
            if not c > e50:      falhas.append("Preço abaixo EMA50")
            if not c > vwap:     falhas.append("Preço abaixo VWAP")
        else:
            if not e50 < e200:   falhas.append("EMA50 > EMA200 (sem tendência de baixa)")
            if not c < e50:      falhas.append("Preço acima EMA50")
            if not c < vwap:     falhas.append("Preço acima VWAP")
        return falhas

    def _filtro_momentum(self, df, direcao):
        r    = df.iloc[-1]
        rsi  = float(r["rsi"])
        adx  = float(r["adx"])
        cmo  = float(r["cmo"]) if not np.isnan(r["cmo"]) else 0
        roc  = float(r["roc"]) if not np.isnan(r["roc"]) else 0
        mhist= float(r["macd_hist"])
        falhas = []

        if direcao == "LONG":
            # RSI adaptativo: em tendência, comprar quando RSI volta a subir
            rsi_subindo = float(df["rsi"].iloc[-1]) > float(df["rsi"].iloc[-3])
            if not rsi_subindo and rsi < 50:
                falhas.append(f"RSI {rsi:.1f} não está subindo")
            if mhist < 0:
                falhas.append("MACD histograma negativo")
            if cmo < -20:
                falhas.append(f"CMO {cmo:.1f} fraco para LONG")
            if roc < 0 and adx < 25:
                falhas.append(f"ROC negativo sem tendência forte")
        else:
            rsi_caindo = float(df["rsi"].iloc[-1]) < float(df["rsi"].iloc[-3])
            if not rsi_caindo and rsi > 50:
                falhas.append(f"RSI {rsi:.1f} não está caindo")
            if mhist > 0:
                falhas.append("MACD histograma positivo")
            if cmo > 20:
                falhas.append(f"CMO {cmo:.1f} fraco para SHORT")
            if roc > 0 and adx < 25:
                falhas.append(f"ROC positivo sem tendência forte")
        return falhas

    def _filtro_volume(self, df, direcao):
        r    = df.iloc[-1]
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        delta= float(r["delta"]) if not np.isnan(r["delta"]) else 0
        vol_crescente = float(df["volume"].iloc[-1]) > float(df["volume"].iloc[-4:-1].mean())
        falhas = []
        if rvol < 0.7:
            falhas.append(f"RVOL {rvol:.2f} < 0.7")
        if not vol_crescente:
            falhas.append("Volume decrescente")
        if direcao == "LONG" and delta < 0:
            falhas.append("Delta negativo (pressão vendedora)")
        if direcao == "SHORT" and delta > 0:
            falhas.append("Delta positivo (pressão compradora)")
        return falhas

    # ─────────────────────────────────────────────────────────────────────────
    # SMC
    # ─────────────────────────────────────────────────────────────────────────
    def _smc_score(self, df, direcao):
        r   = df.iloc[-1]
        c   = float(r["close"])
        atr = float(r["atr"])
        pontos = 0
        confs  = []

        # BOS
        highs = df["high"].rolling(10).max().iloc[-5]
        lows  = df["low"].rolling(10).min().iloc[-5]
        bos = (c > highs) if direcao=="LONG" else (c < lows)
        if bos: pontos += 15; confs.append("BOS")

        # CHoCH
        swing_high = df["high"].iloc[-20:-1].max()
        swing_low  = df["low"].iloc[-20:-1].min()
        choch = (c > swing_high) if direcao=="LONG" else (c < swing_low)
        if choch: pontos += 15; confs.append("CHoCH")

        # Order Block
        vol_ma = df["vol_ma"]
        for i in range(-6, -1):
            forte = abs(df["close"].iloc[i]-df["open"].iloc[i]) > atr*0.7
            inst  = df["volume"].iloc[i] > vol_ma.iloc[i]*1.3
            if forte and inst:
                if direcao=="LONG" and df["close"].iloc[i]>df["open"].iloc[i]:
                    pontos += 15; confs.append("Order Block"); break
                if direcao=="SHORT" and df["close"].iloc[i]<df["open"].iloc[i]:
                    pontos += 15; confs.append("Order Block"); break

        # FVG
        if len(df) >= 4:
            c1h = df["high"].iloc[-3]; c1l = df["low"].iloc[-3]
            c3h = df["high"].iloc[-1]; c3l = df["low"].iloc[-1]
            fvg = (c3l > c1h) if direcao=="LONG" else (c3h < c1l)
            if fvg: pontos += 10; confs.append("FVG")

        # Liquidity Sweep
        eq_high = df["high"].iloc[-20:-1].max()
        eq_low  = df["low"].iloc[-20:-1].min()
        lh = df["high"].iloc[-1]; ll = df["low"].iloc[-1]; lc = df["close"].iloc[-1]
        sweep = (ll < eq_low and lc > eq_low) if direcao=="LONG" else (lh > eq_high and lc < eq_high)
        if sweep: pontos += 15; confs.append("Liquidity Sweep")

        # Mitigação / Reteste
        e21 = float(r["ema21"])
        reteste = abs(c - e21) / atr <= 1.0 if atr > 0 else False
        if reteste: pontos += 10; confs.append("Reteste EMA21")

        # Breaker Block (candle de reversão forte)
        o = float(r["open"]); h = float(r["high"]); l = float(r["low"])
        corpo = abs(c-o); total = h-l
        if total > 0:
            breaker = corpo > total*0.6
            if breaker and ((direcao=="LONG" and c>o) or (direcao=="SHORT" and c<o)):
                pontos += 10; confs.append("Breaker Block")

        return min(pontos, 100), confs

    # ─────────────────────────────────────────────────────────────────────────
    # DISTÂNCIA DA ENTRADA (RFC seção 9)
    # ─────────────────────────────────────────────────────────────────────────
    def _avaliar_distancia(self, preco_atual, entrada, tp1):
        if tp1 == entrada: return "REJEITAR", 100
        pct_percorrido = abs(preco_atual - entrada) / abs(tp1 - entrada) * 100
        dist_pct = abs(preco_atual - entrada) / entrada * 100

        if pct_percorrido >= 30:    return "REJEITAR",   0
        if dist_pct <= 5:           return "EXCELENTE",  100
        if dist_pct <= 15:          return "BOA",        80
        if dist_pct <= 25:          return "ACEITÁVEL",  60
        if dist_pct <= 30:          return "RUIM",       30
        return "REJEITAR", 0

    # ─────────────────────────────────────────────────────────────────────────
    # STOP ADAPTATIVO (RFC seção 10)
    # ─────────────────────────────────────────────────────────────────────────
    def _calcular_niveis(self, df, direcao):
        r   = df.iloc[-1]
        c   = float(r["close"])
        atr = float(r["atr"])

        # Stop atrás da estrutura
        if direcao == "LONG":
            swing_low  = float(df["low"].iloc[-10:].min())
            stop = round(min(swing_low - atr*0.3, c - atr*1.5), 6)
            tp1  = round(c + atr*1.5, 6)
            tp2  = round(c + atr*3.0, 6)
            tp3  = round(c + atr*4.5, 6)
        else:
            swing_high = float(df["high"].iloc[-10:].max())
            stop = round(max(swing_high + atr*0.3, c + atr*1.5), 6)
            tp1  = round(c - atr*1.5, 6)
            tp2  = round(c - atr*3.0, 6)
            tp3  = round(c - atr*4.5, 6)

        rr = round(abs(tp2 - c) / abs(stop - c), 2) if stop != c else 0
        return c, stop, tp1, tp2, tp3, rr, atr

    # ─────────────────────────────────────────────────────────────────────────
    # SCORE ADAPTATIVO (RFC seção 12/13)
    # ─────────────────────────────────────────────────────────────────────────
    def _calcular_score(self, df, direcao, regime, smc_pts, falhas_tend,
                        falhas_mom, falhas_vol, dist_score, rr, atr):
        r    = df.iloc[-1]
        adx  = float(r["adx"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        rsi  = float(r["rsi"])

        componentes = {}

        # Tendência (20pts)
        tend_pts = max(0, 20 - len(falhas_tend)*8)
        componentes["Tendência"] = tend_pts

        # Momentum (20pts)
        mom_pts = max(0, 20 - len(falhas_mom)*7)
        componentes["Momentum"] = mom_pts

        # Volume (15pts)
        vol_pts = max(0, 15 - len(falhas_vol)*6)
        componentes["Volume"] = vol_pts

        # SMC (25pts)
        smc_norm = round(smc_pts * 0.25)
        componentes["SMC"] = smc_norm

        # Entrada/Distância (10pts)
        entrada_pts = round(dist_score * 0.10)
        componentes["Entrada"] = entrada_pts

        # RR (10pts)
        rr_pts = 10 if rr >= 2.0 else (7 if rr >= 1.5 else 3)
        componentes["RR"] = rr_pts

        score = sum(componentes.values())

        # Penalidades
        penais = []
        if adx < 18:
            score -= 10; penais.append(("ADX fraco", -10))
        if rvol < 0.6:
            score -= 8;  penais.append(("Volume fraco", -8))
        if len(falhas_tend) > 0:
            score -= 5 * len(falhas_tend); penais.append((f"Contra tendência ({len(falhas_tend)}x)", -5*len(falhas_tend)))
        if rr < 2.0:
            score -= 5;  penais.append(("RR < 2.0", -5))
        if regime in ("INDEFINIDO", "COMPRESSÃO"):
            score -= 15; penais.append(("Regime desfavorável", -15))

        score = max(0, min(100, score))

        # Classificação RFC seção 15
        if score >= 95:   tier = "DIAMANTE"
        elif score >= 90: tier = "PLATINA"
        elif score >= 85: tier = "OURO"
        elif score >= 80: tier = "PRATA"
        elif score >= 75: tier = "BRONZE"
        else:             tier = "ABAIXO"

        return score, tier, componentes, penais

    # ─────────────────────────────────────────────────────────────────────────
    # GESTÃO DE BANCA
    # ─────────────────────────────────────────────────────────────────────────
    def _gestao_banca(self, regime, entrada, stop, atr):
        regime_map = {
            "TENDÊNCIA_ALTA": "Bull Trend", "TENDÊNCIA_BAIXA": "Bear Trend",
            "TENDÊNCIA_FRACA_ALTA": "Transição", "TENDÊNCIA_FRACA_BAIXA": "Transição",
            "LATERAL": "Range", "ROMPIMENTO": "Compressão",
            "EXAUSTÃO": "Alta Volatilidade",
        }
        r_key = regime_map.get(regime, "Range")
        base  = ALAVANCAGEM_POR_REGIME.get(r_key, 10)
        fator = max(0.5, min(1.0, 0.002/atr if atr > 0 else 1.0))
        alav  = max(8, min(25, round(base * fator)))
        risco = round(BANCA * RISCO_PCT / 100, 2)
        dist  = abs(entrada - stop) / entrada if entrada else 0.01
        pos   = round(min(risco/dist, BANCA*alav), 2) if dist > 0 else 0
        cap   = round(pos/alav, 2)
        return {"alavancagem":alav,"capital":cap,"posicao":pos,"risco_usdt":risco,"banca":BANCA}

    # ─────────────────────────────────────────────────────────────────────────
    # ANÁLISE PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────
    def analisar(self, symbol, timeframe=None):
        tfs = [timeframe] if timeframe else ["30m","1h","4h","1d"]
        resultados = []
        for tf in tfs:
            r = self._analisar_tf(symbol, tf)
            resultados.append(r)
        aprovados = [r for r in resultados if r.get("aprovado")]
        if aprovados:
            return max(aprovados, key=lambda x: x["score"])
        return max(resultados, key=lambda x: x["score"])

    def _analisar_tf(self, symbol, tf="30m"):
        lim = 200 if tf in ("4h","1d") else 300
        try:
            df   = self._calc(self._fetch(symbol, tf, limit=lim))
            df4h = self._calc(self._fetch(symbol, "4h", limit=100))
            df1d = self._calc(self._fetch(symbol, "1d", limit=100))
        except Exception as e:
            return {"symbol":symbol,"aprovado":False,"setup_nome":"—","regime":"Erro",
                    "score":0,"motivos_rejeicao":[str(e)],"o_que_falta":[],"timeframe":tf}

        motivos = []

        # ── 1. Regime ──────────────────────────────────────────────────────
        regime = self._detectar_regime(df)
        estrategia, direcao_sugerida = self._estrategia_por_regime(regime)

        if estrategia in ("REJEITAR", "AGUARDAR"):
            return {"symbol":symbol,"aprovado":False,"setup_nome":estrategia,
                    "regime":regime,"score":0,"direcao":"—",
                    "motivos_rejeicao":[f"Regime {regime} — estratégia: {estrategia}"],
                    "o_que_falta":["Aguardar regime favorável"],"timeframe":tf}

        # ── 2. Direção ─────────────────────────────────────────────────────
        r   = df.iloc[-1]
        if direcao_sugerida:
            direcao = direcao_sugerida
        else:
            direcao = "LONG" if float(r["ema10"]) > float(r["ema21"]) else "SHORT"

        # ── 3. MTF ─────────────────────────────────────────────────────────
        tend_4h = "ALTA" if float(df4h.iloc[-1]["ema21"]) > float(df4h.iloc[-1]["ema50"]) else "BAIXA"
        tend_1d = "ALTA" if float(df1d.iloc[-1]["ema21"]) > float(df1d.iloc[-1]["ema50"]) else "BAIXA"

        if estrategia == "TREND_FOLLOWING":
            if direcao == "LONG" and (tend_4h == "BAIXA" or tend_1d == "BAIXA"):
                motivos.append(f"Contra tendência H4={tend_4h} D1={tend_1d}")
            if direcao == "SHORT" and (tend_4h == "ALTA" or tend_1d == "ALTA"):
                motivos.append(f"Contra tendência H4={tend_4h} D1={tend_1d}")

        # ── 4. Níveis ──────────────────────────────────────────────────────
        entrada, stop, tp1, tp2, tp3, rr, atr = self._calcular_niveis(df, direcao)

        # ── 5. Distância ───────────────────────────────────────────────────
        dist_label, dist_score = self._avaliar_distancia(entrada, entrada, tp1)
        if dist_label == "REJEITAR":
            motivos.append("Entrada atrasada — preço percorreu >30% até TP1")

        # ── 6. Filtros ─────────────────────────────────────────────────────
        falhas_tend = self._filtro_tendencia(df, direcao) if estrategia == "TREND_FOLLOWING" else []
        falhas_mom  = self._filtro_momentum(df, direcao)
        falhas_vol  = self._filtro_volume(df, direcao)

        # Volume sempre obrigatório
        if falhas_vol:
            motivos.extend(falhas_vol)

        # ── 7. SMC ─────────────────────────────────────────────────────────
        smc_pts, smc_confs = self._smc_score(df, direcao)

        # ── 8. ATR extremo ─────────────────────────────────────────────────
        atr_pct = atr / entrada * 100 if entrada > 0 else 0
        if atr_pct < 0.05:
            motivos.append(f"ATR muito baixo ({atr_pct:.3f}%) — sem volatilidade")
        if atr_pct > 15:
            motivos.append(f"ATR excessivo ({atr_pct:.1f}%) — risco alto")

        # ── 9. RR ──────────────────────────────────────────────────────────
        if rr < 2.0:
            motivos.append(f"RR {rr} < 2.0")

        # ── 10. Score ──────────────────────────────────────────────────────
        score, tier, componentes, penais = self._calcular_score(
            df, direcao, regime, smc_pts,
            falhas_tend, falhas_mom, falhas_vol,
            dist_score, rr, atr
        )

        # Score mínimo por tier (RFC seção 15)
        if score < 75:
            motivos.append(f"Score {score} < 75 (mínimo Bronze)")

        # SMC obrigatório
        if smc_pts < 10:
            motivos.append("Sem confluência SMC suficiente")

        aprovado = len(motivos) == 0

        gb = self._gestao_banca(regime, entrada, stop, atr)

        def conv(s):
            if s >= 95: return "ELITE 🔥"
            if s >= 85: return "ALTA ✅"
            if s >= 75: return "BOA ⚡"
            return "BAIXA ❌"

        regime_label = {
            "TENDÊNCIA_ALTA":        "Alta Forte ↑",
            "TENDÊNCIA_BAIXA":       "Baixa Forte ↓",
            "TENDÊNCIA_FRACA_ALTA":  "Alta Fraca ↑",
            "TENDÊNCIA_FRACA_BAIXA": "Baixa Fraca ↓",
            "LATERAL":               "Lateral ↔",
            "ROMPIMENTO":            "Rompimento 💥",
            "EXAUSTÃO":              "Exaustão ⚠️",
            "COMPRESSÃO":            "Compressão 🔄",
        }.get(regime, regime)

        return {
            "symbol":           symbol,
            "aprovado":         aprovado,
            "setup_nome":       estrategia,
            "regime":           regime_label,
            "regime_raw":       regime,
            "direcao":          direcao,
            "score":            score,
            "tier":             tier,
            "conviccao":        conv(score),
            "entrada":          entrada,
            "stop":             stop,
            "tp1":              tp1,
            "tp2":              tp2,
            "tp3":              tp3,
            "rr":               rr,
            "adx":              float(r["adx"]),
            "rsi":              float(r["rsi"]),
            "atr":              atr,
            "atr_pct":          round(atr_pct, 3),
            "rvol":             float(r["rvol"]) if not np.isnan(r["rvol"]) else 0,
            "cmo":              float(r["cmo"]) if not np.isnan(r["cmo"]) else 0,
            "vwap":             float(r["vwap"]),
            "ema50":            float(r["ema50"]),
            "ema200":           float(r["ema200"]),
            "macd_hist":        float(r["macd_hist"]),
            "stoch_rsi":        float(r["stoch_rsi"]) if not np.isnan(r["stoch_rsi"]) else 0,
            "confirmacoes_smc": smc_confs,
            "score_componentes":componentes,
            "penalizacoes":     penais,
            "dist_entrada":     dist_label,
            "motivos_rejeicao": motivos,
            "o_que_falta":      [m for m in motivos],
            "tend_4h":          tend_4h,
            "tend_1d":          tend_1d,
            "timeframe":        tf,
            "preco_atual":      entrada,
            **gb,
        }

    def analisar_tf(self, symbol, tf):
        return self._analisar_tf(symbol, tf)

    def obter_regime(self, symbol):
        df = self._calc(self._fetch(symbol, "30m"))
        regime = self._detectar_regime(df)
        estrategia, _ = self._estrategia_por_regime(regime)
        r = df.iloc[-1]
        return {"regime":regime,"estrategia":estrategia,"adx":float(r["adx"]),"atr":float(r["atr"])}
