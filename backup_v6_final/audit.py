def auditar_sinal(score, classificacao, conviccao, rvol, adx):
    # Aplica regras de coerência do Architect
    # 1. Cap RVOL
    if rvol < 1.10 and score > 85:
        score = 85
    
    # 2. Normalização de Probabilidade
    prob = min(50 + score // 2, 95)
    if conviccao < 30: prob = min(prob, 70)
    elif conviccao < 50: prob = min(prob, 78)
    elif conviccao < 70: prob = min(prob, 85)
    
    return score, prob
