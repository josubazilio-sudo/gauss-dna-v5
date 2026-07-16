# Baseline - QuantOS V17.1

Data: 2026-07-11

## Baseline Anterior
- Health validado: 100 em ciclos recentes.
- Bugs: 0 nos ciclos recentes.
- Silent drops: 0 nos ciclos recentes.
- Sinais aprovados: 0.
- Causa principal: thresholds acima da escala real e `PRONTO` sempre rejeitado.

## Baseline Nova
- Validacao real MEXC aprovou 1 sinal: `67USDT 4h short`.
- Hard gates: aprovados.
- Self-audit: aprovado.
- Consensus: `0.86`.
- Quality: `0.5415`.
- Entry score: `0.566`.
- Risk: `0.0952`.
- RR: `2.0`.

## Metricas Pendentes
- Win Rate, Profit Factor, Drawdown, Expectancy, Sharpe, Sortino e Recovery Factor dependem de paper trading apos abertura/fechamento de trades.

## Baseline V25 (2026-07-14) — Hard Gate Financeiro
- Hard gates: `QUANTOS_ACCOUNT_SIZE` e `QUANTOS_LEVERAGE_MAX` agora aplicados de
  ponta a ponta (saldo em paper trading, alavancagem no calculo, e validacao no
  Math Auditor). Antes eram apenas configuracoes de documentacao sem enforcement
  real.
- Novo Hard Gate Estrutural: conflito MTF isolado reprova sempre (antes exigia
  tambem `structural_score < 0.60`).
- Novos hard gates financeiros: `MarginWithinCapital` (margem <= capital) e
  `LeverageWithinLimit` (alavancagem <= maxima), dentro do Math Auditor (V21).
- Ver `RFC_V25_HARD_GATE_FINANCEIRO.md`.

## Baseline V25.4 (2026-07-15) — Correcao do Filtro de Exaustao
- Bug de escala corrigido em `compute_exaustao()` (velas_alongadas_consecutivas
  disparava em ~100% dos casos por comparar % com fracao). Taxa de rejeicao por
  Exaustao caiu de 71.7% para 19.7% do total de candidatos analisados (dados
  reais, mesmo dia, antes/depois do deploy).
- Nenhum threshold ou peso do filtro foi alterado - apenas a escala da
  comparacao interna.
- Ver `RFC_V25_4_FIX_ESCALA_EXAUSTAO.md`.

## Baseline V25.5 (2026-07-15) — Diagnostico Rapido Inteligente
- Diagnostico ao final de cada ciclo (saudavel SIM/NAO, mercado, top 5
  motivos, gargalos, deteccao de bug vs media historica, alerta imediato
  ao Telegram). Nao recalcula indicadores, nao altera nenhum threshold.
- Validado em producao real (local + VPS): primeiro ciclo pos-deploy
  mostrou corretamente Consenso 50%/Scanner 37%/Exaustao 14% como top
  motivos e 2 gargalos identificados.
- Ver `RFC_V25_5_FAST_DIAGNOSTIC.md`.
