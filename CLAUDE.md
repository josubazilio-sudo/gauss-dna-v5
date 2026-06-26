# GAUSS DNA V5 INFINITY

Sistema institucional de trading automático para MEXC (300+ criptomoedas).

## Arquitetura

```
src/
├── main.py              # Entry point
├── config.py            # Constantes e variáveis de ambiente
├── cycles.py            # Orquestrador principal
├── market.py            # Módulo 1: Classificação do mercado + VOLATILIDADE
├── trend.py             # Módulo 2: Tendência (EMA_10/21/50/200)
├── smart_money.py       # Módulo 3: SMC (BOS, CHOCH, FVG, OB, sweep)
├── flow.py              # Módulo 4: Fluxo (VOLUME, RVOL, DELTA)
├── momentum.py          # Módulo 5: Momentum (RSI, ADX, ATR, HA)
├── score.py             # Score institucional e classificação
├── filters.py           # Filtros e bloqueios
├── risk.py              # Gestão de risco
├── diagnostics.py       # Diagnóstico e logging
├── adaptive.py          # IA adaptativa (pesos dinâmicos por ativo)
├── notify.py            # Notificações Telegram
├── schema/
│   ├── __init__.py
│   └── variables.py     # Schema oficial de variáveis padronizadas
└── modules/
    ├── __init__.py
    ├── indicators.py    # Cálculos técnicos
    └── scanner.py       # Scanner MEXC
```

## Schema Oficial de Variáveis

Todas as variáveis seguem o padrão definido em `schema/variables.py`.
Cada módulo preenche seu subset e o dict final contém todas as chaves.

### Grupos de variáveis:
- **CONFIGURAÇÃO GERAL**: TIMEFRAME_OPERACAO, MAX_CRYPTOS, RISCO_POR_OPERACAO, MODO_*
- **TENDÊNCIA**: EMA_10/21/50/200, EMA_ALINHADA, TENDENCIA, DIRECAO
- **SMART MONEY**: BOS, CHOCH, LIQUIDITY_SWEEP, FVG, ORDER_BLOCK, ESTRUTURA_OK
- **VOLUME**: VOLUME, RVOL, DELTA, VOLUME_CRESCENTE, ABSORCAO, EXAUSTAO
- **MOMENTUM**: RSI, ADX, ATR, HEIKIN_ASHI, HA_BULL/BEAR
- **VOLATILIDADE**: VOL_ALTA, VOL_BAIXA, ATR_EXPANSAO, ATR_COMPRESSAO
- **FILTROS**: FILTRO_LATERAL, FILTRO_VOLUME, FILTRO_FLUXO, FILTRO_TENDENCIA, etc.
- **ENTRADA**: LONG_*/SHORT_* (PERMITIDO, CONFIRMADO, SCORE, STOP, TAKE)
- **GESTÃO**: CAPITAL, SALDO, WINRATE, PROFIT_FACTOR, EXPECTANCIA
- **SCORE**: SCORE_TENDENCIA, SCORE_VOLUME, SCORE_TOTAL
- **CLASSIFICAÇÃO**: SINAL_OURO/PRATA/BRONZE, NIVEL_CONFIANCA
- **DIAGNÓSTICO**: MOTIVO_RECUSA, FILTROS_APROVADOS/REPROVADOS
- **IA ADAPTATIVA**: PESO_TENDENCIA, PESO_FLUXO, PESO_VOLUME, PESO_ATIVO
- **ESTATÍSTICAS**: SYMBOL, WINRATE_SYMBOL, RVOL_SYMBOL, SCORE_SYMBOL
- **SEGURANÇA**: PARAR_OPERACOES, CIRCUIT_BREAKER, MERCADO_PERIGOSO
- **DECISÃO FINAL**: OPERAR, IGNORAR, MOTIVO, CLASSIFICACAO_FINAL, EXECUTAR_ORDEM

## Comportamento

- Score ≥ 90 = OURO | 75-89 = PRATA | 50-74 = BRONZE
- Mercado lateral + ATR comprimido bloqueiam entradas
- IA adaptativa ajusta pesos por ativo baseado em winrate histórico
- Sinais enviados para o mesmo Telegram do bot V3/V4

## Repositórios

- V5: `https://github.com/josubazilio-sudo/gauss-dna-v5`
- V3/V4: `https://github.com/josubazilio-sudo/gauss-dna`
