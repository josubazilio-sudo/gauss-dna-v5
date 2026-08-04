"""
K11 Trade Tracker — Registro e Relatório Profissional
"""
import json, os
from datetime import datetime

ARQUIVO = "k11_trades.json"

def registrar(sinal: dict) -> int:
    trades = _carregar()
    entry = {
        "id":        len(trades) + 1,
        "data":      datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
        "symbol":    sinal.get("symbol","").replace("/USDT:USDT",""),
        "direcao":   sinal.get("direcao",""),
        "timeframe": sinal.get("timeframe",""),
        "score":     sinal.get("score", 0),
        "tier":      sinal.get("tier",""),
        "rvol":      round(sinal.get("rvol", 0), 2),
        "rr_alvo":   sinal.get("rr", 0),
        "entrada":   sinal.get("entrada", 0),
        "tp1":       sinal.get("tp1", 0),
        "stop":      sinal.get("stop", 0),
        "regime":    sinal.get("regime",""),
        "confs":     len(sinal.get("confirmacoes_smc", [])),
        "resultado": "ABERTO",
        "r_obtido":  None,
        "duracao_h": None,
        "obs":       "",
    }
    trades.append(entry)
    _salvar(trades)
    return entry["id"]

def _carregar():
    if os.path.exists(ARQUIVO):
        try:
            with open(ARQUIVO) as f: return json.load(f)
        except: return []
    return []

def _salvar(trades):
    with open(ARQUIVO, "w") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)

def relatorio_telegram() -> str:
    trades = _carregar()
    if not trades:
        return "📊 K11 — Nenhum trade registrado ainda."

    total    = len(trades)
    abertos  = [t for t in trades if t["resultado"] == "ABERTO"]
    fechados = [t for t in trades if t["resultado"] != "ABERTO"]
    wins     = [t for t in fechados if t["resultado"] in ("TP1","TP2")]
    losses   = [t for t in fechados if t["resultado"] == "STOP"]
    cancelados = [t for t in fechados if t["resultado"] == "CANCELADO"]

    sep = "━━━━━━━━━━━━━━━━━━━━"

    linhas = [
        f"📊 K11 — RELATÓRIO PROFISSIONAL",
        f"🗓 Gerado: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC",
        sep,
        f"",
        f"📈 RESUMO GERAL",
        f"Total de sinais: {total}",
        f"Fechados: {len(fechados)} | Abertos: {len(abertos)}",
        f"Wins: {len(wins)} | Losses: {len(losses)} | Cancelados: {len(cancelados)}",
    ]

    if fechados:
        wr = len(wins)/len(fechados)*100
        linhas.append(f"Win Rate: {wr:.1f}%")

        r_vals = [t["r_obtido"] for t in fechados if t["r_obtido"] is not None]
        if r_vals:
            r_pos = sum(r for r in r_vals if r > 0)
            r_neg = abs(sum(r for r in r_vals if r < 0))
            pf    = round(r_pos/r_neg, 2) if r_neg > 0 else "∞"
            r_med = round(sum(r_vals)/len(r_vals), 2)
            r_max = round(max(r_vals), 2)
            r_min = round(min(r_vals), 2)
            linhas += [
                f"Profit Factor: {pf}",
                f"R Médio: {r_med}R",
                f"Melhor trade: +{r_max}R",
                f"Pior trade: {r_min}R",
            ]

        linhas += ["", sep, "", "📋 POR TIER"]
        for tier in ["OURO","PRATA","BRONZE"]:
            tt = [t for t in fechados if t.get("tier") == tier]
            if tt:
                tw = [t for t in tt if t["resultado"] in ("TP1","TP2")]
                linhas.append(f"{tier}: {len(tw)}/{len(tt)} wins ({len(tw)/len(tt)*100:.0f}%)")

        linhas += ["", sep, "", "📋 POR TIMEFRAME"]
        for tf in ["30m","1h","4h","1d"]:
            tt = [t for t in fechados if t.get("timeframe") == tf]
            if tt:
                tw = [t for t in tt if t["resultado"] in ("TP1","TP2")]
                linhas.append(f"{tf}: {len(tw)}/{len(tt)} ({len(tw)/len(tt)*100:.0f}%)")

        linhas += ["", sep, "", "📋 POR DIREÇÃO"]
        for dir in ["LONG","SHORT"]:
            tt = [t for t in fechados if t.get("direcao") == dir]
            if tt:
                tw = [t for t in tt if t["resultado"] in ("TP1","TP2")]
                linhas.append(f"{dir}: {len(tw)}/{len(tt)} ({len(tw)/len(tt)*100:.0f}%)")

        if len(fechados) < 50:
            linhas += ["", f"⚠️ {len(fechados)}/50 trades — dados insuficientes para conclusão definitiva"]

    linhas += ["", sep, "", "📋 ÚLTIMOS SINAIS"]
    for t in trades[-8:][::-1]:
        res = t["resultado"]
        emoji = "✅" if res in ("TP1","TP2") else "❌" if res=="STOP" else "⏳" if res=="ABERTO" else "↩️"
        r_str = f" ({t['r_obtido']}R)" if t["r_obtido"] is not None else ""
        linhas.append(f"{emoji} #{t['id']} {t['symbol']} {t['direcao']} {t['timeframe']} s={t['score']} — {res}{r_str}")

    linhas += ["", sep, "K11 Performance Tracker"]
    return "
".join(linhas)
