"""
K11 Sistema de Relatório
- Registra cada sinal automaticamente
- Envia relatório a cada 2h
- Resumo completo às 23:30 BRT
"""
import json, os, requests
from datetime import datetime, timezone, timedelta

ARQUIVO   = "/root/gauss-dna-v5/k11-signal-bot/k11_trades.json"
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID   = os.getenv("ALLOWED_CHAT_IDS", "").split(",")[0].strip()

def brt_now():
    return datetime.now(timezone.utc) - timedelta(hours=3)

def _carregar():
    if os.path.exists(ARQUIVO):
        try:
            with open(ARQUIVO) as f: return json.load(f)
        except: return []
    return []

def _salvar(trades):
    with open(ARQUIVO, "w") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)

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
        "regime":       sinal.get("regime",""),
        "setup":        sinal.get("prioridade","").replace("🔥","").replace("⭐","").strip(),
        "confs":        len(sinal.get("confirmacoes_smc", [])),
        "dist_ema21":   round(abs(sinal.get("entrada",0)-sinal.get("ema21",0)) / sinal.get("atr",1) if sinal.get("atr",0) > 0 else 0, 2),
        "resultado":    "ABERTO",
        "r_obtido":     None,
        "pnl_usdt":     None,
        "duracao_h":    None,
    }
    trades.append(entry)
    _salvar(trades)
    return entry["id"]

def stats_rapidas() -> str:
    trades = _carregar()
    if not trades:
        return "📊 Sem histórico ainda"
    fechados = [t for t in trades if t["resultado"] != "ABERTO"]
    abertos  = [t for t in trades if t["resultado"] == "ABERTO"]
    if not fechados:
        return f"📊 {len(trades)} sinais | {len(abertos)} abertos | Aguardando resultados"
    wins   = [t for t in fechados if t["resultado"] in ("TP1","TP2")]
    losses = [t for t in fechados if t["resultado"] == "STOP"]
    wr     = len(wins)/len(fechados)*100
    r_vals = [t["r_obtido"] for t in fechados if t.get("r_obtido") is not None]
    if r_vals:
        r_pos = sum(r for r in r_vals if r > 0)
        r_neg = abs(sum(r for r in r_vals if r < 0))
        pf    = round(r_pos/r_neg, 2) if r_neg > 0 else 0
        r_med = round(sum(r_vals)/len(r_vals), 2)
        return f"📊 {len(fechados)} trades | ✅{len(wins)} ❌{len(losses)} | WR {wr:.0f}% | PF {pf} | R̄ {r_med:+.1f}R"
    return f"📊 {len(fechados)} trades | ✅{len(wins)} ❌{len(losses)} | WR {wr:.0f}%"

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
        f"📊 K11 — RELATÓRIO 2H",
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
            emoji = "✅" if t["resultado"] in ("TP1","TP2") else "❌" if t["resultado"]=="STOP" else "⏳"
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
        f"🌙 K11 — RESUMO DO DIA",
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
        emoji = "✅" if t["resultado"] in ("TP1","TP2") else "❌" if t["resultado"]=="STOP" else "⏳"
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

    linhas += [sep, "K11 — Boa noite! 🌙"]
    return "\n".join(linhas)

def enviar_telegram(msg: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg[:4096]}, timeout=30)


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

    trades, sha = _carregar_github()
    abertos = [t for t in trades if t["resultado"] == "ABERTO"]
    if not abertos:
        return 0

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

            if direcao == "LONG":
                if preco >= tp1 and tp1 > 0:
                    rr = round(abs(tp1-entrada)/abs(stop-entrada), 2) if stop != entrada else 0
                    t["resultado"]  = "TP1"
                    t["r_obtido"]   = rr
                    t["pnl_usdt"]   = round(rr * 2.7, 2)
                    atualizados += 1
                elif preco <= stop and stop > 0:
                    rr = -1.0
                    t["resultado"]  = "STOP"
                    t["r_obtido"]   = rr
                    t["pnl_usdt"]   = round(rr * 2.7, 2)
                    atualizados += 1
            else:  # SHORT
                if preco <= tp1 and tp1 > 0:
                    rr = round(abs(tp1-entrada)/abs(stop-entrada), 2) if stop != entrada else 0
                    t["resultado"]  = "TP1"
                    t["r_obtido"]   = rr
                    t["pnl_usdt"]   = round(rr * 2.7, 2)
                    atualizados += 1
                elif preco >= stop and stop > 0:
                    rr = -1.0
                    t["resultado"]  = "STOP"
                    t["r_obtido"]   = rr
                    t["pnl_usdt"]   = round(rr * 2.7, 2)
                    atualizados += 1

        except Exception as e:
            continue

    if atualizados > 0:
        _salvar_github(trades, sha)

    return atualizados


def relatorio_calibracao() -> str:
    """Relatório de calibração — análise por Score, EQ, Tier, Setup."""
    trades, _ = _carregar_github()
    fechados = [t for t in trades if t["resultado"] != "ABERTO"]
    if len(fechados) < 10:
        return f"Calibração: {len(fechados)}/50 trades fechados — coletando dados..."

    sep = "━━━━━━━━━━━━━━━━━━━━"
    now_brt = brt_now()
    linhas = [
        f"🔬 K11 — RELATÓRIO DE CALIBRAÇÃO",
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

    linhas += [sep, "🔬 K11 Calibração Estatística"]
    return "\n".join(linhas)
