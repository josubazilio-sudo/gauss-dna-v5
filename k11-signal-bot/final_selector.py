"""
K12 Final Selector V1 — Shadow Mode
Fluxo: candidatos aprovados → estrutura → timing → regime → cooldown → correlação → TOP 1-2

SHADOW_MODE=True: registra decisões sem interferir no sinal real
"""

import json, os, time, logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ─── CONFIGURAÇÕES CENTRALIZADAS ────────────────────────────────────────────
CFG = {
    "FINAL_SELECTOR_ENABLED":    True,
    "SHADOW_MODE":               False,  # False = bloqueia de verdade
    "MAX_FINAL_SIGNALS_PER_CYCLE": 2,
    # RFC frequencia-sinais 23/08 (3a rodada) — os 3 pisos abaixo eram
    # matematicamente inalcancaveis: testados contra candidatos reais
    # (incluindo o UNICO aprovado pelo k10_engine no periodo, score 89,
    # BOS confirmado, RR 3.5), o maximo observado foi Structure=57.8
    # (piso era 70), Timing=60.2 (piso era 65), Final=58.9 (piso era 75).
    # Ou seja, o Final Selector bloqueava 100% dos candidatos SEMPRE,
    # independente de qualidade -- um bloqueio silencioso downstream do
    # k10_engine, que o usuario pediu explicitamente pra investigar.
    # Recalibrado com margem real sobre o unico candidato confirmado bom
    # (UB score89 folga ~13-20pts em cada piso) mantendo discriminacao
    # sobre candidatos fracos observados (ex.: BNB 30m timing=3.1, ainda
    # bloqueia).
    "FINAL_SCORE_MIN":           45,
    "STRUCTURE_SCORE_MIN":       45,
    "ENTRY_TIMING_MIN":          40,
    "RR_MIN":                    1.5,
    "COOLDOWN_AFTER_LOSS_MIN":   30,     # minutos de cooldown após loss
    "MAX_CORRELATED_SIGNALS":    1,
    "REVERSAL_CHURN_PENALTY":    15,
    "ENTRY_LATE_PENALTY":        10,
    "WATCHING_ENABLED":          True,
}

STATE_FILE = "/tmp/k11_selector_state.json"
SHADOW_FILE = "/tmp/k11_shadow_log.json"


def _load_state():
    try:
        if os.path.exists(STATE_FILE):
            return json.load(open(STATE_FILE))
    except: pass
    return {
        "cooldowns": {},      # sym -> timestamp ultimo loss
        "last_signals": {},   # sym -> {dir, timestamp, result}
        "corr_grupos": {},    # grupo -> [syms enviados neste ciclo]
        "dia": "",
        "count_dia": 0,
    }

def _save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except: pass

def _load_shadow():
    try:
        if os.path.exists(SHADOW_FILE):
            return json.load(open(SHADOW_FILE))
    except: pass
    return []

def _save_shadow(log):
    try:
        with open(SHADOW_FILE, "w") as f:
            json.dump(log[-500:], f)  # manter últimos 500
    except: pass


def _calcular_structure_score(sinal: dict) -> float:
    """
    Structure Score — qualidade da estrutura de mercado.
    Baseado nos dados já calculados pelo engine.
    """
    s = 0.0
    score = sinal.get("score", 0)
    rvol  = sinal.get("rvol", 0)
    adx   = sinal.get("adx", 0)
    confs = sinal.get("confirmacoes_smc", [])
    eq    = sinal.get("entry_quality", 0)

    # Score base do engine (já considera tendência, MACD, EMAs, etc)
    s += score * 0.6

    # RVOL institucional
    if rvol >= 2.0:   s += 15
    elif rvol >= 1.5: s += 10
    elif rvol >= 1.0: s += 5
    else:             s -= 10

    # ADX
    if adx >= 30:   s += 10
    elif adx >= 22: s += 5

    # Confirmações SMC
    n_confs = len(confs)
    if n_confs >= 7:   s += 10
    elif n_confs >= 5: s += 5

    # BOS/Liquidez confirmados
    if any("BOS" in c or "Liquidez" in c or "Tendência forte" in c for c in confs):
        s += 10

    # H1/H4 confirmando
    if any("H1" in c or "H4" in c for c in confs):
        s += 8

    return min(100, max(0, s / 1.58))  # normalizar para 0-100


def _calcular_entry_timing(sinal: dict) -> float:
    """
    Entry Timing Score — qualidade do PONTO de entrada agora.
    Foca em: distância EMA21, extensão do movimento, timing MACD.
    """
    eq     = sinal.get("entry_quality", 50)
    eq_det = sinal.get("eq_detalhes", {})
    confs  = sinal.get("confirmacoes_smc", [])

    t = 0.0

    # Entry Quality do engine é nossa base de timing
    t += eq * 0.7

    # Bônus por componentes de timing
    ema21_pts = eq_det.get("ema21", 0)
    macd_pts  = eq_det.get("timing", 0)
    bos_pts   = eq_det.get("bos", 0)

    if ema21_pts > 0:  t += 10  # perto da EMA21
    if macd_pts >= 10: t += 10  # MACD cruzou agora
    if bos_pts >= 15:  t += 10  # BOS recente (0-3 velas)

    # Penalidade por entrada atrasada
    if ema21_pts < 0:  t -= 15  # longe da EMA21
    if bos_pts < 0:    t -= 10  # BOS antigo

    # MACD cruzou agora = bônus extra de timing
    if any("cruzou" in c.lower() for c in confs):
        t += 8

    return min(100, max(0, t / 1.28))


def _calcular_regime_score(sinal: dict) -> float:
    """
    Market Regime Score — contexto de mercado favorável.
    """
    adx     = sinal.get("adx", 0)
    rvol    = sinal.get("rvol", 0)
    direcao = sinal.get("direcao", "")
    confs   = sinal.get("confirmacoes_smc", [])

    r = 50.0  # base neutra

    # ADX indica força da tendência
    if adx >= 35:   r += 20
    elif adx >= 25: r += 10
    elif adx < 18:  r -= 30  # lateral = ruim

    # Volume indica participação institucional
    if rvol >= 2.0:   r += 15
    elif rvol >= 1.5: r += 8
    elif rvol < 1.0:  r -= 15

    # H4 confirmando = regime maior favorável
    if any("H4" in c for c in confs): r += 15

    return min(100, max(0, r))


def _calcular_final_score(structure: float, timing: float, regime: float) -> float:
    w_s = CFG["FINAL_SCORE_MIN"] / 100 * 0.55  # peso estrutura 55%
    w_t = 0.30   # peso timing 30%
    w_r = 0.15   # peso regime 15%
    return structure * 0.55 + timing * 0.30 + regime * 0.15


def _verificar_cooldown(sym: str, state: dict) -> tuple:
    """Verifica se o ativo está em cooldown após loss."""
    now = time.time()
    cooldown_min = CFG["COOLDOWN_AFTER_LOSS_MIN"]
    if sym in state["cooldowns"]:
        elapsed = (now - state["cooldowns"][sym]) / 60
        if elapsed < cooldown_min:
            return True, f"Cooldown {cooldown_min - elapsed:.0f}min restantes após loss"
    return False, ""


def _verificar_churn(sym: str, direcao: str, state: dict) -> tuple:
    """Detecta LONG→LOSS→SHORT ou SHORT→LOSS→LONG."""
    if sym in state["last_signals"]:
        ultimo = state["last_signals"][sym]
        if (ultimo.get("result") == "STOP" and
            ultimo.get("dir") != direcao):
            return True, f"Churn detectado — {ultimo['dir']} perdeu, agora {direcao}"
    return False, ""


def _verificar_correlacao(sinal: dict, selecionados: list) -> tuple:
    """Evita múltiplos sinais correlacionados no mesmo ciclo."""
    direcao = sinal.get("direcao", "")
    sym     = sinal.get("symbol", "").replace("/USDT:USDT", "")

    # Contar sinais da mesma direção já selecionados
    mesma_dir = [s for s in selecionados if s.get("direcao") == direcao]
    if len(mesma_dir) >= CFG["MAX_CORRELATED_SIGNALS"]:
        return True, f"Correlação: {len(mesma_dir)} sinais {direcao} já selecionados"

    return False, ""


def selecionar(candidatos: list, state: dict = None) -> tuple:
    """
    Final Selector — seleciona os melhores 1-2 candidatos.

    Retorna: (selecionados, rejeitados_com_motivo, contadores, state)
    """
    if state is None:
        state = _load_state()

    contadores = {
        "candidates_total": len(candidatos),
        "structure_rejected": 0,
        "timing_rejected": 0,
        "regime_rejected": 0,
        "cooldown_rejected": 0,
        "churn_rejected": 0,
        "correlation_rejected": 0,
        "final_score_rejected": 0,
        "watching": 0,
        "selected": 0,
    }

    shadow_log = _load_shadow()
    agora = datetime.now(timezone.utc).isoformat()
    selecionados = []
    rejeitados = []

    # Calcular scores para todos os candidatos
    scored = []
    for s in candidatos:
        sym     = s.get("symbol", "").replace("/USDT:USDT", "")
        direcao = s.get("direcao", "")

        structure = _calcular_structure_score(s)
        timing    = _calcular_entry_timing(s)
        regime    = _calcular_regime_score(s)
        final     = _calcular_final_score(structure, timing, regime)

        scored.append({
            "sinal":     s,
            "sym":       sym,
            "direcao":   direcao,
            "structure": round(structure, 1),
            "timing":    round(timing, 1),
            "regime":    round(regime, 1),
            "final":     round(final, 1),
        })

    # Ordenar por: Final Score → Timing → Structure → RR
    scored.sort(key=lambda x: (
        x["final"],
        x["timing"],
        x["structure"],
        x["sinal"].get("rr", 0)
    ), reverse=True)

    for item in scored:
        s       = item["sinal"]
        sym     = item["sym"]
        direcao = item["direcao"]
        motivo_rejeicao = None

        # Gate 1: Structure Score mínimo
        if item["structure"] < CFG["STRUCTURE_SCORE_MIN"]:
            motivo_rejeicao = f"Structure {item['structure']} < {CFG['STRUCTURE_SCORE_MIN']}"
            contadores["structure_rejected"] += 1

        # Gate 2: Entry Timing mínimo
        elif item["timing"] < CFG["ENTRY_TIMING_MIN"]:
            if CFG["WATCHING_ENABLED"]:
                motivo_rejeicao = f"WATCHING — timing {item['timing']} < {CFG['ENTRY_TIMING_MIN']}"
                contadores["watching"] += 1
            else:
                motivo_rejeicao = f"Timing {item['timing']} < {CFG['ENTRY_TIMING_MIN']}"
                contadores["timing_rejected"] += 1

        # Gate 3: Final Score mínimo
        elif item["final"] < CFG["FINAL_SCORE_MIN"]:
            motivo_rejeicao = f"Final Score {item['final']} < {CFG['FINAL_SCORE_MIN']}"
            contadores["final_score_rejected"] += 1

        # Gate 4: Cooldown
        else:
            cool, msg = _verificar_cooldown(sym, state)
            if cool:
                motivo_rejeicao = msg
                contadores["cooldown_rejected"] += 1

        # Gate 5: Anti-churn
        if motivo_rejeicao is None:
            churn, msg = _verificar_churn(sym, direcao, state)
            if churn:
                motivo_rejeicao = msg
                contadores["churn_rejected"] += 1
                item["final"] -= CFG["REVERSAL_CHURN_PENALTY"]

        # Gate 6: Anti-correlação
        if motivo_rejeicao is None:
            corr, msg = _verificar_correlacao(s, selecionados)
            if corr:
                motivo_rejeicao = msg
                contadores["correlation_rejected"] += 1

        # Gate 7: Máximo por ciclo
        if motivo_rejeicao is None:
            if len(selecionados) >= CFG["MAX_FINAL_SIGNALS_PER_CYCLE"]:
                motivo_rejeicao = f"Máximo {CFG['MAX_FINAL_SIGNALS_PER_CYCLE']} sinais/ciclo atingido"

        # Decisão final
        decisao = "REJEITAR" if motivo_rejeicao else "SELECIONAR"
        if "WATCHING" in (motivo_rejeicao or ""):
            decisao = "WATCHING"

        # Shadow log
        shadow_entry = {
            "ts":        agora,
            "sym":       sym,
            "dir":       direcao,
            "tf":        s.get("timeframe", ""),
            "score":     s.get("score", 0),
            "eq":        s.get("entry_quality", 0),
            "structure": item["structure"],
            "timing":    item["timing"],
            "regime":    item["regime"],
            "final":     item["final"],
            "decisao":   decisao,
            "motivo":    motivo_rejeicao or "Aprovado",
        }
        shadow_log.append(shadow_entry)

        if motivo_rejeicao:
            rejeitados.append({"sinal": s, "motivo": motivo_rejeicao, **item})
        else:
            selecionados.append(s)
            contadores["selected"] += 1
            # Adicionar scores ao sinal
            s["fs_structure"] = item["structure"]
            s["fs_timing"]    = item["timing"]
            s["fs_regime"]    = item["regime"]
            s["fs_final"]     = item["final"]

    _save_shadow(shadow_log)

    # Log detalhado
    logger.info(
        f"K12 FINAL SELECTOR | "
        f"Candidates:{contadores['candidates_total']} | "
        f"Structure❌:{contadores['structure_rejected']} | "
        f"Timing❌:{contadores['timing_rejected']} | "
        f"Watching:{contadores['watching']} | "
        f"Cooldown❌:{contadores['cooldown_rejected']} | "
        f"Churn❌:{contadores['churn_rejected']} | "
        f"Corr❌:{contadores['correlation_rejected']} | "
        f"FinalScore❌:{contadores['final_score_rejected']} | "
        f"SELECTED:{contadores['selected']}"
    )

    return selecionados, rejeitados, contadores, state


def relatorio_shadow() -> str:
    """Relatório do Shadow Mode — compara selecionados vs rejeitados."""
    log = _load_shadow()
    if not log:
        return "Shadow Mode: sem dados ainda"

    total     = len(log)
    selecionados = [x for x in log if x["decisao"] == "SELECIONAR"]
    rejeitados   = [x for x in log if x["decisao"] == "REJEITAR"]
    watching     = [x for x in log if x["decisao"] == "WATCHING"]

    sep = "━━━━━━━━━━━━━━━━━━━━"
    linhas = [
        "🔬 K12 FINAL SELECTOR — SHADOW MODE",
        f"Total avaliados: {total}",
        f"Selecionados: {len(selecionados)} ({len(selecionados)/total*100:.0f}%)",
        f"Rejeitados: {len(rejeitados)} ({len(rejeitados)/total*100:.0f}%)",
        f"Watching: {len(watching)}",
        sep,
        "MOTIVOS DE REJEIÇÃO:",
    ]

    motivos = {}
    for r in rejeitados:
        m = r["motivo"][:30]
        motivos[m] = motivos.get(m, 0) + 1
    for m, n in sorted(motivos.items(), key=lambda x: -x[1])[:5]:
        linhas.append(f"  {n}x {m}")

    linhas += [
        sep,
        f"Timing médio selecionados: {sum(x['timing'] for x in selecionados)/len(selecionados):.1f}" if selecionados else "",
        f"Timing médio rejeitados: {sum(x['timing'] for x in rejeitados)/len(rejeitados):.1f}" if rejeitados else "",
    ]

    return "\n".join(l for l in linhas if l)
