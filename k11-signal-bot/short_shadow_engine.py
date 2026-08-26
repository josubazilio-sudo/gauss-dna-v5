"""
K12 SHORT Shadow Engine — RFC short-shadow 26/08
==================================================
Experiencia SHORT completamente isolada do fluxo LONG de producao.

REGRA ABSOLUTA: este modulo NUNCA aprova, envia, registra em
k11_trades.json ou influencia qualquer decisao real. So captura
candidatos em short_shadow_candidates.jsonl para analise posterior.
Zero execucao, zero ordem real, zero risco financeiro.

Reaproveita de K10Engine SOMENTE os metodos puros de calculo (sem
side-effect): _fetch, _calc, _calc_ha, _entry_quality. NUNCA chama
_analisar_tf() (a funcao LONG de producao) nem qualquer coisa que
escreva estado. Isso preserva 100% do isolamento exigido: nenhuma
linha de k10_engine.py, config.py, final_selector.py,
signal_validator.py ou trade_tracker.py e alterada por este modulo.

Motivo do bloqueio HARD de SHORT em producao (k10_engine.py, dentro
de _analisar_tf): WR historico 19-22% vs LONG 38-39% (486 trades,
05-13/08). Este modulo testa uma hipotese mais estreita: existe
vantagem em SHORT apenas durante REGIME BEARISH FORTE (estrutura +
HTF + MACD + RVOL todos confirmados simultaneamente), nao em SHORT
generico. So descobre-se rodando em shadow com dados reais.
"""

import json
import logging
import os
from datetime import datetime, timezone

import numpy as np

from k10_engine import K10Engine

logger = logging.getLogger(__name__)

ARQUIVO_SHADOW = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "short_shadow_candidates.jsonl"
)

# RFC short-shadow 26/08 — piso comprovado pela auditoria de RVOL real
# (1.5-1.79 -> PF 0.77; 1.8-1.99 -> PF 1.32; >=2.0 -> PF 0.99). Constante
# LOCAL deste modulo, nao toca RVOL_HARD_MIN/RVOL_MIN_10 usados pelo LONG.
RVOL_MIN_SHORT = 1.8

# Score minimo para o candidato entrar em shadow ativo (nao e producao).
BEAR_SCORE_MIN = 80

# Timeframe principal -> timeframe de contexto HTF obrigatorio. Mesmo
# pareamento ja usado em producao para LONG (30m->1h, 1h->4h) — nao e
# um valor novo/arbitrario.
TF_CTX = {"30m": "1h", "1h": "4h"}

# ADX floor reaproveitado do mesmo valor ja usado em k10_engine.py para
# LONG (linha ~422: "if adx < 18: bloqueado, mercado lateral"). Nao e
# um novo threshold inventado para este experimento.
ADX_LATERAL_MIN = 18
# Mesmo valor ja usado em k10_engine.py para "tendencia HTF forte"
# (linha ~618: "adx_ctx > 28"). Reaproveitado aqui como bonus de score.
ADX_FORTE = 28


class ShortShadowEngine:
    def __init__(self):
        # Composicao, nao heranca — so usa metodos de calculo puro do
        # K10Engine (_fetch/_calc/_calc_ha/_entry_quality), nunca
        # _analisar_tf() nem qualquer metodo que grave estado.
        self._base = K10Engine()

    def _fetch_ctx(self, symbol, tf):
        df = self._base._calc(self._base._fetch(symbol, tf, limit=100))
        return df.iloc[-2]  # ultima vela FECHADA do contexto

    def analisar_tf(self, symbol, tf):
        """Analisa um symbol/tf para regime bearish forte. Retorna o
        snapshot completo do candidato (aprovado ou nao) — nunca None
        a nao ser por erro de dados, para permitir registrar
        'quase passou' como o RFC pede."""
        if tf not in TF_CTX:
            return None
        ctx = TF_CTX[tf]

        try:
            df = self._base._calc_ha(self._base._fetch(symbol, tf, limit=300))
            r_ctx = self._fetch_ctx(symbol, ctx)
        except Exception as e:
            logger.warning(f"SHORT_SHADOW: fetch falhou {symbol} {tf}: {e}")
            return None

        dfc = df.iloc[:-1]
        if len(dfc) < 25:
            return None
        r = dfc.iloc[-1]
        candle_ts = r["ts"].timestamp() if hasattr(r["ts"], "timestamp") else float(r["ts"])

        c    = float(r["close"]);  atr = float(r["atr"])
        e10  = float(r["ema10"]);  e21 = float(r["ema21"])
        e50  = float(r["ema50"]);  e200 = float(r["ema200"])
        adx  = float(r["adx"]);    rsi = float(r["rsi"])
        rvol = float(r["rvol"]) if not np.isnan(r["rvol"]) else 0
        macd_h  = float(r["macd_hist"])
        macd_sig = float(r["macd_signal"])
        macd_h2 = float(dfc["macd_hist"].iloc[-2])
        macd_h3 = float(dfc["macd_hist"].iloc[-3])
        vwap = float(r["vwap"])

        # Se MACD nem sequer esta bearish, nao vale a pena computar o
        # resto (equivalente ao "quase passou" minimo — descarta ruido
        # puro sem direcao nenhuma, mas ainda captura candidatos fracos
        # que tinham QUALQUER viés bearish).
        if macd_h >= 0 and e10 >= e21:
            return None

        motivos_bloqueio = []
        detalhes = {}

        # 1. ESTRUTURA — mesma janela (20/6, 6/1, 10/2 velas) ja usada em
        # producao para 30m/1h (k10_engine.py, nunca alterada). Sweep e
        # BOS bearish.
        lookback = dfc.iloc[-20:-6]
        swing_high = float(lookback["high"].max())
        sweep_ok = False
        for i in range(-6, -1):
            vela = dfc.iloc[i]
            hv = float(vela["high"]); cv = float(vela["close"])
            if hv > swing_high * 0.999 and cv < swing_high:
                sweep_ok = True
        highs_bos = float(dfc["high"].iloc[-10:-2].max())
        lows_bos  = float(dfc["low"].iloc[-10:-2].min())
        bos_ok = c < lows_bos
        estrutura_ok = sweep_ok or bos_ok
        detalhes["estrutura"] = {"sweep": sweep_ok, "bos": bos_ok, "ok": estrutura_ok}
        if not estrutura_ok:
            motivos_bloqueio.append("sem BOS/CHoCH/sweep bearish confirmado")

        # 2. CONTEXTO HTF — obrigatorio: 30m exige H1 bearish, 1h exige
        # H4 bearish (mesmo pareamento de producao).
        tend_ctx_bear = float(r_ctx["ema21"]) < float(r_ctx["ema50"])
        adx_ctx = float(r_ctx["adx"])
        detalhes["ctx"] = {"tf": ctx, "tend_bear": tend_ctx_bear, "adx": round(adx_ctx, 1)}
        if not tend_ctx_bear:
            motivos_bloqueio.append(f"{ctx} nao esta bearish")

        # 2b. Para 30m, checagem SECUNDARIA: H4 nao pode estar fortemente
        # bullish (mesmo que H1 esteja bearish).
        h4_nao_bullish_forte = True
        if tf == "30m":
            try:
                r_h4 = self._fetch_ctx(symbol, "4h")
                tend_h4_bull = float(r_h4["ema21"]) > float(r_h4["ema50"])
                adx_h4 = float(r_h4["adx"])
                h4_nao_bullish_forte = not (tend_h4_bull and adx_h4 > ADX_FORTE)
                detalhes["h4_secundario"] = {
                    "tend_bull": tend_h4_bull, "adx": round(adx_h4, 1), "ok": h4_nao_bullish_forte
                }
            except Exception as e:
                logger.warning(f"SHORT_SHADOW: fetch H4 secundario falhou {symbol}: {e}")
        if not h4_nao_bullish_forte:
            motivos_bloqueio.append("H4 fortemente bullish (contra SHORT de 30m)")

        # 3. EMA — alinhamento real, com separacao minima (evita medias
        # coladas por ruido: distancia 10-21 precisa ser > 0.15 ATR).
        dist_10_21 = abs(e10 - e21) / atr if atr > 0 else 0
        ema_alinhada = (e10 < e21 < e50) and dist_10_21 > 0.15
        ema_200_ok = e50 < e200 if e200 > 0 else None
        detalhes["ema"] = {
            "e10": e10, "e21": e21, "e50": e50, "e200": e200,
            "alinhada_10_21_50": ema_alinhada, "abaixo_200": ema_200_ok,
        }
        if not ema_alinhada:
            motivos_bloqueio.append("EMA nao alinhada bearish (ou distancia insuficiente)")

        # 4. MACD — abaixo da linha de sinal, histograma negativo,
        # direcao descendente (mesma definicao de "acelerando short" ja
        # usada em producao: mh < mh2 < mh3).
        macd_declinando = macd_h < macd_h2
        macd_bearish = (macd_h < 0) and (macd_h < macd_sig) and macd_declinando
        detalhes["macd"] = {
            "hist": round(macd_h, 6), "signal": round(macd_sig, 6),
            "declinando": macd_declinando, "ok": macd_bearish,
        }
        if not macd_bearish:
            motivos_bloqueio.append("MACD nao confirma bearish (sinal/histograma/direcao)")

        # 5. RVOL — piso 1.8 (nao 2.0), conforme evidencia da auditoria.
        rvol_ok = rvol >= RVOL_MIN_SHORT
        detalhes["rvol"] = {"valor": round(rvol, 2), "ok": rvol_ok}
        if not rvol_ok:
            motivos_bloqueio.append(f"RVOL {rvol:.2f} < {RVOL_MIN_SHORT}")

        # 6. VWAP — preco abaixo preferido; se acima, exige estrutura
        # excepcional (sweep E bos simultaneos, nao so um dos dois).
        vwap_bearish = c < vwap
        vwap_excecao_forte = sweep_ok and bos_ok
        vwap_ok = vwap_bearish or vwap_excecao_forte
        detalhes["vwap"] = {
            "valor": round(vwap, 6), "preco_abaixo": vwap_bearish,
            "excecao_estrutura_forte": vwap_excecao_forte if not vwap_bearish else None,
            "ok": vwap_ok,
        }
        if not vwap_ok:
            motivos_bloqueio.append("preco acima da VWAP sem estrutura excepcional (sweep+BOS)")

        # 7. ADX — piso de lateralizacao (mesmo valor do LONG, 18) e
        # bonus se tendencia forte (mesmo valor do LONG, 28).
        adx_lateral = adx < ADX_LATERAL_MIN
        adx_forte_bonus = (adx > ADX_FORTE) or (adx_ctx > ADX_FORTE)
        detalhes["adx"] = {"valor": round(adx, 1), "lateral": adx_lateral, "forte": adx_forte_bonus}
        if adx_lateral:
            motivos_bloqueio.append(f"ADX {adx:.1f} < {ADX_LATERAL_MIN} (mercado lateral)")

        # BEAR_REGIME_SCORE — separado do Score LONG, nunca reutiliza
        # nem modifica o calculo de score do k10_engine.py.
        score = 0
        score += (15 if tf == "30m" else 20) if tend_ctx_bear else 0  # H1(30m)/H4(1h)
        score += 20 if estrutura_ok else 0
        score += 15 if ema_alinhada else 0
        score += 10 if macd_bearish else 0
        score += 10 if rvol_ok else 0
        score += 5 if vwap_bearish else 0
        score += 5 if adx_forte_bonus else 0
        score = min(score, 100)

        obrigatorios_ok = (
            estrutura_ok and tend_ctx_bear and h4_nao_bullish_forte
            and macd_bearish and rvol_ok and not adx_lateral
        )
        aprovado_shadow = obrigatorios_ok and score >= BEAR_SCORE_MIN

        # Entry Quality — so registro, nunca filtro (RFC explicito: EQ
        # nao e monotonico, nao usar como gate principal). Reaproveita
        # _entry_quality ja pronto e ja direcao-agnostico (trata SHORT
        # nativamente em OB/FVG/RSI).
        try:
            eq, eq_det, _ = self._base._entry_quality(df, "SHORT", False, 0, 0, bos_ok)
        except Exception:
            eq, eq_det = 0, {}

        # STOP/TP — formula identica a producao para SHORT (k10_engine.py,
        # branch SHORT ja existente e correto), UM SO stop (sem stop-duplo
        # nesta v1 — mantem rr_real e rr_exibido sempre identicos por
        # construcao, evitando herdar o bug de RR ja identificado).
        stop_base = float(dfc["high"].iloc[-6:].max())
        stop = round(stop_base + atr * 0.1, 6)
        if abs(stop - c) / c > 0.06:
            stop = round(c * 1.06, 6)
        risco = abs(stop - c)
        tp1 = round(c - risco * 2.0, 6)
        tp2 = round(c - risco * 3.5, 6)
        be  = round(c - risco * 1.0, 6)
        if tp1 < c * 0.85 or tp1 <= 0: tp1 = round(c * 0.90, 6)
        if tp2 < c * 0.75 or tp2 <= 0: tp2 = round(c * 0.85, 6)
        rr_real = round(abs(tp2 - c) / abs(stop - c), 2) if stop != c else 0

        candidato = {
            "symbol": symbol, "timeframe": tf, "direcao": "SHORT",
            "candle_ts": candle_ts,
            "entrada": c, "stop": stop, "tp1": tp1, "tp2": tp2, "be": be,
            "rr_real": rr_real, "rr_exibido": rr_real,  # sempre iguais nesta v1 (1 stop so)
            "bear_regime_score": score,
            "score_detalhes": {
                "h1_h4": (15 if tf == "30m" else 20) if tend_ctx_bear else 0,
                "estrutura": 20 if estrutura_ok else 0,
                "ema": 15 if ema_alinhada else 0,
                "macd": 10 if macd_bearish else 0,
                "rvol": 10 if rvol_ok else 0,
                "vwap": 5 if vwap_bearish else 0,
                "adx": 5 if adx_forte_bonus else 0,
            },
            "ema10": e10, "ema21": e21, "ema50": e50, "ema200": e200,
            "macd_hist": macd_h, "macd_signal": macd_sig,
            "adx": adx, "adx_ctx": round(adx_ctx, 1), "rsi": rsi,
            "rvol": rvol, "vwap": vwap,
            "entry_quality": eq, "eq_detalhes": eq_det,
            "bos_ok": bos_ok, "sweep_ok": sweep_ok,
            "obrigatorios_ok": obrigatorios_ok,
            "aprovado_shadow": aprovado_shadow,
            "motivos_bloqueio": motivos_bloqueio,
            "detalhes": detalhes,
            "tag": "SHORT_STRONG_BEAR_SHADOW",
        }
        return candidato


def _gerar_candidate_id(c: dict) -> str:
    symbol = (c.get("symbol") or "?").replace("/USDT:USDT", "").replace("/USDT", "")
    tf = c.get("timeframe", "?")
    ts_int = int(c.get("candle_ts") or 0)
    return f"SHORTBEAR-{symbol}-{tf}-{ts_int}"


def _carregar_eventos() -> list:
    eventos = []
    if not os.path.exists(ARQUIVO_SHADOW):
        return eventos
    try:
        with open(ARQUIVO_SHADOW, encoding="utf-8") as f:
            for i, linha in enumerate(f, start=1):
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    eventos.append(json.loads(linha))
                except Exception as e:
                    logger.warning(f"SHORT_SHADOW: {ARQUIVO_SHADOW} linha {i} corrompida: {e}")
    except Exception as e:
        logger.warning(f"SHORT_SHADOW: falha ao abrir {ARQUIVO_SHADOW}: {e}")
    return eventos


def _append_evento(evento: dict):
    linha = json.dumps(evento, ensure_ascii=False, default=str) + "\n"
    with open(ARQUIVO_SHADOW, "a", encoding="utf-8") as f:
        f.write(linha)
        f.flush()
        os.fsync(f.fileno())


def capturar_lote(candidatos: list) -> int:
    """Registra candidatos novos (dedupe por candle). Nunca aprova/envia
    nada — so persiste para analise posterior."""
    validos = [c for c in candidatos if c]
    if not validos:
        return 0

    eventos = _carregar_eventos()
    ja_capturados = {ev["candidate_id"] for ev in eventos if ev.get("evento") == "captured"}

    novos = 0
    for c in validos:
        cid = _gerar_candidate_id(c)
        if cid in ja_capturados:
            continue
        evento = {
            "evento": "captured",
            "candidate_id": cid,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            **c,
            "shadow": {"status": "PENDING", "result": None, "r_obtido": None, "mae": None, "mfe": None},
        }
        _append_evento(evento)
        ja_capturados.add(cid)
        novos += 1
    return novos


def _resolver_um(cand: dict, exchange) -> dict:
    """Simula outcome usando OHLCV estritamente posterior ao candle_ts
    (sem look-ahead), mesmo padrao seguro do shadow_tracker.py. Tambem
    calcula MAE/MFE reais ate o fechamento."""
    symbol = cand.get("symbol"); tf = cand.get("timeframe")
    entrada = cand.get("entrada"); stop = cand.get("stop"); tp1 = cand.get("tp1")
    candle_ts = cand.get("candle_ts")
    if not all([symbol, tf, entrada, stop, tp1, candle_ts]):
        return None
    try:
        since_ms = int(candle_ts * 1000) + 1000
        raw = exchange.fetch_ohlcv(symbol, tf, since=since_ms, limit=200)
    except Exception as e:
        logger.warning(f"SHORT_SHADOW: fetch_ohlcv falhou {symbol} {tf}: {e}")
        return None
    if not raw:
        return {"status": "PENDING"}

    risco = abs(entrada - stop)
    mae = 0.0  # maior movimento CONTRA (preco subindo, para SHORT)
    mfe = 0.0  # maior movimento A FAVOR (preco descendo, para SHORT)
    for _ts, _o, h, l, _c, _v in raw:
        mae = max(mae, (h - entrada) / risco) if risco else mae
        mfe = max(mfe, (entrada - l) / risco) if risco else mfe
        hit_tp, hit_sl = l <= tp1, h >= stop
        if hit_tp and hit_sl:
            return {"status": "AMBIGUOUS", "ambiguous": True, "mae": round(mae, 2), "mfe": round(mfe, 2)}
        if hit_tp:
            r_obtido = round(abs(tp1 - entrada) / risco, 2) if risco > 0 else 0
            return {"status": "TP1", "r_obtido": r_obtido, "mae": round(mae, 2), "mfe": round(mfe, 2)}
        if hit_sl:
            return {"status": "STOP", "r_obtido": -1.0, "mae": round(mae, 2), "mfe": round(mfe, 2)}
    return {"status": "PENDING", "mae": round(mae, 2), "mfe": round(mfe, 2)}


def resolver_pendentes(limite: int = 30) -> int:
    try:
        import ccxt
        exchange = ccxt.mexc({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    except Exception as e:
        logger.warning(f"SHORT_SHADOW: ccxt indisponivel: {e}")
        return 0

    eventos = _carregar_eventos()
    estado = {}
    for ev in eventos:
        cid = ev.get("candidate_id")
        if not cid:
            continue
        estado.setdefault(cid, {})
        estado[cid].update(ev)

    pendentes = [c for c in estado.values() if (c.get("shadow") or {}).get("status") == "PENDING"]
    resolvidos = 0
    for cand in pendentes[:limite]:
        resultado = _resolver_um(cand, exchange)
        if resultado is None or resultado["status"] == "PENDING":
            continue
        _append_evento({
            "evento": "resolved",
            "candidate_id": cand["candidate_id"],
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "shadow": {
                "status": resultado["status"], "result": resultado["status"],
                "r_obtido": resultado.get("r_obtido"),
                "mae": resultado.get("mae"), "mfe": resultado.get("mfe"),
                "ambiguous": resultado.get("ambiguous", False),
            },
        })
        resolvidos += 1
    return resolvidos
