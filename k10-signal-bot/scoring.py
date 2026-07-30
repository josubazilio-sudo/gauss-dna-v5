"""
K10 Scoring Engine v45.0
Pesos: Estrutura 40% | Timing 20% | Institucional 15% | Liquidez 10%
       Momentum 5% | Volatilidade 5% | Risco 5%
Penalizações, Bônus e regras Diamante
"""


def calcular_score(data: dict) -> dict:
    """
    data: dict com todos os valores do engine
    Retorna: score_final, tier, detalhes
    """

    # ── Componentes base (0–100 cada) ─────────────────────────────────────────
    estrutura   = _score_estrutura(data)
    timing      = _score_timing(data)
    institucional = _score_institucional(data)
    liquidez    = _score_liquidez(data)
    momentum    = _score_momentum(data)
    volatilidade= _score_volatilidade(data)
    risco       = _score_risco(data)

    # ── Score ponderado ───────────────────────────────────────────────────────
    score_base = round(
        estrutura    * 0.40 +
        timing       * 0.20 +
        institucional* 0.15 +
        liquidez     * 0.10 +
        momentum     * 0.05 +
        volatilidade * 0.05 +
        risco        * 0.05
    )

    # ── Penalizações ──────────────────────────────────────────────────────────
    penais  = []
    pen_tot = 0

    tend_4h = data.get("tend_4h", "NEUTRA")
    tend_1d = data.get("tend_1d", "NEUTRA")
    direcao = data.get("direcao", "LONG")

    if direcao == "LONG":
        contra_4h = tend_4h == "BAIXA"
        contra_1d = tend_1d == "BAIXA"
    else:
        contra_4h = tend_4h == "ALTA"
        contra_1d = tend_1d == "ALTA"

    if contra_4h:
        penais.append(("Contra tendência H4", -10))
        pen_tot -= 10
    if contra_1d:
        penais.append(("Contra tendência Diário", -15))
        pen_tot -= 15

    atr_cons = data.get("atr_consumido", 0)
    if atr_cons > 50:
        penais.append((f"ATR Consumido {atr_cons}% > 50%", -5))
        pen_tot -= 5

    dist_ema = data.get("dist_ema21_atr", 0)
    if dist_ema > 2:
        penais.append((f"Dist EMA21 {dist_ema} ATR > 2", -5))
        pen_tot -= 5

    adx = data.get("adx", 0)
    if adx < 20:
        penais.append((f"ADX {adx:.1f} < 20", -5))
        pen_tot -= 5

    if data.get("liquidez_status") == "BAIXA":
        penais.append(("Liquidez baixa", -5))
        pen_tot -= 5

    if data.get("kalman") == "INDEFINIDO":
        penais.append(("Kalman indefinido", -5))
        pen_tot -= 5

    if data.get("cruzamento_antigo", False):
        penais.append(("Cruzamento antigo", -8))
        pen_tot -= 8

    # ── Bônus ─────────────────────────────────────────────────────────────────
    bonus   = []
    bon_tot = 0
    confs   = data.get("confirmacoes", [])

    bonus_map = {
        "CHoCH confirmado":      ("CHoCH confirmado",     +5),
        "BOS confirmado":        ("BOS confirmado",       +5),
        "Pullback EMA21":        ("Pullback saudável",    +5),
        "Volume institucional":  ("Volume institucional", +5),
        "Sweep de Liquidez":     ("Liquidity Sweep",      +5),
        "Order Block institucional": ("Order Block válido",+5),
        "Fair Value Gap":        ("FVG válido",           +5),
        "MTF H4/D1":             ("Alinhamento MTF",      +5),
    }
    for conf in confs:
        if conf in bonus_map:
            label, val = bonus_map[conf]
            bonus.append((label, val))
            bon_tot += val

    # ── Score final ───────────────────────────────────────────────────────────
    score_final = max(0, min(100, score_base + pen_tot + bon_tot))

    # ── Tier ──────────────────────────────────────────────────────────────────
    tier, aprovado = _classificar(score_final, data)

    # Se não passou no gate do Diamante, limita a Ouro
    if score_final >= 90 and tier != "DIAMANTE":
        score_final = min(score_final, 89)
        tier = "OURO"

    # Reclassificar após possível ajuste
    tier, aprovado = _classificar(score_final, data)

    return {
        "score_final":    score_final,
        "score_base":     score_base,
        "tier":           tier,
        "aprovado":       aprovado,
        "penalizacoes":   penais,
        "bonus":          bonus,
        "pen_total":      pen_tot,
        "bon_total":      bon_tot,
        "componentes": {
            "Estrutura":    estrutura,
            "Timing":       timing,
            "Institucional":institucional,
            "Liquidez":     liquidez,
            "Momentum":     momentum,
            "Volatilidade": volatilidade,
            "Risco":        risco,
        }
    }


# ── Regras Diamante ───────────────────────────────────────────────────────────
def _gate_diamante(data: dict) -> bool:
    confs    = data.get("confirmacoes", [])
    timing   = data.get("timing_score", 0)
    inst     = data.get("institucional_score", 0)
    liquidez = data.get("liquidez_score", 0)
    adx      = data.get("adx", 0)
    atr_cons = data.get("atr_consumido", 100)
    dist_ema = data.get("dist_ema21_atr", 99)
    mtf_ok   = data.get("mtf_ok", False)

    reqs = [
        timing   >= 85,
        inst     >= 85,
        liquidez >= 80,
        adx      >= 25,
        atr_cons <= 35,
        dist_ema <= 1.0,
        mtf_ok,
        any("CHoCH" in c or "BOS" in c for c in confs),
        any("Order Block" in c for c in confs),
        any("FVG" in c or "Fair Value" in c for c in confs),
        any("Sweep" in c or "Liquidez" in c for c in confs),
    ]
    return all(reqs)


def _classificar(score: int, data: dict) -> tuple:
    if score < 70:
        return "REJEITADO", False
    elif score <= 74:
        return "BRONZE", True
    elif score <= 79:
        return "PRATA", True
    elif score <= 89:
        return "OURO", True
    else:
        if _gate_diamante(data):
            return "DIAMANTE", True
        return "OURO", True   # não passou no gate — limita a Ouro


# ── Componentes individuais ───────────────────────────────────────────────────
def _score_estrutura(d: dict) -> int:
    confs = d.get("confirmacoes", [])
    pts   = 0
    if any("BOS" in c for c in confs):     pts += 25
    if any("CHoCH" in c for c in confs):   pts += 25
    if any("Order Block" in c for c in confs): pts += 20
    if any("FVG" in c or "Fair Value" in c for c in confs): pts += 15
    if any("Pullback" in c for c in confs): pts += 15
    return min(pts, 100)

def _score_timing(d: dict) -> int:
    adx      = d.get("adx", 0)
    rsi      = d.get("rsi", 50)
    atr_cons = d.get("atr_consumido", 100)
    dist_ema = d.get("dist_ema21_atr", 5)
    pts = 0
    pts += min(adx, 50)                          # ADX contribui até 50 pts
    pts += max(0, 25 - abs(rsi - 50) * 0.5)      # RSI próximo ao ideal
    pts += max(0, 25 - atr_cons * 0.5)           # ATR pouco consumido
    return min(round(pts), 100)

def _score_institucional(d: dict) -> int:
    confs = d.get("confirmacoes", [])
    pts   = 0
    if any("Sweep" in c or "Liquidez" in c for c in confs): pts += 35
    if any("Volume" in c for c in confs):  pts += 30
    if any("Order Block" in c for c in confs): pts += 20
    if d.get("kalman") in ("UP", "DOWN"):  pts += 15
    return min(pts, 100)

def _score_liquidez(d: dict) -> int:
    rvol = d.get("rvol", 0)
    confs = d.get("confirmacoes", [])
    pts  = min(round(rvol * 40), 70)
    if any("Sweep" in c for c in confs): pts += 30
    return min(pts, 100)

def _score_momentum(d: dict) -> int:
    rsi  = d.get("rsi", 50)
    direcao = d.get("direcao", "LONG")
    macd_hist = d.get("macd_hist", 0)
    pts = 0
    if direcao == "LONG":
        pts += max(0, (rsi - 30) / 40 * 50) if rsi <= 70 else 0
    else:
        pts += max(0, (70 - rsi) / 40 * 50) if rsi >= 30 else 0
    pts += 50 if (macd_hist > 0 and direcao == "LONG") or (macd_hist < 0 and direcao == "SHORT") else 0
    return min(round(pts), 100)

def _score_volatilidade(d: dict) -> int:
    atr_pct = d.get("atr_pct", 0)
    # Ideal: ATR entre 0.5% e 3%
    if 0.5 <= atr_pct <= 3.0:  return 100
    elif atr_pct < 0.5:        return 60
    elif atr_pct <= 5.0:       return 70
    else:                      return 40

def _score_risco(d: dict) -> int:
    rr = d.get("rr", 0)
    if rr >= 3.0:   return 100
    elif rr >= 2.5: return 85
    elif rr >= 2.0: return 70
    elif rr >= 1.5: return 50
    return 20


# ── Helpers para o formatter ──────────────────────────────────────────────────
TIER_EMOJI = {
    "DIAMANTE": "💎",
    "OURO":     "🥇",
    "PRATA":    "🥈",
    "BRONZE":   "🥉",
    "REJEITADO":"❌",
}

TIER_RANK = {
    "DIAMANTE": "💎 INSTITUCIONAL — MELHOR DO CICLO",
    "OURO":     "🥇 #1 DO CICLO",
    "PRATA":    "🥈 TOP DO CICLO",
    "BRONZE":   "🥉 SINAL CONFIRMADO",
}
