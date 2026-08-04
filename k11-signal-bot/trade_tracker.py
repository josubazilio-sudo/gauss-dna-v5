"""
K11 Trade Tracker — Salva no GitHub para acesso via VS Code
"""
import json, os, base64, requests
from datetime import datetime

ARQUIVO    = "k11_trades.json"
REPO       = "josubazilio-sudo/gauss-dna-v5"
REPO_PATH  = "k11-signal-bot/k11_trades.json"
GH_TOKEN   = os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN", ""))

def _headers():
    return {"Authorization": f"token {GH_TOKEN}", "Content-Type": "application/json"}

def _carregar_github():
    """Carrega trades do GitHub."""
    try:
        r = requests.get(
            f"https://api.github.com/repos/{REPO}/contents/{REPO_PATH}",
            headers=_headers(), timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            content = base64.b64decode(data["content"]).decode()
            return json.loads(content), data.get("sha")
    except:
        pass
    return [], None

def _salvar_github(trades, sha=None):
    """Salva trades no GitHub."""
    try:
        url = f"https://api.github.com/repos/{REPO}/contents/{REPO_PATH}"
        content = json.dumps(trades, indent=2, ensure_ascii=False)
        payload = {
            "message": f"K11 trade #{len(trades)} registrado",
            "content": base64.b64encode(content.encode()).decode()
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(url, headers=_headers(), json=payload, timeout=15)
        return r.status_code in (200, 201)
    except:
        return False

def registrar(sinal: dict) -> int:
    trades, sha = _carregar_github()
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
    _salvar_github(trades, sha)
    return entry["id"]

def relatorio_completo() -> str:
    trades, _ = _carregar_github()
    if not trades:
        return "Nenhum trade registrado."

    hoje = datetime.utcnow().strftime("%d/%m/%Y")
    todos     = trades
    de_hoje   = [t for t in trades if t["data"].startswith(hoje)]
    fechados  = [t for t in todos if t["resultado"] != "ABERTO"]
    wins      = [t for t in fechados if t["resultado"] in ("TP1","TP2")]
    losses    = [t for t in fechados if t["resultado"] == "STOP"]

    sep = "━━━━━━━━━━━━━━━━━━━━"
    linhas = [
        "📊 K11 — RELATÓRIO COMPLETO",
        f"🗓 {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC",
        sep,
        f"Total de sinais: {len(todos)}",
        f"Hoje: {len(de_hoje)} sinais",
        f"Fechados: {len(fechados)} | Abertos: {len(todos)-len(fechados)}",
    ]

    if fechados:
        wr = len(wins)/len(fechados)*100
        r_vals = [t["r_obtido"] for t in fechados if t["r_obtido"] is not None]
        linhas += [
            f"Wins: {len(wins)} | Losses: {len(losses)}",
            f"Win Rate: {wr:.1f}%",
        ]
        if r_vals:
            r_pos = sum(r for r in r_vals if r > 0)
            r_neg = abs(sum(r for r in r_vals if r < 0))
            pf    = round(r_pos/r_neg, 2) if r_neg > 0 else "∞"
            linhas += [
                f"Profit Factor: {pf}",
                f"R Médio: {round(sum(r_vals)/len(r_vals),2)}R",
                f"Melhor: +{max(r_vals)}R | Pior: {min(r_vals)}R",
            ]

    linhas += [sep, "SINAIS DE HOJE"]
    for t in de_hoje:
        res   = t["resultado"]
        emoji = "✅" if res in ("TP1","TP2") else "❌" if res=="STOP" else "⏳"
        r_str = f" ({t['r_obtido']}R)" if t["r_obtido"] else ""
        linhas.append(
            f"{emoji} #{t['id']} {t['symbol']} {t['direcao']} {t['timeframe']} "
            f"s={t['score']} — {res}{r_str}"
        )

    if len(fechados) < 50:
        linhas += [sep, f"⚠️ {len(fechados)}/50 trades para análise definitiva"]

    return "\n".join(linhas)

def stats_rapidas() -> str:
    """Retorna linha de estatísticas para colocar no cartão/diagnóstico."""
    trades, _ = _carregar_github()
    if not trades:
        return "📊 Sem histórico ainda"

    fechados = [t for t in trades if t["resultado"] != "ABERTO"]
    if not fechados:
        total = len(trades)
        return f"📊 {total} sinais | Aguardando resultados"

    wins   = [t for t in fechados if t["resultado"] in ("TP1","TP2")]
    losses = [t for t in fechados if t["resultado"] == "STOP"]
    wr     = len(wins)/len(fechados)*100

    r_vals = [t["r_obtido"] for t in fechados if t["r_obtido"] is not None]
    if r_vals:
        r_pos = sum(r for r in r_vals if r > 0)
        r_neg = abs(sum(r for r in r_vals if r < 0))
        pf    = round(r_pos/r_neg, 2) if r_neg > 0 else 0
        r_med = round(sum(r_vals)/len(r_vals), 2)
        return (
            f"📊 {len(fechados)} trades | "
            f"✅{len(wins)} ❌{len(losses)} | "
            f"WR {wr:.0f}% | "
            f"PF {pf} | "
            f"R̄ {r_med:+.1f}R"
        )
    return (
        f"📊 {len(fechados)} trades | "
        f"✅{len(wins)} ❌{len(losses)} | "
        f"WR {wr:.0f}%"
    )
