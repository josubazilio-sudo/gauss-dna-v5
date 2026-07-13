# RFC V19.1 — CONSOLIDAÇÃO FINAL PARA PRODUÇÃO

Data: 2026-07-12

## Objetivo

Eliminar inconsistências identificadas no Paper Trading V19.0: classificação
divergente entre Índice Geral e tier, sinais duplicados, conflito entre timeframes,
expectativa subestimada, penalizações genéricas, e ausência de confluência.

## Problemas e Soluções

### P1 — Classificação Inconsistente
**Causa Raiz:** `operational.py:compute_overall_score()` copia `classification_label`
do scanner (baseado em `quality_score`) em vez de derivar do `overall_score`.
**Solução:** Após calcular `overall_score`, derivar `overall_tier` usando
`CLASSIFICATION_RANGES` (tabela fixa 60/70/80/90). Se houver divergência entre
`classification_label` original e o tier derivado, logar aviso.

### P2 — Anti-Duplicate Engine
**Causa Raiz:** `signal_tracker.py` já existe mas permite reenvio quando score
ou consenso mudam. Sinais muito similares passam.
**Solução:** Cache por hash do setup (ativo+timeframe+direção+entrada+TP+stop).
Bloquear reenvio a menos que: mudança estrutural, novo entry/stop/TP,
score mudou >10%, tendência mudou, consenso mudou >15%. Registrar motivo.

### P3 — Multi-Timeframe Consensus
**Causa:** Sinais de timeframes diferentes podem ter direções opostas.
**Solução:** No DecisionEngine, verificar se há conflito entre timeframes
do mesmo ativo. Se 4H=LONG e 1H=SHORT: reduzir confidence_score,
adicionar penalização "Conflito entre Timeframes", ou bloquear.
Exibir no Telegram quando existir divergência.

### P4 — Expectativa Recalibrada
**Causa:** Setups fortes classificados como Expectativa Baixa.
**Solução:** 5 níveis (Muito Baixa, Baixa, Moderada, Alta, Muito Alta).
Adicionar Multi-Timeframe e RVOL aos fatores. Ajustar thresholds.

### P5 — Penalizações Detalhadas
**Causa:** "Risco Elevado (63%)" genérico.
**Solução:** Cada penalização mostra motivo, peso, impacto negativo no score.
Formato: "Mercado lateral (-6)", "Estrutura fraca (-8)", etc.

### P6 — Índice Geral
**Solução:** Auditoria da fórmula. Manter pesos atuais (V19.0) que já estão
corretos. Garantir que overall_tier é derivado do overall_score.

### P7 — Score de Confluência (0-100)
**Solução:** Novo indicador medindo concordância entre: Trend, Kalman,
Estrutura, Momentum, Liquidez, Volume, Consenso, Fluxo.
Quanto maior, maior a confiabilidade.

### P8 — Decomposição do Risco
**Solução:** Mostrar Risco Estrutural, Tendência, Volatilidade, Liquidez,
Estatístico, Total.

### P9 — Motivo Principal
**Solução:** Resumo automático do motivo de aprovação:
"BOS confirmado + Liquidez institucional + Fluxo dominante"

### P10 — Paper Trading por Classificação
**Solução:** Já implementado em V19.0. Verificar e expandir.

### P11 — Autoaprendizado Rigoroso
**Solução:** Só recalibrar se: >=100 trades, PF>=1.5, WR>=50%, Expectancy>0,
Drawdown<30%, distribuição LONG/SHORT equilibrada.

### P12 — Telegram
**Solução:** Adicionar Confluência, Risco Total, Motivo Principal,
Conflito Multi-Timeframe. Remover redundâncias.

## Arquivos Afetados

### Modificar
- `ENGINE/common/operational.py` — P1, P4, P5, P6, P7, P8
- `ENGINE/scanner/scanner_config.py` — P4, P7
- `ENGINE/decision/decision_engine.py` — P3
- `ENGINE/scanner/scanner_engine.py` — P3
- `ENGINE/signals/signal_tracker.py` — P2
- `ENGINE/common/trade_registry.py` — P2
- `ENGINE/scanner/auto_calibration.py` — P11
- `CORE/trading/paper_trading.py` — P10
- `SERVICES/telegram/telegram_formatter.py` — P12
- `main.py` — P1, P2, P3, P9

## Riscos

1. Anti-Duplicate Engine pode bloquear reenvios legítimos de atualizações.
2. Conflito Multi-Timeframe pode rejeitar operações em ativos voláteis.
3. Score de Confluência pode adicionar complexidade desnecessária.
4. Rollback: git revert por commit individual.

## Critérios de Aceitação

1. overall_tier sempre deriva do overall_score (nunca copia classification_label)
2. Sinais duplicados são bloqueados com motivo registrado
3. Conflito entre timeframes é detectado e exibido
4. Expectativa usa 5 níveis com thresholds calibrados
5. Penalizações mostram motivo, peso e impacto numérico
6. Score de Confluência 0-100 disponível
7. Risco decomposto em 5 componentes
8. Motivo Principal gerado automaticamente
9. 100% dos testes existentes passam
