"""Módulo 4: Análise de Fluxo (Volume, RVOL, Delta)."""


def analyze_flow(candles):
    """
    Avalia fluxo comprador/vendedor.
    """
    result = {
        "rvol": 1.0,
        "volume_crescente": False,
        "absorcao": False,
        "exaustao": False,
        "fluxo_direcao": "neutro",
    }

    if not candles or len(candles) < 20:
        return result

    volumes = [c[5] for c in candles]
    closes = [c[4] for c in candles]
    vol_mean = sum(volumes[-20:]) / len(volumes[-20:])
    vol_current = volumes[-1]

    result["rvol"] = vol_current / vol_mean if vol_mean else 1.0

    recent = volumes[-5:]
    result["volume_crescente"] = all(recent[i] >= recent[i - 1] for i in range(1, len(recent)))

    delta = sum((c[4] - c[1]) * c[5] for c in candles[-5:])
    if abs(delta) > vol_mean * 2:
        result["absorcao"] = True

    vol_decreasing = all(recent[i] <= recent[i - 1] for i in range(1, len(recent)))
    if vol_decreasing and vol_current < vol_mean * 0.5:
        result["exaustao"] = True

    if delta > 0:
        result["fluxo_direcao"] = "comprador"
    elif delta < 0:
        result["fluxo_direcao"] = "vendedor"

    return result
