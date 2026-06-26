"""Módulos 6, 7, 9: Filtros de Tendência, Volume e Bloqueios."""


def check_filters(trend, flow, momentum, side="long"):
    """
    Verifica filtros de tendência e volume.

    - Compra: preço > MM200, MM10 > MM21 > MM50 > MM200, fluxo comprador
    - Venda: inverso
    """
    trend_direction, _ = trend

    if side == "long":
        if trend_direction not in ("muito_forte", "forte"):
            return False
    else:
        if trend_direction not in ("muito_forte", "forte"):
            return False

    if flow.get("rvol", 0) < 1.2:
        return False

    if not flow.get("volume_crescente"):
        return False

    if momentum.get("adx", 0) < 20:
        return False

    return True


def check_blockers(trend, flow, smc, momentum, market_state):
    """
    Verifica bloqueios que cancelam qualquer entrada.

    Retorna lista de blockers ativos (vazia = sem bloqueios).
    """
    blockers = []

    if market_state == "lateral":
        blockers.append("mercado_lateral")

    rsi = momentum.get("rsi", 50)
    adx = momentum.get("adx", 0)
    rvol = flow.get("rvol", 0)

    if rvol < 0.8:
        blockers.append("volume_muito_baixo")

    if (rsi > 75 or rsi < 25) and not smc.get("bos"):
        blockers.append("rsi_extremo_sem_confirmacao")

    if adx < 15:
        blockers.append("adx_muito_baixo")

    if smc.get("sweep") and not smc.get("bos"):
        blockers.append("liquidez_nao_confirmada")

    if flow.get("exaustao"):
        blockers.append("fluxo_contrario")

    return blockers
