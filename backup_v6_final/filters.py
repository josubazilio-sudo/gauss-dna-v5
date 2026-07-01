"""SINAIS TOP V9.1 — Filtros e Bloqueios Institucionais"""

def check_alignment(trend_data, momentum_data, flow_data, kalman_dir, direction, adx):
    """
    Validação obrigatória de alinhamento.
    Retorna (True, None) se ok, (False, "MOTIVO") se bloqueado.
    """
    # 1. ADX (Força)
    if adx < 18:
        return False, "BLOQUEADO: ADX insuficiente"

    # Tendência neutra/lateral e Kalman contra são avaliados no score.
    # Eles não devem bloquear sozinhos um setup institucional com liquidez.

    # 2. Fluxo (Divergência)
    delta = flow_data.get("DELTA", 0)
    if (direction == "long" and delta < -0.05) or (direction == "short" and delta > 0.05):
        return False, "BLOQUEADO: Fluxo divergente"

    return True, None

def run_all(symbol, direction, trend_data, flow_data, momentum_data,
            smc_data, market_data, candles, kalman_dir,
            volume_24h=None, spread=None):
    
    motivos = []
    
    # Validar Liquidez
    if volume_24h is not None and volume_24h < 2_000_000:
        motivos.append("volume_muito_baixo")
        
    # Validar Alinhamento Institucional (Regras V9.1)
    adx = momentum_data.get("ADX", 0)
    ok, block_msg = check_alignment(trend_data, momentum_data, flow_data, kalman_dir, direction, adx)
    if not ok:
        motivos.append(block_msg)
        
    aprovado = len(motivos) == 0
    return aprovado, motivos, 0, 0
