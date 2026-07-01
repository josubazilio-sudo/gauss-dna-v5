# GAUSS DNA V5 INFINITY

Sistema institucional de trading automático para MEXC (300+ criptomoedas).

## Skills
- **dna-flex-architect** — CQO / Arquiteto Quant. Carregar SEMPRE ao ajustar parâmetros, score, filtros, classificação, gestão de risco, ou qualquer alteração na estratégia.

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

## SINAIS TOP

Scanner institucional com pesos revisados para ~300 moedas MEXC.

```
src/flex/
├── main.py          # Entry point
├── config.py        # Constantes FLEX (pesos, thresholds, bandas)
├── kalman.py        # Filtro Kalman 1D (UP/DOWN/SIDE)
├── score.py         # Score Fluxo 25% + Tendência 20% + RVOL 15% + ADX 10% + Liquidez 10% + Momentum 10% + Kalman 5% + RSI 5%
├── filters.py       # Filtros RVOL/ADX/RSI/Liquidez/Kalman/Tendência/Fluxo/Volatilidade/Funding/Velas Fortes
├── cycle.py         # Orquestrador: scan 300 moedas → filtra → score → classifica → notifica
└── notify.py        # Sinal formatado + Diagnóstico Avançado
```

### Score FLEX (0-100)
- **Fluxo Institucional**: 25pts — Muito Forte/Forte/Moderado/Fraco
- **Tendência**: 20pts — Alta/Baixa alinhada > moderada > neutra
- **RVOL**: 15pts — Bandas: reprovado/neutro/bom/muito_bom/excelente
- **ADX**: 10pts — Bandas: reprovado/neutro/bom/muito_bom/excelente
- **Liquidez**: 10pts — SMC + spread + volume 24h
- **Momentum**: 10pts — Crescente/Decrescente + HA + velas fortes
- **Kalman**: 5pts — Alinhado = cheio, contra = 0
- **RSI**: 5pts — Ideal/Aceitável/Evitar por direção

### Classificação
- 🥇 **OURO**: 85-100 (EXCELENTE)
- 🥈 **PRATA**: 70-84 (MUITO BOA)
- 🥉 **BRONZE**: 55-69 (BOA)
- Abaixo de 55: descartado (não gera sinal)

### Executar
```bash
python -m src.flex.main
```

### Regra
Sempre rodar `python -m src.flex.main` após qualquer ajuste nos arquivos `src/flex/` para validar que compila e o ciclo executa sem erros.

## Repositórios

- SINAIS TOP: scanner em `src/flex/`
- V5: `https://github.com/josubazilio-sudo/gauss-dna-v5`
- V3/V4: `https://github.com/josubazilio-sudo/gauss-dna`
