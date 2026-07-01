"""Módulo de Auditoria de Integridade DNA FLEX - V7.0"""

def validar_coerencia_sinal(result):
    """
    Audita o sinal contra o perfil de risco e regime de mercado.
    Retorna (SinalAuditado, Modificado=True/False)
    """
    modificado = False
    classificacao = result.get("classificacao")
    score = result.get("score", 0)
    conviccao = result.get("conviction_score", 0)
    rvol = result.get("rvol", 0)
    adx = result.get("adx", 0)
    regime = result.get("regime_data", {}).get("regime", "TRANSICAO")

    # Auditoria de Ouro/Diamante
    if classificacao in ["OURO", "OURO_SUPREMO"]:
        if rvol < 1.3 or adx < 25 or conviccao < 75:
            result["classificacao"] = "PRATA"
            result["emoji"] = "🥈"
            modificado = True

    # Auditoria de Prata
    if result["classificacao"] == "PRATA" and regime == "TRANSICAO":
        if conviccao < 60:
            result["classificacao"] = "BRONZE"
            result["emoji"] = "🥉"
            modificado = True

    # Trava de Segurança Final (Se o Score for baixo mas passou por erro de logica)
    if score < 65:
        return None, True # Rejeita sinal inconsistente
    
    return result, modificado
