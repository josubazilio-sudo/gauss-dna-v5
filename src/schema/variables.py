"""
GAUSS DNA V5 INFINITY — Schema Oficial de Variáveis.

Todas as variáveis que o sistema produz/consome.
Cada módulo preenche seu subset e o result final
contém o dicionário completo padronizado.
"""

def empty_schema():
    return {
        # ── CONFIGURAÇÃO GERAL ──────────────────────────────────────
        "TIMEFRAME_OPERACAO": "",
        "TIMEFRAME_CONFIRMACAO": "",
        "TIMEFRAME_MACRO": "",
        "MAX_CRYPTOS": 0,
        "RISCO_POR_OPERACAO": 0.0,
        "RISCO_DIARIO": 0.0,
        "MAX_OPERACOES": 0,
        "MAX_OPERACOES_SIMULTANEAS": 0,
        "MODO_AUTOMATICO": False,
        "MODO_OURO": False,
        "MODO_PRATA": False,
        "MODO_BRONZE": False,

        # ── TENDÊNCIA ──────────────────────────────────────────────
        "EMA_10": None,
        "EMA_21": None,
        "EMA_50": None,
        "EMA_200": None,
        "EMA_ALINHADA": False,
        "EMA_CRUZAMENTO": "",
        "EMA_FORCA": "",
        "EMA_INCLINACAO": "",
        "TENDENCIA": "",
        "DIRECAO": "",

        # ── SMART MONEY ────────────────────────────────────────────
        "BOS": False,
        "CHOCH": False,
        "LIQUIDITY_SWEEP": False,
        "STOP_HUNT": False,
        "ORDER_BLOCK": False,
        "FVG": False,
        "MITIGACAO": False,
        "RETESTE": False,
        "ESTRUTURA_OK": False,

        # ── VOLUME ─────────────────────────────────────────────────
        "VOLUME": 0.0,
        "VOLUME_MEDIO": 0.0,
        "RVOL": 1.0,
        "RVOL_MINIMO": 1.0,
        "DELTA": 0.0,
        "DELTA_POSITIVO": False,
        "DELTA_NEGATIVO": False,
        "VOLUME_CRESCENTE": False,
        "ABSORCAO": False,
        "EXAUSTAO": False,

        # ── MOMENTUM ───────────────────────────────────────────────
        "RSI": 50.0,
        "RSI_LONG": False,
        "RSI_SHORT": False,
        "ADX": 0.0,
        "ADX_MINIMO": 20,
        "ATR": 0.0,
        "ATR_MEDIO": 0.0,
        "MOMENTUM": "",
        "HEIKIN_ASHI": "",
        "HA_BULL": False,
        "HA_BEAR": False,
        "MACD": None,
        "MACD_SIGNAL": None,
        "MACD_HIST": None,
        "MACD_BULLISH": False,
        "MACD_BEARISH": False,
        "MACD_HIST_CRESCENTE": False,

        # ── VOLATILIDADE ───────────────────────────────────────────
        "VOLATILIDADE": "",
        "VOL_ALTA": False,
        "VOL_BAIXA": False,
        "ATR_EXPANSAO": False,
        "ATR_COMPRESSAO": False,

        # ── FILTROS ────────────────────────────────────────────────
        "FILTRO_LATERAL": True,
        "FILTRO_VOLUME": True,
        "FILTRO_FLUXO": True,
        "FILTRO_TENDENCIA": True,
        "FILTRO_LIQUIDEZ": True,
        "FILTRO_MOMENTUM": True,
        "FILTRO_VOLATILIDADE": True,
        "FILTRO_NOTICIAS": False,
        "FILTRO_SPREAD": True,

        # ── ENTRADA LONG ───────────────────────────────────────────
        "LONG_PERMITIDO": False,
        "LONG_CONFIRMADO": False,
        "LONG_SCORE": 0,
        "LONG_ENTRADA": None,
        "LONG_STOP": None,
        "LONG_TAKE": None,
        "LONG_TRAILING": None,

        # ── ENTRADA SHORT ──────────────────────────────────────────
        "SHORT_PERMITIDO": False,
        "SHORT_CONFIRMADO": False,
        "SHORT_SCORE": 0,
        "SHORT_ENTRADA": None,
        "SHORT_STOP": None,
        "SHORT_TAKE": None,
        "SHORT_TRAILING": None,

        # ── GESTÃO ─────────────────────────────────────────────────
        "CAPITAL": 0.0,
        "SALDO": 0.0,
        "RISCO_ATUAL": 0.0,
        "DRAWDOWN": 0.0,
        "LUCRO_DIA": 0.0,
        "PREJUIZO_DIA": 0.0,
        "WINRATE": 0.0,
        "PROFIT_FACTOR": 0.0,
        "EXPECTANCIA": 0.0,
        "OPERACOES_HOJE": 0,

        # ── SCORE ──────────────────────────────────────────────────
        "SCORE_TENDENCIA": 0,
        "SCORE_VOLUME": 0,
        "SCORE_FLUXO": 0,
        "SCORE_MOMENTUM": 0,
        "SCORE_LIQUIDEZ": 0,
        "SCORE_ESTRUTURA": 0,
        "SCORE_VOLATILIDADE": 0,
        "SCORE_TOTAL": 0,

        # ── MULTI-TIMEFRAME ────────────────────────────────────────
        "MTF_15M_TENDENCIA": "",
        "MTF_1H_TENDENCIA": "",
        "MTF_4H_TENDENCIA": "",
        "MTF_15M_DIRECAO": "",
        "MTF_1H_DIRECAO": "",
        "MTF_4H_DIRECAO": "",
        "MTF_15M_SCORE": 0,
        "MTF_1H_SCORE": 0,
        "MTF_4H_SCORE": 0,
        "MTF_CONVERGENCIA": False,
        "MTF_BONUS": 0,

        # ── CLASSIFICAÇÃO ──────────────────────────────────────────
        "SINAL_OURO": False,
        "SINAL_PRATA": False,
        "SINAL_BRONZE": False,
        "NIVEL_CONFIANCA": 0,
        "QUALIDADE_SINAL": "",

        # ── DIAGNÓSTICO ────────────────────────────────────────────
        "MOTIVO_RECUSA": "",
        "MOTIVO_ENTRADA": "",
        "FILTROS_APROVADOS": [],
        "FILTROS_REPROVADOS": [],
        "ESTADO_MERCADO": "",
        "ULTIMO_SINAL": "",
        "TEMPO_SEM_SINAL": 0,
        "ULTIMO_RESULTADO": "",

        # ── IA ADAPTATIVA ──────────────────────────────────────────
        "PESO_TENDENCIA": 20,
        "PESO_FLUXO": 20,
        "PESO_VOLUME": 10,
        "PESO_LIQUIDEZ": 15,
        "PESO_ESTRUTURA": 20,
        "PESO_MOMENTUM": 10,
        "PESO_VOLATILIDADE": 5,
        "PESO_MULTI_TIMEFRAME": 5,
        "PESO_CONFIANCA": 10,
        "PESO_ATIVO": 5,

        # ── ESTATÍSTICAS POR MOEDA ─────────────────────────────────
        "SYMBOL": "",
        "OPERACOES_SYMBOL": 0,
        "WINRATE_SYMBOL": 0.0,
        "PF_SYMBOL": 0.0,
        "DRAWDOWN_SYMBOL": 0.0,
        "VOLATILIDADE_SYMBOL": 0.0,
        "RVOL_SYMBOL": 1.0,
        "ATR_SYMBOL": 0.0,
        "HORARIO_MELHOR": "",
        "HORARIO_PIOR": "",
        "SCORE_SYMBOL": 0,

        # ── SEGURANÇA ──────────────────────────────────────────────
        "PARAR_OPERACOES": False,
        "MODO_PROTECAO": False,
        "STOP_CONSECUTIVO": 0,
        "LIMITE_STOPS": 3,
        "LIMITE_LOSS": 0.0,
        "LIMITE_GAIN": 0.0,
        "CIRCUIT_BREAKER": False,
        "MERCADO_PERIGOSO": False,

        # ── FLUXO / KALMAN ──────────────────────────────────────────
        "FLUXO_TIPO": "",
        "KALMAN_DIRECAO": "",
        "FUNDING_RATE": None,

        # ── DECISÃO FINAL ──────────────────────────────────────────
        "OPERAR": False,
        "IGNORAR": False,
        "MOTIVO": "",
        "CONFIANCA": 0,
        "QUALIDADE": "",
        "CLASSIFICACAO_FINAL": "",
        "EXECUTAR_ORDEM": False,
    }
