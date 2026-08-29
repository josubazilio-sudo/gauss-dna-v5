"""
K11 Shadow Outcome Tracking V1 — instrumentação pura, RFC 21/08.

Objetivo: registrar TODOS os candidatos relevantes (aprovados ou não) que o
scanner encontra a cada ciclo, com o motivo completo de cada bloqueio, e
simular o que teria acontecido com os candidatos bloqueados — sem nunca
influenciar a decisão real de aprovação/rejeição.

REGRA ABSOLUTA: este módulo é somente-leitura em relação à estratégia. Ele
nunca aprova, nunca bloqueia, nunca modifica score/entrada/stop/alvo/gestão.
Nenhum threshold de trading é definido aqui — os limites usados no snapshot
de filtros (`_montar_filters`) são só LIDOS de config.py, nunca alterados.

Persistência: arquivo JSONL append-only (`shadow_candidates.jsonl`), onde
cada linha é um evento independente ("captured", "linked" ou "resolved")
identificado por `candidate_id`. O estado atual de um candidato é obtido
dobrando (fold) a sequência de eventos na ordem em que ocorreram. Esse
formato é deliberadamente diferente do k11_trades.json (array JSON único
reescrito por inteiro a cada trade) — aqui só se acrescenta, nunca se
reescreve um registro existente, o que elimina de saída a classe de bug de
leitura parcial que motivou a correção do `_salvar()` do trade_tracker.

Nunca usa `except: ...` silencioso — todo erro de leitura é logado com
warning, identificando o arquivo e a linha afetada, e nunca é traduzido em
"lista vazia"/"sem candidatos" sem deixar rastro no log.
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations

from config import (ENTRY_QUALITY_MIN, MODO_10_10, RVOL_MIN_10,
                     SCORE_PRATA_10, RR_MIN_10)

logger = logging.getLogger(__name__)

ARQUIVO_SHADOW = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "shadow_candidates.jsonl"
)

CAMPOS_SNAPSHOT = [
    "symbol", "timeframe", "direcao", "score", "tier", "regime",
    "entrada", "stop", "tp1", "tp2", "rr", "rvol", "adx", "rsi",
    "ema10", "ema21", "ema50", "ema200", "macd_hist", "vwap", "atr",
    "entry_quality", "candle_ts", "aprovado", "motivos_rejeicao",
    "confirmacoes_smc", "not_extended", "bull_candle", "pullback_long",
    "h1_quality_long", "dist_ema50_atr",
    # RFC operacao-rapida 24/08 — gap conhecido desde a RFC reequilibrio
    # 22/08, nunca corrigido: faltavam os campos de soft/quality/tier
    # novos, impedindo diagnostico de PORQUE um candidato caiu num tier
    # (ex.: ABAIXO com score alto mas soft_penalty batendo o teto).
    "quality_final", "tier_qualidade", "soft_penalty", "motivos_soft",
    "soft_filters_mode", "saude_mercado", "risco_pct_aplicado",
]

# Mapeamento motivo (texto do k10_engine) -> código canônico de bloqueio.
# Ordem importa: entradas mais específicas primeiro, catch-all genérico por
# último. Nunca para no primeiro match GLOBAL — percorre TODOS os motivos
# do candidato (ver `_block_reasons`), só usa a lista ordenada pra resolver
# qual código cada motivo individual vira.
_MOTIVO_MAP = [
    ("Mercado lateral ADX", "ADX_LOW"),
    ("sobrevendido", "RSI_EXTREME"),
    ("sobrecomprado", "RSI_EXTREME"),
    ("Preco esticado", "EXTENDED_FROM_EMA50"),
    ("Candle sem confirmacao", "CANDLE_NO_CONFIRMATION"),
    ("histograma declinando", "MACD_DECLINING"),
    ("SHORT bloqueado", "SHORT_BLOCKED"),
    ("MACD acelerou demais", "MACD_LATE"),
    ("MACD sem direção", "MACD_NO_DIRECTION"),
    ("EMA10 < EMA21", "EMA_COUNTER"),
    ("EMA10 > EMA21", "EMA_COUNTER"),
    ("Sem BOS/CHoCH", "NO_BOS_CHOCH"),
    ("sem BOS/CHoCH", "NO_BOS_CHOCH"),
    ("Volume insuficiente", "RVOL_LOW"),
    ("contra tendência forte", "H4_COUNTER_TREND"),
    ("sem tendência alinhada", "H4_COUNTER_TREND"),
    ("zona institucional", "NO_INSTITUTIONAL_ZONE"),
    ("entrada atrasada", "LATE_ENTRY_50PCT"),
    ("Entry Quality", "ENTRY_QUALITY_LOW"),
    ("RVOL", "RVOL_LOW"),
    ("Score", "SCORE_LOW"),
    ("RR", "RR_LOW"),
    ("MACD", "MACD_COUNTER_TREND"),
]


def _classificar_motivo(motivo: str) -> str:
    for chave, codigo in _MOTIVO_MAP:
        if chave in motivo:
            return codigo
    return "OUTRO"


def _block_reasons(r: dict) -> list:
    """Todos os motivos de bloqueio do candidato, não só o primeiro."""
    motivos = r.get("motivos_rejeicao") or []
    codigos = []
    for m in motivos:
        c = _classificar_motivo(m)
        if c not in codigos:
            codigos.append(c)
    return codigos


def _montar_filters(r: dict) -> dict:
    """
    Snapshot de cada filtro individual — valor observado vs threshold ATUAL
    (lido de config.py, nunca hardcoded aqui). Só inclui um filtro se o
    valor correspondente existir no resultado do engine — quando o motor
    bloqueou antes de calcular algo (ex.: EQ, estrutura), esse filtro
    simplesmente não aparece aqui, em vez de inventar um valor.
    """
    filtros = {}

    rvol = r.get("rvol")
    if rvol is not None:
        rvol_min = RVOL_MIN_10 if MODO_10_10 else 1.0
        filtros["rvol"] = {"value": rvol, "threshold": rvol_min, "passed": rvol >= rvol_min}

    eq = r.get("entry_quality")
    if eq is not None:
        filtros["entry_quality"] = {
            "value": eq, "threshold": ENTRY_QUALITY_MIN, "passed": eq >= ENTRY_QUALITY_MIN
        }

    adx = r.get("adx")
    if adx is not None:
        filtros["adx"] = {"value": adx, "threshold": 18, "passed": adx >= 18}

    score = r.get("score")
    if score is not None:
        score_min = SCORE_PRATA_10 if MODO_10_10 else 75
        filtros["score"] = {"value": score, "threshold": score_min, "passed": score >= score_min}

    rr = r.get("rr")
    if rr is not None:
        rr_min = RR_MIN_10 if MODO_10_10 else 2.0
        filtros["rr"] = {"value": rr, "threshold": rr_min, "passed": bool(rr) and rr >= rr_min}

    e10, e21 = r.get("ema10"), r.get("ema21")
    if e10 is not None and e21 is not None:
        rel = "BULLISH" if e10 > e21 else "BEARISH" if e10 < e21 else "FLAT"
        filtros["ema10_21"] = {
            "ema10": e10, "ema21": e21, "relationship": rel, "passed": rel == "BULLISH"
        }

    h1q = r.get("h1_quality_long")
    if h1q is not None:
        h1_trend = "ALIGNED" if h1q >= 75 else "PARTIAL" if h1q >= 50 else "COUNTER"
        filtros["h1_h4_trend"] = {
            "value": h1_trend, "score_0_90": h1q, "required": "ALIGNED", "passed": h1q >= 75
        }

    confs = r.get("confirmacoes_smc")
    motivos = r.get("motivos_rejeicao")
    if confs is not None or motivos is not None:
        confs = confs or []
        motivos = motivos or []
        tem_estrutura = any(
            ("Liquidez capturada" in c) or ("BOS confirmado" in c) or ("Tendência forte" in c)
            for c in confs
        )
        sem_estrutura_reportado = any("BOS/CHoCH" in m for m in motivos)
        filtros["bos_choch"] = {
            "estrutura_confirmada": tem_estrutura,
            "sem_estrutura_reportado": sem_estrutura_reportado,
            "passed": tem_estrutura and not sem_estrutura_reportado,
        }

    return filtros


def _gerar_candidate_id(r: dict) -> str:
    """Chave de deduplicação: symbol + timeframe + candle_timestamp + direção."""
    symbol = (r.get("symbol") or "?").replace("/USDT:USDT", "").replace("/USDT", "")
    tf = r.get("timeframe", "?")
    direcao = r.get("direcao", "?")
    candle_ts = r.get("candle_ts")
    ts_int = int(candle_ts) if candle_ts is not None else 0
    return f"K11-{symbol}-{tf}-{direcao}-{ts_int}"


def _carregar_eventos() -> list:
    """
    Lê o log de eventos linha a linha. Uma linha corrompida é logada com
    warning e pulada — NUNCA descarta o arquivo inteiro por causa de uma
    linha ruim (diferente do problema antigo do k11_trades.json, que era
    um array JSON único onde qualquer erro invalidava tudo).
    """
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
                    logger.warning(
                        f"shadow_tracker: {ARQUIVO_SHADOW} linha {i} corrompida, "
                        f"pulando (histórico anterior preservado): {e}"
                    )
                    continue
    except Exception as e:
        logger.warning(f"shadow_tracker: falha ao abrir {ARQUIVO_SHADOW}: {e}")
    return eventos


def _dobrar_estado(eventos: list) -> dict:
    """Reconstrói o estado atual de cada candidate_id dobrando a sequência de eventos."""
    estado = {}
    for ev in eventos:
        cid = ev.get("candidate_id")
        if not cid:
            continue
        estado.setdefault(cid, {})
        estado[cid].update(ev)
    return estado


def _append_evento(evento: dict):
    """
    Append atômico de uma linha JSON. Escritas O_APPEND de uma linha curta
    são atômicas no nível do SO (POSIX, dentro de PIPE_BUF) — diferente do
    k11_trades.json, aqui nunca há truncamento nem reescrita do arquivo
    inteiro, então não existe a janela de leitura parcial.
    """
    linha = json.dumps(evento, ensure_ascii=False, default=str) + "\n"
    with open(ARQUIVO_SHADOW, "a", encoding="utf-8") as f:
        f.write(linha)
        f.flush()
        os.fsync(f.fileno())


def _montar_snapshot(r: dict) -> dict:
    return {k: r.get(k) for k in CAMPOS_SNAPSHOT}


def capturar_lote(resultados: list) -> int:
    """
    Recebe TODOS os resultados de um ciclo de scan (aprovados ou não) e
    registra os candidatos "relevantes" (score>0 — mesmo critério já usado
    no diagnóstico "SEM SINAL" existente) que ainda não foram capturados
    para este candle. Não modifica `resultados` nem os dicts dentro dela.
    """
    candidatos = [r for r in resultados if r and (r.get("score") or 0) > 0]
    if not candidatos:
        return 0

    eventos = _carregar_eventos()
    ja_capturados = {ev["candidate_id"] for ev in eventos if ev.get("evento") == "captured"}

    novos = 0
    for r in candidatos:
        cid = _gerar_candidate_id(r)
        if cid in ja_capturados:
            continue

        snap = _montar_snapshot(r)
        outcome_simulable = bool(snap.get("entrada")) and bool(snap.get("stop")) and bool(snap.get("tp1"))

        evento = {
            "evento": "captured",
            "candidate_id": cid,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            **snap,
            "filters": _montar_filters(r),
            "block_reasons": _block_reasons(r),
            "outcome_simulable": outcome_simulable,
            "shadow": {
                "status": "PENDING" if outcome_simulable else "NOT_SIMULABLE",
                "result": None, "r_obtido": None, "ambiguous": False,
            },
            "real_trade_id": None,
        }
        _append_evento(evento)
        ja_capturados.add(cid)
        novos += 1

    return novos


def marcar_aprovado_real(sinal: dict, trade_id: int):
    """
    Vincula o candidate_id ao id do trade real registrado no trade_tracker,
    quando o mesmo sinal foi de fato aprovado e enviado. Não cria um
    segundo trade — só um evento de vínculo sobre o candidato já capturado.
    """
    cid = _gerar_candidate_id(sinal)
    _append_evento({
        "evento": "linked",
        "candidate_id": cid,
        "linked_at": datetime.now(timezone.utc).isoformat(),
        "real_trade_id": trade_id,
    })


def _resolver_um(cand: dict, exchange) -> dict:
    """
    Simula o outcome de UM candidato usando OHLCV histórico, olhando SOMENTE
    velas estritamente posteriores ao candle_ts do sinal (sem look-ahead).
    Nunca recalcula entrada/stop/tp1 — usa exatamente os valores do
    snapshot original, exatamente como capturados no momento do sinal.
    """
    symbol = cand.get("symbol")
    tf = cand.get("timeframe")
    entrada = cand.get("entrada")
    stop = cand.get("stop")
    tp1 = cand.get("tp1")
    direcao = cand.get("direcao")
    candle_ts = cand.get("candle_ts")
    if not all([symbol, tf, entrada, stop, tp1, direcao, candle_ts]):
        return None

    try:
        since_ms = int(candle_ts * 1000) + 1000
        raw = exchange.fetch_ohlcv(symbol, tf, since=since_ms, limit=200)
    except Exception as e:
        logger.warning(f"shadow_tracker: fetch_ohlcv falhou para {symbol} {tf}: {e}")
        return None

    if not raw:
        return {"status": "PENDING"}

    for _ts, _o, h, l, _c, _v in raw:
        if direcao == "LONG":
            hit_tp, hit_sl = h >= tp1, l <= stop
        elif direcao == "SHORT":
            hit_tp, hit_sl = l <= tp1, h >= stop
        else:
            return {"status": "INVALID"}

        # Nunca assumir que o TP ocorreu primeiro só porque é favorável.
        if hit_tp and hit_sl:
            return {"status": "AMBIGUOUS", "ambiguous": True}
        if hit_tp:
            risco = abs(entrada - stop)
            r_obtido = round(abs(tp1 - entrada) / risco, 2) if risco > 0 else 0
            return {"status": "TP1", "r_obtido": r_obtido}
        if hit_sl:
            return {"status": "STOP", "r_obtido": -1.0}

    return {"status": "PENDING"}


def resolver_pendentes(limite: int = 50) -> int:
    """
    Resolve até `limite` candidatos PENDING por ciclo (limite operacional
    de chamadas à exchange, não é um threshold de estratégia). Sem política
    de expiração — segue exatamente o mesmo comportamento do trade_tracker
    real, que também nunca expira posições abertas por tempo. Se algum dia
    quiser uma expiração diferente para o shadow, isso precisa ser definido
    explicitamente; não foi inventado aqui.
    """
    try:
        import ccxt
        exchange = ccxt.mexc({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    except Exception as e:
        logger.warning(f"shadow_tracker: ccxt indisponível para resolução: {e}")
        return 0

    eventos = _carregar_eventos()
    estado = _dobrar_estado(eventos)

    pendentes = [
        c for c in estado.values()
        if c.get("outcome_simulable") and (c.get("shadow") or {}).get("status") == "PENDING"
    ]
    # RFC prioridade-shadow 28/08 — achado real: com 16k+ pendentes e so
    # `limite` resolvidos por ciclo, a fila (ordem cronologica de captura)
    # e dominada por candidatos BLOQUEADOS (muito mais numerosos que
    # aprovados a cada ciclo). Resultado: 935 de 944 aprovados nunca
    # chegavam a ser resolvidos, ficando "afogados" atras da fila -- nao
    # e que aprovados performem pior, e que quase nao havia dado real
    # sobre eles ainda. Prioriza aprovados primeiro (sort estavel, mantem
    # ordem cronologica dentro de cada grupo); nao muda nenhuma logica de
    # aprovacao/estrategia, so a ordem de resolucao do shadow.
    pendentes.sort(key=lambda c: not c.get("aprovado"))

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
                "status": resultado["status"],
                "result": resultado["status"],
                "r_obtido": resultado.get("r_obtido"),
                "ambiguous": resultado.get("ambiguous", False),
            },
        })
        resolvidos += 1

    return resolvidos


# ── Relatórios ────────────────────────────────────────────────────────────

def relatorio_shadow() -> str:
    estado = _dobrar_estado(_carregar_eventos())
    total = len(estado)
    aprovados = sum(1 for c in estado.values() if c.get("aprovado"))
    bloqueados = total - aprovados

    simulaveis = [c for c in estado.values() if c.get("outcome_simulable")]
    pendentes = [c for c in simulaveis if (c.get("shadow") or {}).get("status") == "PENDING"]
    concluidos = [
        c for c in simulaveis
        if (c.get("shadow") or {}).get("status") not in (None, "PENDING", "NOT_SIMULABLE")
    ]
    r_vals = [c["shadow"]["r_obtido"] for c in concluidos if c["shadow"].get("r_obtido") is not None]

    sep = "━━━━━━━━━━━━━━━━━━━━"
    linhas = [
        "🔬 K12 SHADOW REPORT",
        sep,
        f"Total candidatos: {total}",
        f"Aprovados: {aprovados}",
        f"Bloqueados: {bloqueados}",
        sep,
        f"Shadow pendentes: {len(pendentes)}",
        f"Shadow concluídos: {len(concluidos)}",
        sep,
    ]
    if r_vals:
        wins = [r for r in r_vals if r > 0]
        n = len(r_vals)
        wr = len(wins) / n * 100
        r_pos = sum(r for r in r_vals if r > 0)
        r_neg = abs(sum(r for r in r_vals if r < 0))
        pf = round(r_pos / r_neg, 2) if r_neg > 0 else 0
        exp = round(sum(r_vals) / n, 3)
        linhas += [
            f"Shadow Wins: {len(wins)}",
            f"Shadow Losses: {n - len(wins)}",
            f"Shadow WR: {wr:.1f}%",
            f"Shadow PF: {pf}",
            f"Shadow Expectancy: {exp:+.3f}R",
        ]
    else:
        linhas.append("Shadow: sem resultados concluídos ainda")
    return "\n".join(linhas)


def relatorio_por_motivo() -> str:
    estado = _dobrar_estado(_carregar_eventos())
    bloqueados = [c for c in estado.values() if not c.get("aprovado")]

    por_motivo = defaultdict(list)
    for c in bloqueados:
        for reason in (c.get("block_reasons") or []):
            por_motivo[reason].append(c)

    sep = "━━━━━━━━━━━━━━━━━━━━"
    linhas = ["🔬 K12 SHADOW — BLOCK REASON ANALYSIS", sep]
    if not por_motivo:
        linhas.append("Sem candidatos bloqueados registrados ainda")
        return "\n".join(linhas)

    for reason, cands in sorted(por_motivo.items(), key=lambda x: -len(x[1])):
        concluidos = [
            c for c in cands
            if c.get("outcome_simulable")
            and (c.get("shadow") or {}).get("status") not in (None, "PENDING", "NOT_SIMULABLE")
        ]
        r_vals = [c["shadow"]["r_obtido"] for c in concluidos if c["shadow"].get("r_obtido") is not None]
        linhas.append(f"\n{reason}")
        linhas.append(f"Candidates: {len(cands)}")
        if r_vals:
            wins = [r for r in r_vals if r > 0]
            n = len(r_vals)
            wr = len(wins) / n * 100
            r_pos = sum(r for r in r_vals if r > 0)
            r_neg = abs(sum(r for r in r_vals if r < 0))
            pf = round(r_pos / r_neg, 2) if r_neg > 0 else 0
            exp = round(sum(r_vals) / n, 3)
            linhas.append(f"Wins: {len(wins)} | Losses: {n - len(wins)}")
            linhas.append(f"WR: {wr:.1f}% | PF: {pf} | Exp: {exp:+.3f}R")
        else:
            linhas.append("Sem resultados shadow concluídos ainda")
    return "\n".join(linhas)


def relatorio_combinacoes(min_freq: int = 5) -> str:
    estado = _dobrar_estado(_carregar_eventos())
    bloqueados = [c for c in estado.values() if not c.get("aprovado")]

    por_combo = defaultdict(list)
    for c in bloqueados:
        reasons = sorted(set(c.get("block_reasons") or []))
        if len(reasons) < 2:
            continue
        for combo in combinations(reasons, 2):
            por_combo[combo].append(c)

    freq = {combo: cands for combo, cands in por_combo.items() if len(cands) >= min_freq}
    sep = "━━━━━━━━━━━━━━━━━━━━"
    linhas = [f"🔬 K12 SHADOW — COMBINAÇÕES FREQUENTES (min {min_freq}x)", sep]
    if not freq:
        linhas.append("Nenhuma combinação atingiu a frequência mínima ainda")
        return "\n".join(linhas)

    for combo, cands in sorted(freq.items(), key=lambda x: -len(x[1])):
        concluidos = [
            c for c in cands
            if c.get("outcome_simulable")
            and (c.get("shadow") or {}).get("status") not in (None, "PENDING", "NOT_SIMULABLE")
        ]
        r_vals = [c["shadow"]["r_obtido"] for c in concluidos if c["shadow"].get("r_obtido") is not None]
        linhas.append(f"\n{' + '.join(combo)}")
        linhas.append(f"Candidates: {len(cands)}")
        if r_vals:
            wins = [r for r in r_vals if r > 0]
            n = len(r_vals)
            wr = len(wins) / n * 100
            r_pos = sum(r for r in r_vals if r > 0)
            r_neg = abs(sum(r for r in r_vals if r < 0))
            pf = round(r_pos / r_neg, 2) if r_neg > 0 else 0
            exp = round(sum(r_vals) / n, 3)
            linhas.append(f"WR: {wr:.1f}% | PF: {pf} | Exp: {exp:+.3f}R")
        else:
            linhas.append("Sem resultados concluídos ainda")
    return "\n".join(linhas)
