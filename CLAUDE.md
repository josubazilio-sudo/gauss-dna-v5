# GAUSS DNA V5 INFINITY

Sistema institucional de trading automático para MEXC (300+ criptomoedas).

## Arquitetura

```
src/
├── main.py              # Entry point
├── config.py            # Constantes e variáveis de ambiente
├── cycles.py            # Orquestrador principal (scan -> análise -> decisão)
├── state.py             # Persistência de estado e journal
├── market.py            # Módulo 1: Classificação do mercado
├── trend.py             # Módulo 2: Detecção de tendência (MM10/21/50/200)
├── smart_money.py       # Módulo 3: SMC (sweep, BOS, CHOCH, FVG, OB)
├── flow.py              # Módulo 4: Fluxo (volume, RVOL, delta)
├── momentum.py          # Módulo 5: Momentum (RSI, ADX, ATR, HA)
├── score.py             # Módulo 8: Score institucional e classificação
├── filters.py           # Módulos 6, 7, 9: Filtros e bloqueios
├── risk.py              # Gestão de risco
├── diagnostics.py       # Diagnóstico e logging
└── modules/
    ├── indicators.py    # Cálculos técnicos
    └── scanner.py       # Scanner MEXC
```

## Comportamento

- **Não prevê mercado** — reage apenas a consenso multi-fator
- **Sem consenso = sem operação**
- **Score ≥ 95 = OURO**, 85-94 = PRATA, 75-84 = BRONZE
- **Nunca operar abaixo de 75**
- **Mercado lateral bloqueia entradas**
- **Saída**: manter enquanto MM10/MM21 alinhadas + fluxo favorável + estrutura intacta

## Referências

- Repositório anterior (V3/V4): `https://github.com/josubazilio-sudo/gauss-dna.git`
- Local: `C:\Users\josue\Usersjosuegauss-dna`
