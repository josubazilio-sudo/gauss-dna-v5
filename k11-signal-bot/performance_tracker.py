"""
K11 Performance Tracker — RFC Teste Adaptativo V1
Registra cada sinal enviado para análise estatística posterior.
Arquivo: k11_trades.json (acumulativo por ciclo)
"""

import json, os
from datetime import datetime

ARQUIVO = "k11_trades.json"

SETUP_LABELS = {
    "TENDENCIA":   "1. Tendência",
    "REVERSAO":    "2. Reversão",
    "CRUZAMENTO":  "3. Cruzamento",
    "LATERAL":     "4. Lateralidade",
    "VIRADA":      "3. Cruzamento",
    "NEUTRO":      "2. Reversão",
}

def registrar_sinal(sinal: dict):
    """Registra um sinal enviado no arquivo de trades."""
    trades = _carregar()

    setup = SETUP_LABELS.get(
        sinal.get("regime_mercado", sinal.get("setup_nome", "NEUTRO")),
        "2. Reversão"
    )

    entry = {
        "id":        len(trades) + 1,
        "timestamp": datetime.utcnow().isoformat(),
        "symbol":    sinal.get("symbol",""),
        "direcao":   sinal.get("direcao",""),
        "timeframe": sinal.get("timeframe",""),
        "setup":     setup,
        "score":     sinal.get("score", 0),
        "tier":      sinal.get("tier",""),
        "rvol":      round(sinal.get("rvol", 0), 2),
        "adx":       round(sinal.get("adx", 0), 1),
        "rr":        sinal.get("rr", 0),
        "entrada":   sinal.get("entrada", 0),
        "tp1":       sinal.get("tp1", 0),
        "stop":      sinal.get("stop", 0),
        "resultado": "ABERTO",   # ABERTO / TP1 / TP2 / STOP / CANCELADO
        "r_obtido":  None,
        "duracao_h": None,
    }

    trades.append(entry)
    _salvar(trades)
    return entry["id"]

def _carregar():
    if os.path.exists(ARQUIVO):
        try:
            with open(ARQUIVO) as f:
                return json.load(f)
        except:
            return []
    return []

def _salvar(trades):
    with open(ARQUIVO, "w") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)

def gerar_relatorio() -> str:
    """Gera relatório de performance por setup."""
    trades = _carregar()
    if not trades:
        return "Nenhum trade registrado ainda."

    fechados = [t for t in trades if t["resultado"] != "ABERTO"]
    abertos  = [t for t in trades if t["resultado"] == "ABERTO"]

    if not fechados:
        return (
            f"📊 K11 Performance Tracker\n"
            f"Total sinais: {len(trades)}\n"
            f"Abertos: {len(abertos)}\n"
            f"Fechados: 0 (mínimo 50 para análise)"
        )

    wins  = [t for t in fechados if t["resultado"] in ("TP1","TP2")]
    loses = [t for t in fechados if t["resultado"] == "STOP"]
    wr    = len(wins)/len(fechados)*100 if fechados else 0

    r_vals = [t["r_obtido"] for t in fechados if t["r_obtido"] is not None]
    r_med  = sum(r_vals)/len(r_vals) if r_vals else 0
    r_pos  = sum(r for r in r_vals if r > 0)
    r_neg  = abs(sum(r for r in r_vals if r < 0))
    pf     = round(r_pos/r_neg, 2) if r_neg > 0 else 0

    linhas = [
        f"📊 K11 Performance — {len(fechados)} trades fechados\n",
        f"Win Rate: {wr:.1f}%",
        f"Profit Factor: {pf}",
        f"R médio: {r_med:.2f}",
        f"Wins: {len(wins)} | Losses: {len(loses)}",
        f"Abertos: {len(abertos)}\n",
    ]

    # Por setup
    setups = set(t["setup"] for t in fechados)
    for s in sorted(setups):
        st = [t for t in fechados if t["setup"] == s]
        sw = [t for t in st if t["resultado"] in ("TP1","TP2")]
        linhas.append(
            f"{s}: {len(sw)}/{len(st)} wins "
            f"({len(sw)/len(st)*100:.0f}%)"
        )

    if len(fechados) < 50:
        linhas.append(f"\n⚠️ Mínimo 50 trades para análise definitiva ({len(fechados)}/50)")

    return "\n".join(linhas)
