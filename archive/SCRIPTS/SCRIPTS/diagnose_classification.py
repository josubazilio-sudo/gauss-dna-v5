"""Diagnóstico da distribuição de classificação dos sinais.

Analisa os thresholds atuais, simula scores típicos,
e mostra se existe compressão da classificação.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ENGINE.scanner.scanner_config import QUALITY_TIERS, SCORE_WEIGHTS_DEFAULT, QUALITY_GATE_MIN_SCORE
from ENGINE.scanner.scanner_scoring import (
    score_structural, score_market_from_context, score_momentum,
    score_liquidity, score_risk, score_confidence,
    score_institutional, compute_quality_score, classify_signal,
)
from ENGINE.scanner.scanner_scoring import ScannerScore


def simulate_classification(structural: float, market: float, momentum: float,
                            liquidity: float, risk: float, confidence: float,
                            institutional: float = None) -> str:
    if institutional is None:
        inst = score_institutional(structural, market, momentum, liquidity, risk, confidence)
    else:
        inst = institutional

    scores = ScannerScore(
        institutional_score=inst,
        structural_score=structural,
        market_score=market,
        momentum_score=momentum,
        liquidity_score=liquidity,
        risk_score=risk,
        confidence_score=confidence,
    )
    scores.quality_score = compute_quality_score(scores)
    cls = classify_signal(scores)
    return cls.value if hasattr(cls, 'value') else str(cls), round(scores.quality_score, 4)


def main():
    print("=" * 60)
    print("DIAGNÓSTICO DE CLASSIFICAÇÃO — QUANTOS")
    print("=" * 60)

    print(f"\nQUALITY_GATE_MIN_SCORE (DEBUG): {QUALITY_GATE_MIN_SCORE}")
    print(f"\nQUALITY_TIERS atuais:")
    for name, cfg in QUALITY_TIERS.items():
        print(f"  {name}: min_score = {cfg['min_score']}")

    print(f"\nSCORE_WEIGHTS (quality_score):")
    for k, v in SCORE_WEIGHTS_DEFAULT["quality_score"].items():
        print(f"  {k}: {v}")

    print(f"\n--- SIMULAÇÃO DE CLASSIFICAÇÃO ---")

    cenarios = [
        ("Sinal fraco (tudo baixo)", 0.20, 0.20, 0.20, 0.20, 0.20, 0.20),
        ("Médio-baixo (valores típicos)", 0.35, 0.35, 0.35, 0.35, 0.35, 0.35),
        ("Médio (mercado normal)", 0.45, 0.45, 0.45, 0.45, 0.45, 0.45),
        ("Médio-alto (boa confluência)", 0.55, 0.55, 0.55, 0.55, 0.55, 0.55),
        ("Alto (tendência forte + volume)", 0.70, 0.70, 0.70, 0.70, 0.70, 0.70),
        ("Muito alto (tudo excelente)", 0.85, 0.85, 0.85, 0.85, 0.85, 0.85),
        ("SMC forte + inst alto", 0.60, 0.50, 0.55, 0.60, 0.55, 0.65),
        ("Volume alto + tendência", 0.40, 0.65, 0.55, 0.70, 0.60, 0.50),
        ("Estrutura forte + fluxo", 0.75, 0.40, 0.35, 0.45, 0.40, 0.50),
        ("Mercado lateral (tudo mediano)", 0.30, 0.30, 0.30, 0.50, 0.50, 0.30),
    ]

    print(f"\n{'Cenário':<45} {'Classe':<15} {'Quality':<10}")
    print("-" * 70)

    for nome, s, m, mom, liq, r, c in cenarios:
        cls, qual = simulate_classification(s, m, mom, liq, r, c)
        print(f"{nome:<45} {cls:<15} {qual:<10.4f}")

    print(f"\n--- ANÁLISE DE COMPRESSÃO ---")

    print(f"\nA classe BRONZE cobre o range 40-59 (20 pontos).")
    print(f"PRATA cobre 60-69 (10 pontos).")
    print(f"OURO cobre 70-89 (20 pontos, mas DIAMANTE vira OURO).")
    print(f"OURO_SUPREMO cobre apenas 90-100 (10 pontos).")

    print(f"\nPara atingir PRATA (quality >= 0.60), os scores componentes")
    print(f"precisam estar em média acima de 0.60.")
    print(f"Isso requer condições de mercado EXCEPCIONAIS na prática.")

    print(f"\n--- RECOMENDAÇÃO ---")
    print(f"Se mais de 80% dos sinais forem BRONZE, baixar thresholds:")
    print(f"  PRATA: 60 -> 50")
    print(f"  OURO:  70 -> 60")
    print(f"  OURO_SUPREMO: 90 -> 80")
    print(f"Isso distribuiria melhor os sinais sem perder diferenciação.")


if __name__ == "__main__":
    main()
