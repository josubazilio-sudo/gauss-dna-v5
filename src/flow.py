"""Módulo 4: Análise de Fluxo — preenche variáveis VOLUME."""

from config import RVOL_MINIMO


def analyze_flow(candles):
    """
    Preenche VOLUME, VOLUME_MEDIO, RVOL, DELTA,
    DELTA_POSITIVO, DELTA_NEGATIVO, VOLUME_CRESCENTE,
    ABSORCAO, EXAUSTAO.
    """
    result = {
        "VOLUME": 0.0,
        "VOLUME_MEDIO": 0.0,
        "PRECO": 0.0,
        "RVOL": 1.0,
        "RVOL_MINIMO": RVOL_MINIMO,
        "DELTA": 0.0,
        "DELTA_POSITIVO": False,
        "DELTA_NEGATIVO": False,
        "VOLUME_CRESCENTE": False,
        "ABSORCAO": False,
        "EXAUSTAO": False,
    }

    if not candles or len(candles) < 20:
        return result

    volumes = [c[5] for c in candles]
    closes = [c[4] for c in candles]
    opens = [c[1] for c in candles]

    result["PRECO"] = closes[-1]
    result["VOLUME"] = volumes[-1]
    result["VOLUME_MEDIO"] = sum(volumes[-20:]) / 20

    result["RVOL"] = result["VOLUME"] / result["VOLUME_MEDIO"] if result["VOLUME_MEDIO"] else 1.0

    recent = volumes[-5:]
    result["VOLUME_CRESCENTE"] = all(recent[i] >= recent[i - 1] for i in range(1, len(recent)))

    # Delta: diferença entre compra e venda
    delta = sum((closes[i] - opens[i]) * volumes[i] for i in range(-5, 0))
    result["DELTA"] = delta
    result["DELTA_POSITIVO"] = delta > 0
    result["DELTA_NEGATIVO"] = delta < 0

    # Absorção: delta pequeno com volume alto = batalha
    if result["VOLUME"] > result["VOLUME_MEDIO"] * 2 and abs(delta) < volumes[-1] * 0.01:
        result["ABSORCAO"] = True

    # Exaustão: volume caindo consistentemente
    if all(volumes[-i] <= volumes[-i - 1] for i in range(1, min(4, len(volumes)))):
        if volumes[-1] < result["VOLUME_MEDIO"] * 0.5:
            result["EXAUSTAO"] = True

    return result
