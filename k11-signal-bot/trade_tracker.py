"""
K11 Sistema de Relatório
- Registra cada sinal automaticamente
- Envia relatório a cada 2h
- Resumo completo às 23:30 BRT
"""
import json, os, logging, requests, time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

ARQUIVO   = "/root/gauss-dna-v5/k11-signal-bot/k11_trades.json"
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("ALLOWED_CHAT_IDS", "").split(",")[0].strip()

def brt_now():
    return datetime.now(timezone.utc) - timedelta(hours=3)

def _carregar():
    if os.path.exists(ARQUIVO):
        try:
            with open(ARQUIVO) as f: return json.load(f)
        except Exception as e:
            logger.warning(f"k11_trades.json ilegivel neste ciclo: {e}")
            return []
    return []

def _salvar(trades):
    """
    Escrita atômica — corrige o problema de leitura parcial observado
    anteriormente (Shadow Outcome Tracking V1, RFC 21/08). Escreve num
    arquivo temporário no mesmo diretório, faz flush+fsync, e só então
    substitui o arquivo real via os.replace (atômico no mesmo filesystem).
    Isso elimina a janela em que um leitor concorrente veria o arquivo
    truncado/parcial — o arquivo real nunca fica num estado intermediário.
    """
    tmp = ARQUIVO + ".tmp"
    with open(tmp, "w") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, ARQUIVO)

def registrar(sinal: dict) -> int:
    trades = _carregar()
    now_brt = brt_now()
    eq_det = sinal.get("eq_detalhes", {})
    entry = {
        "id":           len(trades) + 1,
        "data":         now_brt.strftime("%d/%m/%Y"),
        "hora":         now_brt.strftime("%H:%M"),
        "symbol":       sinal.get("symbol","").replace("/USDT:USDT",""),
        "direcao":      sinal.get("direcao",""),
        "timeframe":    sinal.get("timeframe",""),
        "score":        sinal.get("score", 0),
        "entry_quality":sinal.get("entry_quality", 0),
        "eq_ema21":     eq_det.get("ema21", 0),
        "eq_ob":        eq_det.get("ob_fvg", 0),
        "eq_timing":    eq_det.get("timing", 0),
        "eq_rsi":       eq_det.get("rsi", 0),
        "eq_bos":       eq_det.get("bos", 0),
        "tier":         sinal.get("tier",""),
        "rvol":         round(sinal.get("rvol", 0), 2),
        "rsi":          round(sinal.get("rsi", 0), 1),
        "adx":          round(sinal.get("adx", 0), 1),
        "rr_alvo":      sinal.get("rr", 0),
        "entrada":      sinal.get("entrada", 0),
        "tp1":          sinal.get("tp1", 0),
        "tp2":          sinal.get("tp2", 0),
        "stop":         sinal.get("stop", 0),
        "be":           sinal.get("be", 0),
        "regime":       sinal.get("regime",""),
        "setup":        sinal.get("prioridade","").replace("🔥","").replace("⭐","").strip(),
        "confs":        len(sinal.get("confirmacoes_smc", [])),
        "dist_ema21":   round(abs(sinal.get("entrada",0)-sinal.get("ema21",0)) / sinal.get("atr",1) if sinal.get("atr",0) > 0 else 0, 2),
        # Final Selector (observabilidade — RFC correção conservadora 20/08).
        # Aditivo: None quando o sinal veio do fallback do runner (final_selector
        # rejeitou tudo no ciclo) em vez de ter sido de fato selecionado.
        "fs_structure": sinal.get("fs_structure"),
        "fs_timing":    sinal.get("fs_timing"),
        "fs_regime":    sinal.get("fs_regime"),
        "fs_final":     sinal.get("fs_final"),
        # K11 APEX (observabilidade — RFC APEX v1 shadow mode 20/08).
        # Aditivo: False/None quando o sinal nao passou pelo avaliador APEX.
        "is_apex":         sinal.get("is_apex", False),
        "apex_tipo":       sinal.get("apex_tipo"),
        "apex_score":      sinal.get("apex_score"),
        "apex_componentes":sinal.get("apex_componentes"),
        # RFC reequilibrio 22/08 — aditivo. Marca explicitamente se o trade
        # foi aprovado sob soft_filters_mode, pra permitir comparar depois
        # regime estrito (antes) vs regime reequilibrado (depois) sem
        # misturar as duas populações.
        "quality_final":     sinal.get("quality_final"),
        "tier_qualidade":    sinal.get("tier_qualidade"),
        "soft_penalty":      sinal.get("soft_penalty"),
        # RFC modo-operavel 29/08 — classificacao final do modulo de
        # liberacao (NAO_OPERAVEL nunca chega aqui; ACEITAVEL/BOM/PREMIUM).
        "classificacao_operavel": sinal.get("classificacao_operavel"),
        # RFC operacao-rapida 24/08 — faltava o TEXTO dos motivos soft, so
        # o numero agregado (soft_penalty) era salvo. Sem isso, nao da pra
        # diagnosticar RETROATIVAMENTE por que um trade caiu pra ABAIXO
        # (ex.: os 13 trades ABAIXO de 23-24/08 tinham score 86-94 mas
        # soft_penalty 20-50 -- sabiamos O QUANTO penalizou, nao O QUE).
        "motivos_soft":      sinal.get("motivos_soft"),
        "soft_filters_mode": sinal.get("soft_filters_mode", False),
        # RFC stop-duplo 23/08 — REGISTRO OBRIGATÓRIO. Aditivo: None/False
        # em trades antigos (campo não existia antes desta RFC).
        "atr":                 sinal.get("atr"),
        "saude_mercado":       sinal.get("saude_mercado"),
        "risco_pct_aplicado":  sinal.get("risco_pct_aplicado"),
        "posicao_usdt":        sinal.get("posicao"),
        "liquidez_relevante":  sinal.get("liquidez_relevante"),
        "sweep_extremo":       sinal.get("sweep_extremo"),
        "stop1":                sinal.get("stop1"),
        "stop2":                sinal.get("stop2"),
        "dist_stop1":           sinal.get("dist_stop1"),
        "dist_stop2":           sinal.get("dist_stop2"),
        "stop_duplo_ativo":     sinal.get("stop_duplo_ativo", False),
        "risco_adaptativo_ativo": sinal.get("risco_adaptativo_ativo", False),
        "stop1_tocado":         False,
        "salvo_por_stop2":      False,
        "mfe_apos_stop1":       None,   # máx. excursão favorável DEPOIS de tocar STOP1
        "max_r_adverso":        None,   # máx. excursão adversa (MAE, candle H1 fechado)
        "resultado":    "ABERTO",
        "be_tocado":    False,
        "r_obtido":     None,
        "pnl_usdt":     None,
        "duracao_h":    None,
        # Gestão de Posição (2026-08-10) — ver verificar_gestao_avancada().
        "stop_trailing":             None,
        "alerta_estrutural_enviado": False,
        # Métricas de avanço/devolução (V58.1 FASE 1 — coleta p/ decidir FASE 2).
        "max_r_favoravel":  None,   # maior R favorável atingido (candle H1 fechado)
        "r_be_momento":     None,   # R no momento em que o BE ativou
        "r_tp1":            None,   # R quando o TP1 é atingido
        "r_devolvido":      None,   # R devolvido = max_r_favoravel - r_final
        # RFC operacao-rapida 24/08 — instrumentacao de tempo (pre-requisito
        # pra medir R/hora, tempo ate TP1/STOP, MFE/MAE com timestamp).
        # `duracao_h` acima existia no schema desde sempre mas NUNCA era
        # preenchido -- esse e o gap real que bloqueava a Fase 1 pedida
        # (medir duracao dos trades atuais). Aditivo, zero impacto em
        # gates/entrada/stop/TP.
        "entrada_ts":       time.time(),
        "fechado_ts":       None,
        "tempo_ate_tp1_h":  None,
        "tempo_ate_stop_h": None,
        "tempo_ate_mfe_h":  None,   # quando o max_r_favoravel bateu o pico
        "tempo_ate_mae_h":  None,   # quando o max_r_adverso bateu o fundo
    }
    trades.append(entry)
    _salvar(trades)
    return entry["id"]

def metricas(trades):
    fechados = [t for t in trades if t["resultado"] != "ABERTO"]
    abertos  = [t for t in trades if t["resultado"] == "ABERTO"]
    wins  = [t for t in fechados if t["resultado"] in ("TP1","TP2")]
    losses= [t for t in fechados if t["resultado"] == "STOP"]
    bes   = [t for t in fechados if t["resultado"] == "BE"]
    r_vals = [t["r_obtido"] for t in fechados if t.get("r_obtido") is not None]
    wr   = len(wins)/len(fechados)*100 if fechados else 0
    pf   = 0.0; exp = 0.0; r_med = 0.0
    if r_vals:
        r_pos = sum(r for r in r_vals if r > 0)
        r_neg = abs(sum(r for r in r_vals if r < 0))
        pf   = round(r_pos/r_neg, 2) if r_neg > 0 else 0
        r_med = round(sum(r_vals)/len(r_vals), 2)
        exp  = round(sum(r_vals)/len(fechados), 2) if fechados else 0
    return {"total": len(trades), "fechados": len(fechados), "abertos": len(abertos),
            "wins": len(wins), "losses": len(losses), "bes": len(bes),
            "wr": wr, "pf": pf, "exp": exp, "r_med": r_med}

def stats_rapidas() -> str:
    trades = _carregar()
    if not trades:
        return "📊 Sem histórico ainda"
    m = metricas(trades)
    if not m["fechados"]:
        return f"📊 {m['total']} sinais | {m['abertos']} abertos | Aguardando resultados"
    return (f"📊 {m['total']} trades | ✅{m['wins']} ❌{m['losses']} ⚖️{m['bes']} "
            f"WR {m['wr']:.0f}% | PF {m['pf']} | Exp {m['exp']:+.2f}R")

def relatorio_2h() -> str:
    trades = _carregar()
    now_brt = brt_now()
    sep = "━━━━━━━━━━━━━━━━━━━━"

    # Sinais das últimas 2h
    cutoff = now_brt - timedelta(hours=2)
    recentes = []
    for t in trades:
        try:
            dt = datetime.strptime(f"{t['data']} {t['hora']}", "%d/%m/%Y %H:%M")
            dt = dt.replace(tzinfo=timezone.utc) - timedelta(hours=0)
            if dt >= cutoff.replace(tzinfo=None if cutoff.tzinfo else timezone.utc):
                recentes.append(t)
        except: pass

    fechados = [t for t in trades if t["resultado"] != "ABERTO"]
    abertos  = [t for t in trades if t["resultado"] == "ABERTO"]
    wins     = [t for t in fechados if t["resultado"] in ("TP1","TP2")]
    losses   = [t for t in fechados if t["resultado"] == "STOP"]

    linhas = [
        f"📊 K12 — RELATÓRIO 2H",
        f"🕐 {now_brt.strftime('%H:%M')} BRT | {now_brt.strftime('%d/%m/%Y')}",
        sep,
        f"Total: {len(trades)} sinais | Abertos: {len(abertos)}",
    ]

    if fechados:
        wr = len(wins)/len(fechados)*100
        r_vals = [t["r_obtido"] for t in fechados if t.get("r_obtido") is not None]
        linhas.append(f"Wins: {len(wins)} | Losses: {len(losses)} | WR: {wr:.1f}%")
        if r_vals:
            r_pos = sum(r for r in r_vals if r > 0)
            r_neg = abs(sum(r for r in r_vals if r < 0))
            pf    = round(r_pos/r_neg, 2) if r_neg > 0 else "—"
            linhas.append(f"Profit Factor: {pf} | R Médio: {round(sum(r_vals)/len(r_vals),2):+.2f}R")

    linhas += [sep, f"🔔 ÚLTIMAS 2H ({len(recentes)} sinais):"]
    if recentes:
        for t in recentes[-5:]:
            emoji = "✅" if t["resultado"] in ("TP1","TP2") else "❌" if t["resultado"] in ("STOP","TIMEOUT") else "⏳"
            linhas.append(f"{emoji} {t['hora']} {t['symbol']} {t['direcao']} {t['timeframe']} s={t['score']} RVOL={t['rvol']}")
    else:
        linhas.append("Nenhum sinal nas últimas 2h")

    if len(fechados) < 50:
        linhas += [sep, f"⚠️ {len(fechados)}/50 trades para análise estatística definitiva"]

    return "\n".join(linhas)

def relatorio_diario() -> str:
    trades = _carregar()
    now_brt = brt_now()
    hoje = now_brt.strftime("%d/%m/%Y")
    sep = "━━━━━━━━━━━━━━━━━━━━"

    de_hoje   = [t for t in trades if t.get("data") == hoje]
    fechados  = [t for t in de_hoje if t["resultado"] != "ABERTO"]
    abertos   = [t for t in de_hoje if t["resultado"] == "ABERTO"]
    wins      = [t for t in fechados if t["resultado"] in ("TP1","TP2")]
    losses    = [t for t in fechados if t["resultado"] == "STOP"]
    todos_f   = [t for t in trades if t["resultado"] != "ABERTO"]

    linhas = [
        f"🌙 K12 — RESUMO DO DIA",
        f"📅 {hoje} | {now_brt.strftime('%H:%M')} BRT",
        sep,
        f"HOJE: {len(de_hoje)} sinais emitidos",
        f"Abertos: {len(abertos)} | Fechados: {len(fechados)}",
    ]

    if fechados:
        wr = len(wins)/len(fechados)*100
        linhas += [f"Wins: {len(wins)} | Losses: {len(losses)} | WR hoje: {wr:.1f}%"]
        r_vals = [t["r_obtido"] for t in fechados if t.get("r_obtido") is not None]
        if r_vals:
            pnl = sum(t.get("pnl_usdt",0) or 0 for t in fechados)
            linhas.append(f"PnL hoje: {pnl:+.2f} USDT")

    linhas += [sep, "TODOS OS SINAIS DE HOJE:"]
    for t in de_hoje:
        emoji = "✅" if t["resultado"] in ("TP1","TP2") else "❌" if t["resultado"] in ("STOP","TIMEOUT") else "⏳"
        r_str = f" {t['r_obtido']:+.1f}R" if t.get("r_obtido") is not None else ""
        linhas.append(f"{emoji} {t['hora']} {t['symbol']} {t['direcao']} s={t['score']}{r_str}")

    linhas += [sep, "HISTÓRICO GERAL:"]
    if todos_f:
        wr_total = len([t for t in todos_f if t["resultado"] in ("TP1","TP2")])/len(todos_f)*100
        linhas.append(f"Total fechados: {len(todos_f)} | WR geral: {wr_total:.1f}%")

        # Por tier
        for tier in ["OURO","PRATA","BRONZE"]:
            tt = [t for t in todos_f if t.get("tier")==tier]
            if tt:
                tw = [t for t in tt if t["resultado"] in ("TP1","TP2")]
                linhas.append(f"  {tier}: {len(tw)}/{len(tt)} ({len(tw)/len(tt)*100:.0f}%)")

        # Por direção
        for dir in ["LONG","SHORT"]:
            tt = [t for t in todos_f if t.get("direcao")==dir]
            if tt:
                tw = [t for t in tt if t["resultado"] in ("TP1","TP2")]
                linhas.append(f"  {dir}: {len(tw)}/{len(tt)} ({len(tw)/len(tt)*100:.0f}%)")

    linhas += [sep, "K12 — Boa noite! 🌙"]
    return "\n".join(linhas)

def enviar_telegram(msg: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg[:4096]}, timeout=30)


# ── K11 APEX — coorte de validação (shadow mode, RFC APEX v1 20/08) ─────────
# Reaproveita o MESMO arquivo/pipeline de resolução (verificar_resultados_
# automatico / verificar_gestao_avancada) — nao existe uma segunda fila de
# monitoramento de preco. So filtra is_apex==True sobre os trades ja
# rastreados normalmente. Nao decide aprovacao de nada, so mede.

def _metricas_subset(subset):
    fechados = [t for t in subset if t["resultado"] != "ABERTO"]
    r_vals = [t["r_obtido"] for t in fechados if t.get("r_obtido") is not None]
    n = len(fechados)
    if n == 0:
        return {"n": 0, "wr": 0, "pf": 0, "exp": 0, "r_medio": 0,
                "max_drawdown_r": 0, "max_losing_streak": 0}
    wins = [r for r in r_vals if r > 0]
    wr = len(wins) / n * 100 if n else 0
    r_pos = sum(r for r in r_vals if r > 0)
    r_neg = abs(sum(r for r in r_vals if r < 0))
    pf = round(r_pos / r_neg, 2) if r_neg > 0 else 0
    exp = round(sum(r_vals) / n, 3) if n else 0
    r_medio = round(sum(r_vals) / n, 3) if n else 0

    # Drawdown maximo (R acumulado, sequencia de fechamento) e maior
    # sequencia de perdas consecutivas — na ordem em que os trades fecharam.
    acumulado = 0.0
    pico = 0.0
    max_dd = 0.0
    streak = 0
    max_streak = 0
    for r in r_vals:
        acumulado += r
        pico = max(pico, acumulado)
        max_dd = max(max_dd, pico - acumulado)
        if r < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    return {"n": n, "wr": round(wr, 1), "pf": pf, "exp": exp, "r_medio": r_medio,
            "max_drawdown_r": round(max_dd, 2), "max_losing_streak": max_streak}


def _tier_qualidade(m: dict) -> str:
    if m["n"] < 30:
        return "⚪ AMOSTRA INSUFICIENTE (<30)"
    if m["pf"] < 1.20:
        return "🟡 APEX FRACO (PF < 1.20)"
    if m["pf"] < 1.50:
        return "🟢 APEX PROMISSOR (PF 1.20-1.49)" if m["exp"] > 0 else "🟡 APEX FRACO (Exp negativa)"
    if m["n"] >= 100 and m["exp"] > 0:
        return "🏆 APEX VALIDADO (PF>=1.50, Exp+, n>=100)"
    return "🔥 APEX FORTE (PF >= 1.50, aguardando n>=100 p/ validar)"


def metricas_apex() -> dict:
    """Retorna as métricas completas da coorte APEX, separadas por tipo e TF."""
    trades = _carregar()
    apex = [t for t in trades if t.get("is_apex")]
    geral = _metricas_subset(apex)
    trend = _metricas_subset([t for t in apex if t.get("apex_tipo") == "TREND"])
    reversal = _metricas_subset([t for t in apex if t.get("apex_tipo") == "REVERSAL"])
    tf_30m = _metricas_subset([t for t in apex if t.get("timeframe") == "30m"])
    tf_1h = _metricas_subset([t for t in apex if t.get("timeframe") == "1h"])
    return {"geral": geral, "trend": trend, "reversal": reversal,
            "tf_30m": tf_30m, "tf_1h": tf_1h,
            "total_registrados": len(apex),
            "abertos": len([t for t in apex if t["resultado"] == "ABERTO"])}


def relatorio_apex_progresso() -> str:
    """Relatório de progresso da coorte de validação APEX (secao 14-15 da RFC)."""
    m = metricas_apex()
    sep = "━━━━━━━━━━━━━━━━━━━━"
    g = m["geral"]
    linhas = [
        "🔥 K12 APEX — PROGRESSO DA VALIDAÇÃO (shadow mode)",
        sep,
        f"Registrados: {m['total_registrados']} | Abertos: {m['abertos']} | Fechados: {g['n']}",
        f"Meta mínima: 100 trades fechados | Ideal: 150-200",
    ]
    if g["n"] > 0:
        linhas += [
            sep,
            f"GERAL: WR {g['wr']}% | PF {g['pf']} | Exp {g['exp']:+.3f}R | R médio {g['r_medio']:+.3f}",
            f"Max drawdown: {g['max_drawdown_r']:.2f}R | Maior sequência de perdas: {g['max_losing_streak']}",
            f"Classificação: {_tier_qualidade(g)}",
        ]
        for label, sub in [("APEX TREND", m["trend"]), ("APEX REVERSAL", m["reversal"]),
                            ("30m", m["tf_30m"]), ("1h", m["tf_1h"])]:
            if sub["n"] > 0:
                linhas.append(f"  {label}: n={sub['n']} WR={sub['wr']}% PF={sub['pf']} Exp={sub['exp']:+.3f}R")
    else:
        linhas += [sep, "Nenhum APEX fechado ainda — aguardando primeiros resultados."]
    return "\n".join(linhas)


def verificar_resultados_automatico():
    """
    Verifica automaticamente resultados de trades abertos.
    Busca preço atual e compara com TP1 e Stop.
    """
    try:
        import ccxt
        exchange = ccxt.mexc({
            "enableRateLimit": True,
            "options": {"defaultType": "swap"}
        })
    except:
        return 0

    trades = _carregar()
    abertos = [t for t in trades if t["resultado"] == "ABERTO"]
    if not abertos:
        return 0

    import logging
    log = logging.getLogger("K12")
    try:
        from config import TP1_FRACAO_VOLUME
        frac_tp1 = int(round(TP1_FRACAO_VOLUME * 100))
    except Exception:
        frac_tp1 = 30
    try:
        from config import TRADE_TIMEOUT_HORAS
    except Exception:
        TRADE_TIMEOUT_HORAS = 168

    atualizados = 0
    for t in trades:
        if t["resultado"] != "ABERTO":
            continue
        try:
            sym = t["symbol"] + "/USDT:USDT"
            ticker = exchange.fetch_ticker(sym)
            preco  = ticker.get("last") or ticker.get("close", 0)
            if not preco:
                continue

            entrada = float(t.get("entrada", 0))
            tp1     = float(t.get("tp1", 0))
            stop    = float(t.get("stop", 0))
            direcao = t.get("direcao","")
            risco   = abs(entrada - stop) if entrada != stop else 0

            be      = float(t.get("be", 0))
            ja_be   = bool(t.get("be_tocado", False))
            # Gestão de Posição (2026-08-10) — stop_trailing só existe (e só
            # é usado) depois que o BE já foi tocado; nunca afrouxa o stop
            # original. Antes disso o comportamento é idêntico ao de sempre.
            stop_trail = t.get("stop_trailing")
            stop_efetivo = float(stop_trail) if (ja_be and stop_trail) else stop
            if direcao == "LONG":
                if preco >= tp1 and tp1 > 0:
                    rr = round(abs(tp1-entrada)/abs(stop-entrada), 2) if stop != entrada else 0
                    t["resultado"]  = "TP1"
                    t["r_obtido"]   = rr
                    t["r_tp1"]      = rr
                    t["pnl_usdt"]   = round(rr * 2.7, 2)
                    _set_r_devolvido(t, rr)
                    _marcar_fechamento(t)
                    if t.get("stop1_tocado"):
                        t["salvo_por_stop2"] = True
                    atualizados += 1
                    _log_tp1(log, t, direcao, rr, frac_tp1)
                elif preco <= stop_efetivo and stop_efetivo > 0:
                    trailou = ja_be and stop_trail and stop_efetivo > stop
                    rr = round((stop_efetivo - entrada) / risco, 2) if (trailou and risco > 0) else -1.0
                    t["resultado"]  = "TRAIL" if trailou else "STOP"
                    t["r_obtido"]   = rr
                    t["pnl_usdt"]   = round(rr * 2.7, 2)
                    _set_r_devolvido(t, rr)
                    _marcar_fechamento(t)
                    atualizados += 1
                elif be > 0 and ja_be and preco <= be and preco > stop_efetivo:
                    t["resultado"]  = "BE"
                    t["r_obtido"]   = 0
                    t["pnl_usdt"]   = 0
                    _set_r_devolvido(t, 0)
                    _marcar_fechamento(t)
                    atualizados += 1
                elif risco > 0 and (_idade_horas(t) or 0) > TRADE_TIMEOUT_HORAS:
                    rr = round((preco - entrada) / risco, 2)
                    t["resultado"]  = "TIMEOUT"
                    t["r_obtido"]   = rr
                    t["pnl_usdt"]   = round(rr * 2.7, 2)
                    _set_r_devolvido(t, rr)
                    _marcar_fechamento(t)
                    atualizados += 1
                    log.info(f"[K12][TIMEOUT] {t['symbol']} LONG fechado apos {TRADE_TIMEOUT_HORAS:.0f}h sem TP/stop | preco={preco} r={rr:+.2f}")
            else:  # SHORT
                if preco <= tp1 and tp1 > 0:
                    rr = round(abs(tp1-entrada)/abs(stop-entrada), 2) if stop != entrada else 0
                    t["resultado"]  = "TP1"
                    t["r_obtido"]   = rr
                    t["r_tp1"]      = rr
                    t["pnl_usdt"]   = round(rr * 2.7, 2)
                    _set_r_devolvido(t, rr)
                    _marcar_fechamento(t)
                    if t.get("stop1_tocado"):
                        t["salvo_por_stop2"] = True
                    atualizados += 1
                    _log_tp1(log, t, direcao, rr, frac_tp1)
                elif preco >= stop_efetivo and stop_efetivo > 0:
                    trailou = ja_be and stop_trail and stop_efetivo < stop
                    rr = round((entrada - stop_efetivo) / risco, 2) if (trailou and risco > 0) else -1.0
                    t["resultado"]  = "TRAIL" if trailou else "STOP"
                    t["r_obtido"]   = rr
                    t["pnl_usdt"]   = round(rr * 2.7, 2)
                    _set_r_devolvido(t, rr)
                    _marcar_fechamento(t)
                    atualizados += 1
                elif be > 0 and ja_be and preco >= be and preco < stop_efetivo:
                    t["resultado"]  = "BE"
                    t["r_obtido"]   = 0
                    t["pnl_usdt"]   = 0
                    _set_r_devolvido(t, 0)
                    _marcar_fechamento(t)
                    atualizados += 1
                elif risco > 0 and (_idade_horas(t) or 0) > TRADE_TIMEOUT_HORAS:
                    rr = round((entrada - preco) / risco, 2)
                    t["resultado"]  = "TIMEOUT"
                    t["r_obtido"]   = rr
                    t["pnl_usdt"]   = round(rr * 2.7, 2)
                    _set_r_devolvido(t, rr)
                    _marcar_fechamento(t)
                    atualizados += 1
                    log.info(f"[K12][TIMEOUT] {t['symbol']} SHORT fechado apos {TRADE_TIMEOUT_HORAS:.0f}h sem TP/stop | preco={preco} r={rr:+.2f}")

        except Exception as e:
            continue

    if atualizados > 0:
        _salvar(trades)

    return atualizados


def _linha(sym, direcao):
    return f"{sym} {direcao}".strip()


def _log_be(log, t, direcao, r, entrada, novo_stop):
    log.info(
        "[K12][BE]\n%s\nR=%.2f\nENTRADA=%.8g\nNOVO_STOP=%.8g\nH1_CONFIRMADO=True",
        _linha(t["symbol"], direcao), r, entrada, novo_stop
    )


def _log_tp1(log, t, direcao, rr, frac):
    log.info(
        "[K12][TP1]\n%s\nR=%.2f\nVOLUME_FECHADO=%d%%\nVOLUME_RESTANTE=%d%%",
        _linha(t["symbol"], direcao), rr, frac, 100 - frac
    )


def _idade_horas(t):
    """Idade do trade em horas. Usa entrada_ts (instrumentado desde
    24/08) quando existe; para trades mais antigos, cai no fallback de
    data/hora (string 'DD/MM/YYYY'/'HH:MM', formato usado desde sempre
    no registro). Retorna None se nao houver nenhuma fonte de tempo."""
    entrada_ts = t.get("entrada_ts")
    if entrada_ts:
        return (time.time() - entrada_ts) / 3600
    data_str, hora_str = t.get("data"), t.get("hora")
    if not data_str or not hora_str:
        return None
    try:
        dt = datetime.strptime(f"{data_str} {hora_str}", "%d/%m/%Y %H:%M")
        dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return None


def _set_r_devolvido(t, r_final):
    """MÉTRICA FASE 1 — R devolvido = maior R favorável - R final."""
    max_r = t.get("max_r_favoravel")
    base = max_r if max_r is not None else r_final
    t["r_devolvido"] = round(base - r_final, 2)


def _marcar_fechamento(t):
    """RFC operacao-rapida 24/08 — grava fechado_ts/duracao_h/tempo_ate_*
    no momento em que o trade sai de ABERTO. Chamado sempre junto de
    _set_r_devolvido (mesmo evento de fechamento). Aditivo, so le/escreve
    campos de tempo -- nao influencia resultado nem r_obtido."""
    agora = time.time()
    entrada_ts = t.get("entrada_ts")
    t["fechado_ts"] = agora
    if entrada_ts:
        duracao_h = round((agora - entrada_ts) / 3600, 2)
        t["duracao_h"] = duracao_h
        if t.get("resultado") == "TP1":
            t["tempo_ate_tp1_h"] = duracao_h
        elif t.get("resultado") in ("STOP", "TRAIL"):
            t["tempo_ate_stop_h"] = duracao_h


def _log_trailing(log, t, direcao, familia, tf, ref, old, novo, r_atual):
    log.info(
        "[K12][TRAILING]\n%s\nR=%.2f\nSETUP=%s\nTF=%s\nREF=%.8g\nOLD_STOP=%.8g\nNEW_STOP=%.8g",
        _linha(t["symbol"], direcao), r_atual, familia, (tf or ""), ref, old, novo
    )


def _log_block(log, t, direcao, familia, tf, ref, old):
    log.info(
        "[K12][TRAILING][BLOCK]\n%s\nNovo stop rejeitado\nMotivo: reduziria proteção\nSETUP=%s TF=%s REF=%.8g OLD=%.8g",
        _linha(t["symbol"], direcao), familia, (tf or ""), ref, old
    )


def _log_bos(log, t, direcao, idade, limite):
    log.info(
        "[K12][BOS]\n%s\nBOS/CHoCH idade=%d > %d — estrutura antiga, trailing bloqueado",
        _linha(t["symbol"], direcao), idade, limite
    )


def verificar_gestao_avancada() -> list:
    """Gestão de Posição V58.1 — 3 partes:

    0. BE (sempre ativo): só ativa com R >= BE_TRIGGER_R confirmado no
       candle H1 fechado (BE_EXIGE_H1_FECHADO). Depois do BE o stop mínimo
       é a entrada — proteção monotônica (nunca recua).
    1. Trailing (flag TRAILING_ATIVO): só depois do BE. Regra por família
       de setup (REVERSÃO 2R/H1, TENDÊNCIA 1.5R/30M, BREAKOUT mantém a
       regra ATR existente). BOS Age reutiliza o BOS/CHoCH real já
       calculado pelo K11 (k10_engine._bos_idade) — limite
       BOS_AGE_MAX_CANDLES.
    2. Alerta de Saída Estrutural (flag ESTRUTURAL_ALERTA_ATIVO): avisa
       (não fecha) quando a estrutura virou contra antes do TP/Stop.

    Roda 1x por ciclo, só sobre trades ABERTOS. Retorna os textos pro
    Telegram (envio de fato é responsabilidade do runner.py)."""
    import logging
    log = logging.getLogger("K12")
    from config import TRAILING_ATIVO, ESTRUTURAL_ALERTA_ATIVO, BOS_AGE_MAX_CANDLES
    from gestao_trade import (avaliar_be, aplicar_be_stop, bos_age,
                              calcular_r, candidato_trailing, config_trailing,
                              proteger_stop, tf_display)

    trades = _carregar()
    abertos = [t for t in trades if t["resultado"] == "ABERTO"]
    if not abertos:
        return []

    if not TRAILING_ATIVO:
        log.info("[K12][TRAILING]\nstatus=OFF")

    try:
        from k10_engine import K10Engine
    except Exception:
        return []
    engine = K10Engine()

    avisos = []
    alterado = False

    for t in trades:
        if t["resultado"] != "ABERTO":
            continue
        direcao = t.get("direcao")
        entrada = float(t.get("entrada", 0) or 0)
        stop_original = float(t.get("stop", 0) or 0)
        if not entrada or not stop_original or direcao not in ("LONG", "SHORT"):
            continue

        symbol = t["symbol"] + "/USDT:USDT"
        familia, cfg_trail = config_trailing(t.get("setup", ""))

        # H1 fechado (uma só busca por operação p/ status + BE)
        h1_df = None
        try:
            h1_df = engine._calc(engine._fetch(symbol, "1h", limit=60))
        except Exception:
            pass

        # ── LOG DE GESTÃO POR OPERAÇÃO (FASE 1, log interno) ──────────
        if h1_df is not None and len(h1_df) >= 3:
            vela_h1 = h1_df.iloc[-2]
            close_h1 = float(vela_h1["close"])
            r_atual = calcular_r(entrada, stop_original, close_h1, direcao)
            stop_atual = float(t.get("stop_trailing") or stop_original)
            log.info(
                "[K12][GESTAO]\n%s\nSETUP=%s\nR=%.2f\nBE=%s\nH1_FECHADO=SIM\nSTOP_ATUAL=%.8g",
                _linha(t["symbol"], direcao), familia, r_atual,
                ("SIM" if t.get("be_tocado") else "NAO"), stop_atual
            )
            # MÉTRICA FASE 1 — maior R favorável (pico do candle H1 fechado)
            if direcao == "LONG":
                r_pico = calcular_r(entrada, stop_original, float(vela_h1["high"]), "LONG")
            else:
                r_pico = calcular_r(entrada, stop_original, float(vela_h1["low"]), "SHORT")
            if r_pico > float(t.get("max_r_favoravel") or 0):
                t["max_r_favoravel"] = round(r_pico, 2)
                # RFC operacao-rapida 24/08 — tempo ate o pico (MFE), pra
                # distinguir "foi rapido e devolveu" (gestao) de "nunca
                # teve momentum" (secao 8 da RFC).
                if t.get("entrada_ts"):
                    t["tempo_ate_mfe_h"] = round((time.time() - t["entrada_ts"]) / 3600, 2)
                alterado = True

            # MAE — máxima excursão adversa (pior R contra, candle H1 fechado)
            if direcao == "LONG":
                r_pior = calcular_r(entrada, stop_original, float(vela_h1["low"]), "LONG")
            else:
                r_pior = calcular_r(entrada, stop_original, float(vela_h1["high"]), "SHORT")
            if t.get("max_r_adverso") is None or r_pior < t["max_r_adverso"]:
                t["max_r_adverso"] = round(r_pior, 2)
                if t.get("entrada_ts"):
                    t["tempo_ate_mae_h"] = round((time.time() - t["entrada_ts"]) / 3600, 2)
                alterado = True

            # RFC stop-duplo 23/08 — STOP1 é só monitorado/logado aqui, NUNCA
            # fecha o trade (fechamento continua via `stop`/stop_efetivo em
            # verificar_resultados_automatico). Objetivo: medir empiricamente
            # quantas operações o STOP1 mataria que sobrevivem até o TP.
            stop1_val = t.get("stop1")
            if stop1_val:
                if direcao == "LONG":
                    tocou_stop1 = float(vela_h1["low"]) <= float(stop1_val)
                else:
                    tocou_stop1 = float(vela_h1["high"]) >= float(stop1_val)
                if tocou_stop1 and not t.get("stop1_tocado"):
                    t["stop1_tocado"] = True
                    t["mfe_apos_stop1"] = 0.0
                    alterado = True
                if t.get("stop1_tocado"):
                    mfe_atual = max(r_pico, 0.0)
                    if t.get("mfe_apos_stop1") is None or mfe_atual > t["mfe_apos_stop1"]:
                        t["mfe_apos_stop1"] = round(mfe_atual, 2)
                        alterado = True

        # ── 0. BE V58.1 (sempre ativo) — R>=BE_TRIGGER_R em H1 fechado ──
        if not t.get("be_tocado"):
            ativar, r_be, motivo = avaliar_be(engine, symbol, direcao, entrada, stop_original, df=h1_df)
            if ativar:
                atual = float(t.get("stop_trailing") or stop_original)
                novo = round(aplicar_be_stop(atual, entrada, direcao), 8)
                t["be_tocado"] = True
                t["stop_trailing"] = novo
                t["r_be_momento"] = round(r_be, 2)
                alterado = True
                _log_be(log, t, direcao, r_be, entrada, novo)

        # ── 1. Trailing (só depois do BE armado) — regra por família ─────
        if TRAILING_ATIVO and t.get("be_tocado"):
            tf_trail = cfg_trail.get("timeframe") or t.get("timeframe") or "30m"
            try:
                df_trail = engine._calc(engine._fetch(symbol, tf_trail, limit=60))
            except Exception:
                df_trail = None
            if df_trail is not None and len(df_trail) >= 5:
                idade, bos_ok = bos_age(engine, df_trail, direcao)
                if not bos_ok:
                    _log_bos(log, t, direcao, idade, BOS_AGE_MAX_CANDLES)
                else:
                    cand, r_atual = candidato_trailing(df_trail, cfg_trail, entrada, stop_original, direcao)
                    if cand is not None:
                        atual = float(t.get("stop_trailing") or stop_original)
                        novo = round(proteger_stop(atual, cand, direcao), 8)
                        if novo != atual:
                            t["stop_trailing"] = novo
                            alterado = True
                            _log_trailing(log, t, direcao, familia, tf_display(tf_trail),
                                          cand, atual, novo, r_atual)
                        elif (direcao == "LONG" and cand < atual) or (direcao == "SHORT" and cand > atual):
                            _log_block(log, t, direcao, familia, tf_display(tf_trail), cand, atual)

        # ── 2. Alerta de Saída Estrutural ─────────────────────────────────
        if ESTRUTURAL_ALERTA_ATIVO and not t.get("alerta_estrutural_enviado"):
            tf = t.get("timeframe") or "30m"
            try:
                df = engine._calc(engine._fetch(symbol, tf, limit=60))
            except Exception:
                df = None
            if df is not None and len(df) >= 5:
                r = df.iloc[-2]
                close = float(r["close"]); ema10 = float(r["ema10"]); ema21 = float(r["ema21"])
                macd_hist = float(r["macd_hist"])
                invalidado = (
                    (direcao == "LONG" and close < ema21 and ema10 < ema21 and macd_hist < 0) or
                    (direcao == "SHORT" and close > ema21 and ema10 > ema21 and macd_hist > 0)
                )
                if invalidado:
                    t["alerta_estrutural_enviado"] = True
                    alterado = True
                    avisos.append(
                        f"🚨 K12 — Estrutura invalidada em {t['symbol']} ({direcao} {tf}): "
                        f"tendência virou contra. Considere sair — ainda longe do TP/Stop."
                    )

    if alterado:
        _salvar(trades)

    return avisos


def relatorio_calibracao() -> str:
    """Relatório de calibração — análise por Score, EQ, Tier, Setup."""
    trades = _carregar()
    fechados = [t for t in trades if t["resultado"] != "ABERTO"]
    if len(fechados) < 10:
        return f"Calibração: {len(fechados)}/50 trades fechados — coletando dados..."

    sep = "━━━━━━━━━━━━━━━━━━━━"
    now_brt = brt_now()
    linhas = [
        f"🔬 K12 — RELATÓRIO DE CALIBRAÇÃO",
        f"📅 {now_brt.strftime('%d/%m/%Y %H:%M')} BRT",
        f"Total fechados: {len(fechados)}",
        sep
    ]

    def stats(grupo, label):
        if not grupo: return
        wins = [t for t in grupo if t["resultado"] in ("TP1","TP2")]
        wr   = len(wins)/len(grupo)*100
        r_vals = [t["r_obtido"] for t in grupo if t.get("r_obtido") is not None]
        pf = 0
        if r_vals:
            r_pos = sum(r for r in r_vals if r > 0)
            r_neg = abs(sum(r for r in r_vals if r < 0))
            pf = round(r_pos/r_neg, 2) if r_neg > 0 else 0
            r_med = round(sum(r_vals)/len(r_vals), 2)
            linhas.append(f"{label}: n={len(grupo)} WR={wr:.0f}% PF={pf} R={r_med:+.2f}")
        else:
            linhas.append(f"{label}: n={len(grupo)} WR={wr:.0f}%")

    # Por Score
    linhas += ["", "📊 POR SCORE:"]
    stats([t for t in fechados if 75<=t.get("score",0)<=79], "75-79")
    stats([t for t in fechados if 80<=t.get("score",0)<=89], "80-89")
    stats([t for t in fechados if 90<=t.get("score",0)<=99], "90-99")
    stats([t for t in fechados if t.get("score",0)==100],    "100  ")

    # Por Entry Quality
    linhas += ["", "🎯 POR ENTRY QUALITY:"]
    stats([t for t in fechados if t.get("entry_quality",0)<70],          "EQ <70 ")
    stats([t for t in fechados if 70<=t.get("entry_quality",0)<=79],     "EQ 70-79")
    stats([t for t in fechados if 80<=t.get("entry_quality",0)<=89],     "EQ 80-89")
    stats([t for t in fechados if t.get("entry_quality",0)>=90],         "EQ 90+  ")

    # Por Tier
    linhas += ["", "🏆 POR TIER:"]
    stats([t for t in fechados if t.get("tier")=="OURO"],  "OURO ")
    stats([t for t in fechados if t.get("tier")=="PRATA"], "PRATA")

    # Por Direção
    linhas += ["", "↕ POR DIREÇÃO:"]
    stats([t for t in fechados if t.get("direcao")=="LONG"],  "LONG ")
    stats([t for t in fechados if t.get("direcao")=="SHORT"], "SHORT")

    # Por Timeframe
    linhas += ["", "⏱ POR TIMEFRAME:"]
    stats([t for t in fechados if t.get("timeframe")=="30m"], "30m")
    stats([t for t in fechados if t.get("timeframe")=="1h"],  "1h ")

    linhas += [sep, "🔬 K12 Calibração Estatística"]
    return "\n".join(linhas)


def _calc_grupo(grupo) -> dict:
    if not grupo:
        return None
    wins   = [t for t in grupo if t["resultado"] in ("TP1", "TP2")]
    losses = [t for t in grupo if t["resultado"] == "STOP"]
    r_vals = [t["r_obtido"] for t in grupo if t.get("r_obtido") is not None]
    r_pos  = sum(r for r in r_vals if r > 0)
    r_neg  = abs(sum(r for r in r_vals if r < 0))
    return {
        "n":       len(grupo),
        "wins":    len(wins),
        "losses":  len(losses),
        "wr":      round(len(wins) / len(grupo) * 100, 1),
        "pf":      round(r_pos / r_neg, 2) if r_neg > 0 else 0.0,
        "r_med":   round(sum(r_vals) / len(r_vals), 2) if r_vals else 0.0,
        "r_total": round(sum(r_vals), 2),
    }


def relatorio_fase1() -> str:
    """Relatório específico da FASE 1 (V58.1): BE 1.5R + H1 fechado + TP1 30%,
    trailing OFF. Métricas globais, estados de saída, por família de setup e
    por timeframe. Uso interno/auditoria (não vai ao Telegram)."""
    from gestao_trade import normalizar_setup

    trades    = _carregar()
    fechados  = [t for t in trades if t["resultado"] != "ABERTO"]
    abertos   = [t for t in trades if t["resultado"] == "ABERTO"]
    sep = "━━━━━━━━━━━━━━━━━━━━"

    linhas = [
        "📊 K12 — RELATÓRIO FASE 1 (BE 1.5R + H1 + TP1 30%, trailing OFF)",
        f"📅 {brt_now().strftime('%d/%m/%Y %H:%M')} BRT",
        sep,
    ]

    g = _calc_grupo(fechados)
    if not g:
        linhas.append("Sem trades fechados ainda — coletando dados…")
        linhas.append(sep)
        return "\n".join(linhas)

    exp = round(sum(t.get("r_obtido") or 0 for t in fechados) / len(fechados), 2)
    linhas += [
        "GERAL:",
        f"  Operações: {len(fechados)} (abertos: {len(abertos)})",
        f"  Wins: {g['wins']} | Losses: {g['losses']}",
        f"  Win Rate: {g['wr']:.1f}%",
        f"  Profit Factor: {g['pf']}",
        f"  R médio: {g['r_med']:+.2f}R",
        f"  Expectancy: {exp:+.2f}R",
        f"  R total: {g['r_total']:+.2f}R",
        sep,
    ]

    estados = ["TP1", "TP2", "BE", "STOP"]
    linhas.append("ESTADOS DE SAÍDA:")
    for st in estados:
        n = len([t for t in fechados if t.get("resultado") == st])
        linhas.append(f"  {st}: {n}")
    outros = [t for t in fechados if t.get("resultado") not in estados]
    if outros:
        linhas.append(f"  OUTROS (ex.: TRAIL): {len(outros)}")

    linhas.append(sep)
    linhas.append("POR FAMÍLIA DE SETUP:")
    fams = ["REVERSAO", "TENDENCIA", "BREAKOUT", "DEFAULT"]
    for fam in fams:
        grupo = [t for t in fechados if normalizar_setup(t.get("setup", "")) == fam]
        gg = _calc_grupo(grupo)
        if gg:
            linhas.append(
                f"  {fam}: n={gg['n']} WR={gg['wr']:.1f}% PF={gg['pf']} "
                f"Rmed={gg['r_med']:+.2f} Rtot={gg['r_total']:+.2f}"
            )

    linhas.append(sep)
    linhas.append("POR TIMEFRAME:")
    for tf_label, tf_val in (("30M", "30m"), ("1H", "1h")):
        grupo = [t for t in fechados if t.get("timeframe") == tf_val]
        gg = _calc_grupo(grupo)
        if gg:
            linhas.append(
                f"  {tf_label}: n={gg['n']} WR={gg['wr']:.1f}% PF={gg['pf']} Rmed={gg['r_med']:+.2f}"
            )

    def _media(chave):
        vals = [t.get(chave) for t in fechados if t.get(chave) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    devolv = [t.get("r_devolvido") for t in fechados if (t.get("r_devolvido") or 0) > 0]
    linhas += [
        sep,
        "R AVANÇO / DEVOLUÇÃO (média por trade, coleta FASE 1):",
        f"  Maior R favorável : {_media('max_r_favoravel')}",
        f"  R no TP1          : {_media('r_tp1')}",
        f"  R no momento do BE: {_media('r_be_momento')}",
        f"  R final           : {g['r_med']:+.2f}R",
        f"  R devolvido (R>0) : {round(sum(devolv) / len(devolv), 2) if devolv else 0:+.2f} em {len(devolv)} trades",
    ]

    linhas += [sep, "🔬 K12 FASE 1 — coleta de dados"]
    return "\n".join(linhas)
