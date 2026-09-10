"""
K12 — FILTRO DE MERCADO (RFC 29/08, Secao 11 "MODO OPERAVEL REAL")
====================================================================
Contexto geral de BTC (H1/H4) calculado UMA vez por ciclo, nao por symbol,
e repassado para modo_operavel.avaliar(sinal, contexto_mercado=...).

Escopo deliberadamente minimo: a RFC pede um filtro de mercado "antes de
qualquer sinal", mas o usuario tambem deixou claro (28-29/08) que quer um
bot OPERAVEL, nao regras que sufoquem sinal ("nao se apegue a quantidade
de amostra... quero um bot operavel nao regras"; "quero pelo menos 3
sinais por dia"). Por isso este filtro bloqueia SO em cenario objetivo e
raro -- volatilidade extrema do BTC (flash move) -- e nao tenta "adivinhar"
direcao geral de mercado para vetar LONG/SHORT em massa (isso ja e feito,
por simbolo, em _contexto_htf_fortemente_contra() dentro do modo_operavel).
"""

import logging

logger = logging.getLogger(__name__)

BTC_SYMBOL = "BTC/USDT:USDT"

# ATR14(1h) do BTC acima disso, em % do preco, indica candle/sequencia fora
# do padrao normal (flash crash/pump) -- mesma logica de "stop2 buffer" ja
# usada no motor, so que aplicada ao BTC como termometro do mercado geral.
ATR_PCT_EXTREMO = 4.0


def calcular_contexto_mercado(engine) -> dict:
    """Le BTC 1h uma vez (reaproveita engine._fetch/_calc do K10Engine ja
    instanciado -- mesma conexao ccxt, sem duplicar rate limit). Chamado
    1x por ciclo em runner.py, resultado repassado a todos os sinais do
    ciclo via modo_operavel.avaliar(sinal, contexto_mercado)."""
    try:
        df1h = engine._calc(engine._fetch(BTC_SYMBOL, "1h", limit=60))
    except Exception as e:
        logger.warning(f"FILTRO_MERCADO: falha ao buscar BTC 1h ({e}) -- filtro inerte neste ciclo")
        return {"ok": True, "motivo": "", "atr_pct": None}

    r = df1h.iloc[-1]
    atr_pct = round((r["atr"] / r["close"]) * 100, 2) if r["close"] else 0

    if atr_pct > ATR_PCT_EXTREMO:
        motivo = f"BTC em volatilidade extrema (ATR1h {atr_pct}% > {ATR_PCT_EXTREMO}%) -- mercado fora do padrao, sinais suspensos neste ciclo"
        logger.warning(f"FILTRO_MERCADO: {motivo}")
        return {"ok": False, "motivo": motivo, "atr_pct": atr_pct}

    return {"ok": True, "motivo": "", "atr_pct": atr_pct}
