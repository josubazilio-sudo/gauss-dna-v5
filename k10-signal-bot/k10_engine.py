"""
K10 Engine — Motor de análise adaptativa
4 Setups | Market Regime | Entry Engine | Quality Gate
"""

import ccxt
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ── Estrutura de resultado ────────────────────────────────────────────────────
@dataclass
class SinalResult:
    symbol: str
    aprovado: bool
    setup_nome: str
    regime: str
    direcao: str = ""
    score: int = 0
    convicção: str = ""
    entrada: float = 0.0
    stop: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    rr: float = 0.0
    adx: float = 0.0
    atr: float = 0.0
    volume_status: str = ""
    confirmacoes: list = field(default_factory=list)
    motivos_rejeicao: list = field(default_factory=list)
    o_que_falta: list = field(default_factory=list)
    setup_alternativo: str = ""


# ── Engine principal ──────────────────────────────────────────────────────────
class K10Engine:
    def __init__(self, exchange_id: str = "binance"):
        self.exchange = ccxt.binance({"enableRateLimit": True})

    # ── Dados OHLCV ──────────────────────────────────────────────────────────
    def _fetch(self, symbol: str, tf: str, limit: int = 200) -> pd.DataFrame:
        try:
            raw = self.exchange.fetch_ohlcv(symbol, tf, limit=limit)
            df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
            df["ts"] = pd.to_datetime(df["ts"], unit="ms")
            return df
        except Exception as e:
            raise RuntimeError(f"Erro ao buscar {symbol} {tf}: {e}")

    # ── Indicadores ──────────────────────────────────────────────────────────
    def _indicadores(self, df: pd.DataFrame) -> pd.DataFrame:
        c = df["close"]
        h = df["high"]
        l = df["low"]

        # EMAs
        df["ema20"] = c.ewm(span=20).mean()
        df["ema50"] = c.ewm(span=50).mean()
        df["ema200"] = c.ewm(span=200).mean()

        # VWAP (intraday proxy)
        df["vwap"] = (df["volume"] * (h + l + c) / 3).cumsum() / df["volume"].cumsum()

        # ATR
        tr = pd.concat([
            h - l,
            (h - c.shift()).abs(),
            (l - c.shift()).abs()
        ], axis=1).max(axis=1)
        df["atr"] = tr.ewm(span=14).mean()

        # ADX
        df["adx"] = self._calc_adx(df)

        # RSI
        df["rsi"] = self._calc_rsi(c)

        # Volume médio
        df["vol_ma"] = df["volume"].rolling(20).mean()
        df["rvol"] = df["volume"] / df["vol_ma"]

        return df

    def _calc_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0).ewm(span=period).mean()
        loss = (-delta.clip(upper=0)).ewm(span=period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _calc_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        h, l, c = df["high"], df["low"], df["close"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        dm_pos = (h.diff()).clip(lower=0).where((h.diff()) > (-l.diff()), 0)
        dm_neg = (-l.diff()).clip(lower=0).where((-l.diff()) > (h.diff()), 0)
        atr14 = tr.ewm(span=period).mean()
        di_pos = 100 * dm_pos.ewm(span=period).mean() / atr14
        di_neg = 100 * dm_neg.ewm(span=period).mean() / atr14
        dx = (100 * (di_pos - di_neg).abs() / (di_pos + di_neg).replace(0, np.nan))
        return dx.ewm(span=period).mean()

    # ── Market Regime ─────────────────────────────────────────────────────────
    def _regime(self, df: pd.DataFrame) -> str:
        last = df.iloc[-1]
        adx = last["adx"]
        ema20, ema50, ema200 = last["ema20"], last["ema50"], last["ema200"]
        atr = last["atr"]
        atr_mean = df["atr"].rolling(50).mean().iloc[-1]

        if adx >= 25:
            if ema20 > ema50 > ema200:
                return "Bull Trend"
            elif ema20 < ema50 < ema200:
                return "Bear Trend"
            else:
                return "Transição"
        elif adx < 15:
            if atr > atr_mean * 1.5:
                return "Alta Volatilidade"
            elif atr < atr_mean * 0.7:
                return "Baixa Volatilidade"
            else:
                return "Range"
        else:
            return "Transição"

    def _setup_recomendado(self, regime: str) -> str:
        mapa = {
            "Bull Trend": "SETUP 1 — CONTINUAÇÃO",
            "Bear Trend": "SETUP 1 — CONTINUAÇÃO",
            "Range": "SETUP 4 — RANGE",
            "Alta Volatilidade": "SETUP 3 — BREAKOUT",
            "Baixa Volatilidade": "SETUP 4 — RANGE",
            "Transição": "SETUP 2 — REVERSAL",
        }
        return mapa.get(regime, "SETUP 4 — RANGE")

    # ── Detecção de BOS / CHoCH ───────────────────────────────────────────────
    def _bos(self, df: pd.DataFrame) -> bool:
        """Break of Structure simples: novo high/low rompido"""
        highs = df["high"].rolling(10).max()
        lows = df["low"].rolling(10).min()
        last = df.iloc[-1]
        prev_high = highs.iloc[-5]
        prev_low = lows.iloc[-5]
        return last["close"] > prev_high or last["close"] < prev_low

    def _divergencia(self, df: pd.DataFrame) -> bool:
        """Divergência RSI simples"""
        closes = df["close"].iloc[-10:]
        rsis = df["rsi"].iloc[-10:]
        price_up = closes.iloc[-1] > closes.iloc[0]
        rsi_down = rsis.iloc[-1] < rsis.iloc[0]
        return (price_up and rsi_down) or (not price_up and not rsi_down)

    # ── Entry Engine ──────────────────────────────────────────────────────────
    def _entry_engine(self, df: pd.DataFrame, direcao: str) -> dict:
        last = df.iloc[-1]
        c = last["close"]
        ema20, vwap = last["ema20"], last["vwap"]
        atr = last["atr"]
        rvol = last["rvol"]

        prox_ema = abs(c - ema20) / atr < 1.5
        prox_vwap = abs(c - vwap) / atr < 1.5
        atr_ok = atr > 0
        vol_ok = rvol >= 1.0
        espaco = atr * 4  # espaço mínimo para TP

        falhas = []
        if not prox_ema:
            falhas.append("Preço distante do EMA20")
        if not prox_vwap:
            falhas.append("Preço distante do VWAP")
        if not vol_ok:
            falhas.append(f"Volume abaixo da média (RVOL {rvol:.2f} < 1.0)")

        aprovado = len(falhas) == 0

        # Níveis
        if direcao == "LONG":
            entrada = round(c, 4)
            stop = round(c - atr * 1.5, 4)
            tp1 = round(c + atr * 2, 4)
            tp2 = round(c + atr * 4, 4)
        else:
            entrada = round(c, 4)
            stop = round(c + atr * 1.5, 4)
            tp1 = round(c - atr * 2, 4)
            tp2 = round(c - atr * 4, 4)

        rr = round(abs(tp1 - entrada) / abs(stop - entrada), 2) if stop != entrada else 0

        return {
            "aprovado": aprovado,
            "falhas": falhas,
            "entrada": entrada,
            "stop": stop,
            "tp1": tp1,
            "tp2": tp2,
            "rr": rr,
        }

    # ── Setup 1 — Continuação ─────────────────────────────────────────────────
    def _setup1(self, df: pd.DataFrame, regime: str) -> dict:
        last = df.iloc[-1]
        conf = []
        falhas = []
        falta = []

        # Regime
        if regime not in ("Bull Trend", "Bear Trend"):
            falhas.append(f"Regime incompatível: {regime} (precisa Bull/Bear Trend)")
            falta.append("Aguardar tendência definida (ADX ≥ 25 + EMAs alinhadas)")

        adx = last["adx"]
        if adx >= 25:
            conf.append(f"ADX {adx:.1f} ≥ 25 ✓")
        else:
            falhas.append(f"ADX {adx:.1f} < 25")
            falta.append("ADX ≥ 25")

        ema20, ema50, ema200 = last["ema20"], last["ema50"], last["ema200"]
        if ema20 > ema50 > ema200 or ema20 < ema50 < ema200:
            conf.append("EMAs alinhadas ✓")
        else:
            falhas.append("EMAs desalinhadas")
            falta.append("EMA20 > EMA50 > EMA200 (ou invertido para short)")

        if self._bos(df):
            conf.append("BOS confirmado ✓")
        else:
            falhas.append("BOS não confirmado")
            falta.append("Break of Structure confirmado")

        vol_ok = last["rvol"] >= 1.1
        if vol_ok:
            conf.append(f"Volume acima da média (RVOL {last['rvol']:.2f}) ✓")
        else:
            falhas.append(f"Volume fraco (RVOL {last['rvol']:.2f})")
            falta.append("RVOL ≥ 1.1")

        direcao = "LONG" if regime == "Bull Trend" else "SHORT"
        return {"conf": conf, "falhas": falhas, "falta": falta, "direcao": direcao}

    # ── Setup 2 — Reversal ────────────────────────────────────────────────────
    def _setup2(self, df: pd.DataFrame) -> dict:
        last = df.iloc[-1]
        conf = []
        falhas = []
        falta = []

        rsi = last["rsi"]
        if rsi >= 70:
            conf.append(f"RSI {rsi:.1f} sobrecomprado ✓")
            direcao = "SHORT"
        elif rsi <= 30:
            conf.append(f"RSI {rsi:.1f} sobrevendido ✓")
            direcao = "LONG"
        else:
            falhas.append(f"RSI {rsi:.1f} não extremo (precisa ≤30 ou ≥70)")
            falta.append("RSI ≤ 30 ou ≥ 70")
            direcao = "LONG"

        if self._divergencia(df):
            conf.append("Divergência RSI confirmada ✓")
        else:
            falhas.append("Sem divergência")
            falta.append("Divergência de preço vs RSI")

        rvol = last["rvol"]
        if rvol >= 1.0:
            conf.append(f"Volume crescente (RVOL {rvol:.2f}) ✓")
        else:
            falhas.append(f"Volume fraco (RVOL {rvol:.2f})")
            falta.append("RVOL ≥ 1.0")

        return {"conf": conf, "falhas": falhas, "falta": falta, "direcao": direcao}

    # ── Setup 3 — Breakout ────────────────────────────────────────────────────
    def _setup3(self, df: pd.DataFrame) -> dict:
        last = df.iloc[-1]
        conf = []
        falhas = []
        falta = []

        adx = last["adx"]
        adx_prev = df["adx"].iloc[-5]
        if adx > adx_prev:
            conf.append(f"ADX crescente ({adx_prev:.1f} → {adx:.1f}) ✓")
        else:
            falhas.append("ADX não crescente")
            falta.append("ADX crescente (momentum expandindo)")

        rvol = last["rvol"]
        if rvol >= 1.5:
            conf.append(f"Volume explosivo (RVOL {rvol:.2f}) ✓")
        else:
            falhas.append(f"Volume insuficiente para breakout (RVOL {rvol:.2f} < 1.5)")
            falta.append("RVOL ≥ 1.5 (volume explosivo)")

        if self._bos(df):
            conf.append("BOS / Rompimento confirmado ✓")
        else:
            falhas.append("Rompimento não confirmado")
            falta.append("Fechamento acima/abaixo da região de consolidação")

        direcao = "LONG" if last["close"] > last["ema50"] else "SHORT"
        return {"conf": conf, "falhas": falhas, "falta": falta, "direcao": direcao}

    # ── Setup 4 — Range ───────────────────────────────────────────────────────
    def _setup4(self, df: pd.DataFrame, regime: str) -> dict:
        last = df.iloc[-1]
        conf = []
        falhas = []
        falta = []

        adx = last["adx"]
        if adx < 20:
            conf.append(f"ADX {adx:.1f} lateral ✓")
        else:
            falhas.append(f"ADX {adx:.1f} alto demais para range (precisa < 20)")
            falta.append("ADX < 20")

        rsi = last["rsi"]
        if rsi <= 35:
            conf.append(f"RSI {rsi:.1f} em suporte ✓")
            direcao = "LONG"
        elif rsi >= 65:
            conf.append(f"RSI {rsi:.1f} em resistência ✓")
            direcao = "SHORT"
        else:
            falhas.append(f"RSI {rsi:.1f} sem extremo de range")
            falta.append("RSI ≤ 35 (suporte) ou ≥ 65 (resistência)")
            direcao = "LONG"

        return {"conf": conf, "falhas": falhas, "falta": falta, "direcao": direcao}

    # ── Score ─────────────────────────────────────────────────────────────────
    def _score(self, conf: list, rr: float, adx: float, rvol: float, regime: str) -> int:
        score = 0
        score += min(len(conf) * 8, 40)      # confirmações (max 40)
        score += min(int(rr * 8), 20)         # RR (max 20)
        score += min(int(adx / 2), 15)        # ADX (max 15)
        score += min(int(rvol * 5), 15)       # Volume (max 15)
        if regime in ("Bull Trend", "Bear Trend"):
            score += 10
        return min(score, 100)

    def _convicção(self, score: int) -> str:
        if score >= 80:
            return "MUITO ALTA 🔥"
        elif score >= 65:
            return "ALTA ✅"
        elif score >= 50:
            return "MÉDIA ⚠️"
        else:
            return "BAIXA ❌"

    # ── Análise completa ──────────────────────────────────────────────────────
    def analisar(self, symbol: str) -> dict:
        try:
            df1h = self._fetch(symbol, "1h")
            df1h = self._indicadores(df1h)
            df4h = self._fetch(symbol, "4h", limit=100)
            df4h = self._indicadores(df4h)
        except Exception as e:
            return {
                "symbol": symbol, "aprovado": False,
                "setup_nome": "—", "regime": "Erro",
                "score": 0, "motivos_rejeicao": [str(e)],
                "o_que_falta": [], "setup_alternativo": "—"
            }

        regime = self._regime(df1h)
        setup_rec = self._setup_recomendado(regime)
        last = df1h.iloc[-1]

        # Selecionar e rodar setup
        if setup_rec == "SETUP 1 — CONTINUAÇÃO":
            res = self._setup1(df1h, regime)
        elif setup_rec == "SETUP 2 — REVERSAL":
            res = self._setup2(df1h)
        elif setup_rec == "SETUP 3 — BREAKOUT":
            res = self._setup3(df1h)
        else:
            res = self._setup4(df1h, regime)

        direcao = res["direcao"]
        ee = self._entry_engine(df1h, direcao)

        # Consolidar falhas
        todas_falhas = res["falhas"] + ee["falhas"]
        tudo_falta = res["falta"] + [f for f in ee["falhas"] if f not in res["falta"]]

        # Quality Gate
        rr_ok = ee["rr"] >= 2.0
        if not rr_ok:
            todas_falhas.append(f"RR {ee['rr']} < 2.0")
            tudo_falta.append("RR ≥ 2.0")

        aprovado = len(todas_falhas) == 0 and ee["aprovado"] and rr_ok

        score = self._score(
            res["conf"], ee["rr"], last["adx"], last["rvol"], regime
        )

        return {
            "symbol": symbol,
            "aprovado": aprovado,
            "setup_nome": setup_rec,
            "regime": regime,
            "direcao": direcao,
            "score": score,
            "convicção": self._convicção(score),
            "entrada": ee["entrada"],
            "stop": ee["stop"],
            "tp1": ee["tp1"],
            "tp2": ee["tp2"],
            "rr": ee["rr"],
            "adx": last["adx"],
            "atr": last["atr"],
            "volume_status": f"RVOL {last['rvol']:.2f}",
            "confirmacoes": res["conf"],
            "motivos_rejeicao": todas_falhas,
            "o_que_falta": tudo_falta,
            "setup_alternativo": self._setup_alternativo(regime, setup_rec),
        }

    def _setup_alternativo(self, regime: str, atual: str) -> str:
        alternativas = {
            "SETUP 1 — CONTINUAÇÃO": "SETUP 3 — BREAKOUT",
            "SETUP 2 — REVERSAL": "SETUP 4 — RANGE",
            "SETUP 3 — BREAKOUT": "SETUP 1 — CONTINUAÇÃO",
            "SETUP 4 — RANGE": "SETUP 2 — REVERSAL",
        }
        return alternativas.get(atual, "—")

    def obter_regime(self, symbol: str) -> dict:
        df = self._fetch(symbol, "1h")
        df = self._indicadores(df)
        df4h = self._fetch(symbol, "4h", limit=100)
        df4h = self._indicadores(df4h)
        df1d = self._fetch(symbol, "1d", limit=100)
        df1d = self._indicadores(df1d)

        regime = self._regime(df)
        last = df.iloc[-1]

        def tendencia(d):
            l = d.iloc[-1]
            if l["ema20"] > l["ema50"]:
                return "Alta"
            elif l["ema20"] < l["ema50"]:
                return "Baixa"
            return "Neutra"

        return {
            "regime": regime,
            "adx": last["adx"],
            "atr": last["atr"],
            "tendencia_4h": tendencia(df4h),
            "tendencia_1d": tendencia(df1d),
            "setup_recomendado": self._setup_recomendado(regime),
        }
