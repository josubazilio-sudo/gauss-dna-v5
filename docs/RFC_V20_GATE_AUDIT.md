# RFC V20.0 — AUDITORIA DOS GATES E CALIBRAÇÃO INTELIGENTE

- **Data**: 2026-07-13
- **Versão**: V18.4 → Proposta V20.0
- **Autor**: Auditoria Automática QuantOS
- **Status**: RFC — Nenhuma implementação realizada

---

## 1. ARQUIVOS ANALISADOS

| Componente | Arquivo |
|---|---|
| Scanner Config | `ENGINE/scanner/scanner_config.py` |
| Decision Engine | `ENGINE/decision/decision_engine.py` |
| Risk Manager | `ENGINE/risk/risk_manager.py` |
| Consensus Engine | `ENGINE/consensus/consensus_engine.py` |
| Confluence Engine | `ENGINE/confluence/confluence_engine.py` |
| Consistency Validator | `ENGINE/validation/consistency_validator.py` |
| Signal Cache | `ENGINE/deduplication/signal_cache.py` |
| Signal Tracker | `ENGINE/signals/signal_tracker.py` |
| Bot Config | `BOTS/mexc/bot_config.py` |
| Signal Validator | `BOTS/mexc/signals/signal_validator.py` |
| Active Signal Manager | `SERVICES/telegram/active_signal_manager.py` |
| Update Engine | `SERVICES/telegram/update_engine.py` |
| Telegram Service | `SERVICES/telegram/telegram_service.py` |
| Paper Trading | `CORE/trading/paper_trading.py` |
| Main Pipeline | `main.py` |
| Health Monitor | `CORE/health/health_monitor.py` |
| Watchdog | `ENGINE/watchdog/watchdog_integration.py` |

---

## 2. FUNIL COMPLETO — SINAIS POR GATE

Dados extraídos de 699.907 linhas de log (7 dias: 6–13 Jul 2026):

```
SCANNER (300 pairs/cycle)
  │
  ├─ RVOL < 0.70 ──────────────── 29.335 elim. (65,8%)
  │
  ├─ ADX < 25 ──────────────────── 1.297 elim. (2,9%)
  │
  ├─ Entry Zone < 0.40 ─────────── 5.675 elim. (12,7%)
  │
  ├─ Quality < 0.60 ──────────────── 959 elim. (2,2%)
  │
  ├─ Structure < 0.30 ────────────── 944 elim. (2,1%)
  │
  ├─ RR < 2.0 ────────────────────── 805 elim. (1,8%)
  │
  ├─ Confidence < 0.75 ───────────── 728 elim. (1,6%)
  │
  ├─ Consensus < 0.70 ────────────── 721 elim. (1,6%)
  │
  │   Decision Engine: 772 APROVADOS (1,7%)
  │
  ├─ Final Validation ──────────────── 2 elim. (CHZUSDT coherence/vote)
  ├─ SignalValidator REJEITADOS ─── 2.598 elim. (ver seção 3)
  ├─ Dedup/Self-Audit/Cache ──────── 252 elim.
  │
  Telegram: 708 enviados
```

### Observações críticas:

1. **RVOL domina 65,8% de todas as rejeições** — quando RVOL falha, todos os gates seguintes são short-circuitados (ADX, Structure, Entry Zone, etc. ficam `None`).
2. **Decision Engine x SignalValidator**: 772 passam no engine, apenas ~22 passam no bot validator. Diferença de ~35x.
3. **CHZUSDT** foi o único sinal barrado pela Final Validation (Coherence 56.2, Weighted Vote 63.2%).

---

## 3. RANKING DE REJEIÇÕES — RAZÕES AGRUPADAS

### Decision Engine (44.594 traços)

| Gate | Rejeições | % | Threshold Atual | Impacto |
|---|---|---|---|---|
| RVOL | 29.335 | 65,8% | 0,70 | **DOMINANTE** |
| Entry Zone | 5.675 | 12,7% | 0,40 | Alto |
| ADX | 1.297 | 2,9% | 25 | Moderado |
| Quality | 959 | 2,2% | 0,60 | Moderado |
| Structure | 944 | 2,1% | 0,30 | Moderado |
| RR | 805 | 1,8% | 2,0 | Moderado |
| Confidence | 728 | 1,6% | 0,75 | Baixo |
| Consensus | 721 | 1,6% | 0,70 | Baixo |
| BOS/CHOCH | 406 | 0,9% | ≥1 | Baixo |

### SignalValidator (2.598 rejeições)

| Motivo | Ocorrências | % |
|---|---|---|
| SCORE INST < 0,85 | 868 | 33,4% |
| RVOL não confirmado | 422 | 16,2% |
| ARMADILHA detectada | 422 | 16,2% |
| FALSO ROMPIMENTO | 422 | 16,2% |
| ESTRUTURA inválida | 422 | 16,2% |
| VOLUME abaixo média | 422 | 16,2% |
| RR < 2,0 | 224 | 8,6% |
| SCORE ESTRUT < 0,80 | 213 | 8,2% |
| QUALIDADE < 85% | 213 | 8,2% |
| ABSORÇÃO detectada | 213 | 8,2% |
| REJEIÇÃO pavio excessivo | 213 | 8,2% |
| CONFIANÇA < 85% | 147 | 5,7% |

### Final Validation

| Motivo | Ocorrências |
|---|---|
| Coherence Score < 60 | 2 |
| Weighted Vote < 70% | 2 |

---

## 4. MATRIZ DE CORRELAÇÃO

### Pares de falhas no Decision Engine

| Combinação | % | Interpretação |
|---|---|---|
| **RVOL sozinho** | 64,1% | RVOL falha e curto-circuita todos os outros |
| **RVOL + ADX** | 0,3% | Raro — ADX quase nunca é avaliado quando RVOL falha |
| **ADX sozinho** | 2,6% | RVOL passou, ADX falhou |
| **Entry Zone sozinha** | 10,1% | RVOL+ADX passaram, Entry Zone barrou |
| **Quality + Confidence** | 0,8% | Ambos falham juntos em ~40% dos casos de falha individual |
| **RR + Quality** | 0,5% | Correlação baixa |
| **Quality + Entry Zone** | 1,2% | Correlação moderada |
| **Consensus + Confidence** | 0,6% | Correlação baixa |

### Conclusão da Matriz

- **RVOL é o gate isolado dominante** — responde sozinho por ~64% das rejeições.
- **Sem correlação forte entre pares de gates** — cada gate elimina um conjunto diferente de sinais.
- **A pilha é sequencial e independente**: cada gate filtra um aspecto diferente. Não há redundância significativa no Decision Engine.

### Conflitos no SignalValidator

| Combinação | % dos REJEITADOS |
|---|---|
| RVOL + FALSO ROMPIMENTO + ARMADILHA + ESTRUTURA + VOLUME | 16,2% |
| SCORE INST sozinho | 33,4% |
| SCORE INST + QUALIDADE + CONFIANÇA + SCORE ESTRUT | 5,7% |

---

## 5. DUPLICIDADE E CONFLITOS ENTRE GATES

### Duplicações Críticas Identificadas

| Gate #1 | Gate #2 | Threshold 1 | Threshold 2 | Diferença |
|---|---|---|---|---|
| Engine: Quality (Gate 7) | Bot: Quality (Check 14) | 0,60 | 0,85 | **+0,25** |
| Engine: Confidence (Gate 9) | Bot: Confidence (Check 13) | 0,75 | 0,85 | **+0,10** |
| Engine: Structure (Gate 5) | Bot: SCORE ESTRUT (Check 16) | 0,30 | 0,80 | **+0,50** |
| Engine: Institutional (V17) | Bot: SCORE INST (Check 15) | 0,45 | 0,85 | **+0,40** |
| Engine: RR (Gate 8b) | Bot: RR (Check 12) | 2,0 | 2,0 | **0 (mesmo)** |
| Engine: Weighted Vote (Gate 14) | Main: Final Validation | 70% | 70% | **0 (mesmo)** |
| Engine: Kalman (Gate 12) | Main: Final Validation | conflito | conflito | **0 (mesmo)** |
| Engine: Contra-tendência (Gate 15) | Engine: Final Validation (Gate 16) | reversão | reversão | **0 (mesmo)** |

### Problema principal: **Barreira dupla com thresholds diferentes**

O sistema tem **DUAS camadas independentes** de validação com thresholds drasticamente diferentes:

```
Decision Engine (mais permissivo)
  quality ≥ 0.60 ✓
  confidence ≥ 0.75 ✓
  structure ≥ 0.30 ✓
  institutional ≥ 0.45 ✓
  → APROVADO (772 sinais)

SignalValidator (muito mais restritivo)
  quality ≥ 0.85 ❌ (média dos aprovados: ~0,73)
  confidence ≥ 0.85 ❌ (média dos aprovados: ~0,74)
  structure ≥ 0.80 ❌
  institutional ≥ 0.85 ❌
  → REJEITADO (2.598 de 2.620)
```

### Conflitos e redundâncias

| Tipo | Detalhe | Severidade |
|---|---|---|
| **Duplicado** | Volume acima média repetido 2x no mesmo SignalValidator | Média |
| **Duplicado** | Kalman Gate (Engine Gate 12 + Engine Gate 16 + Main Final Validation = 3x) | Alta |
| **Duplicado** | Weighted Vote (Engine Gate 14 + Main Final Validation) | Média |
| **Duplicado** | Contra-tendência (Engine Gate 15 + Engine Gate 16) | Média |
| **Conflito** | Consistency Validator checa `flow_ok`/`timing_ok` que não são mais definidos no V18.4 | Alta |
| **Conflito** | Telegram Service revalida 8 gates já aprovados no Engine | Média |
| **Conflito** | Classification no engine (0-100) vs SignalValidator (0-1, thresholds diferentes) | Alta |

---

## 6. SCORE DE IMPACTO POR GATE

### Impacto Quantitativo (quantos sinais cada gate elimina)

| Gate | Eliminados | % Acumulado | Nota |
|---|---|---|---|
| RVOL (0,70) | 29.335 | 65,8% | Gate mais impactante |
| Entry Zone (0,40) | 5.675 | 78,5% | Segundo maior eliminador |
| ADX (25) | 1.297 | 81,4% | Impacto moderado |
| Quality (0,60) | 959 | 83,6% | Impacto moderado |
| Structure (0,30) | 944 | 85,7% | Impacto moderado |
| RR (2,0) | 805 | 87,5% | Impacto baixo |
| Confidence (0,75) | 728 | 89,1% | Impacto baixo |
| Consensus (0,70) | 721 | 90,8% | Impacto baixo |
| SignalValidator | 2.598 | 95,7% | Gargalo #2 |
| Final Validation | 2 | 95,7% | Quase irrelevante |

### Notas sobre Win Rate / Profit Factor

Não foi possível calcular Win Rate ou Profit Factor histórico por gate porque:
1. O sistema opera em **modo PAPER_TRADING** — não há trades reais com resultado fechado.
2. Sinais rejeitados não geram trades para comparar.
3. Para calcular impacto real seria necessário um **backtest comparativo** simulando cenários com e sem cada gate.

**Recomendação**: Implementar modo de backtest que registre o resultado hipotético de sinais que seriam rejeitados por cada gate.

---

## 7. SIMULADOR DE THRESHOLDS

### Cenário 1: Confidence 0,80 (atual: 0,75)

| Métrica | Estimativa |
|---|---|
| Sinais adicionais no Engine | ~180 (25%) |
| Que chegariam ao SignalValidator | ~5 (estimado) |
| Impacto no bot (threshold 0,85) | **Nenhum** — bot ainda exigiria 0,85 |
| Risco | Baixo (engine mais permissivo, mas bot barra) |

### Cenário 2: RVOL 0,60 (atual: 0,70)

| Métrica | Estimativa |
|---|---|
| Sinais adicionais no Engine | ~8.800 (+30%) |
| Que passariam ADX | ~2.200 |
| Que chegariam ao SignalValidator | ~180 |
| Impacto no bot (RVOL também checado) | Moderado — 422 rejeições por RVOL no validator |
| Risco | **Alto** — RVOL é o principal filtro de liquidez |

### Cenário 3: ADX 20 (atual: 25)

| Métrica | Estimativa |
|---|---|
| Sinais adicionais no Engine | ~650 (+50%) |
| Que chegariam ao SignalValidator | ~50 |
| Risco | Moderado — ADX 20-25 ainda indica tendência fraca |

### Cenário 4: Quality 0,55 no Engine (atual: 0,60)

| Métrica | Estimativa |
|---|---|
| Sinais adicionais no Engine | ~500 |
| Que chegariam ao SignalValidator | ~40 |
| Impacto no bot (quality 0,85) | **Nenhum** — bot ainda barra |
| Risco | Baixo |

### Conclusão do Simulador

**Ação que realmente teria impacto**: Alinhar os thresholds do Decision Engine com os do SignalValidator. Atualmente, mesmo que o engine seja liberal, o bot barra tudo. O gargalo real **não está nos thresholds do engine**, mas na **diferença de 0,25 entre engine (0,60) e bot (0,85)** para quality e **0,10 para confidence**.

---

## 8. RECOMENDAÇÕES

### Não alterar

| Gate | Threshold | Motivo |
|---|---|---|
| RR | 2,0 | Institucional, alinhado engine/bot |
| Consensus | 0,70 | Já perde só 1,6% dos sinais |
| Weighted Vote | 70% | Apenas 2 sinais barrados |
| ADX | 25 | Perde só 2,9%, protege tendência |

### Relaxar (threshold muito conservador)

| Gate | Atual | Proposto | Motivo |
|---|---|---|---|
| **Quality (Engine)** | 0,60 | 0,55 | Já comprovado que 0,60 captura 81% dos sinais; 0,55 adiciona ~500 sem risco (bot ainda filtra) |
| **Entry Zone** | 0,40 | 0,35 | Perde 12,7%; 0,70 era excessivo, 0,40 ainda conservador para o pós-recalibração |
| **RVOL (Engine vs Bot)** | 0,70/0,70 | Manter ambos | RVOL é gate de liquidez crítico; alinhado. |

### Endurecer

| Gate | Atual | Proposto | Motivo |
|---|---|---|---|
| Nenhum identificado | — | — | Todos os thresholds estão dentro ou acima do razoável |

### Remover (gate redundante)

| Gate | Arquivo | Motivo |
|---|---|---|
| **Kalman Gate 16** | `decision_engine.py` Final Validation | Duplicado do Gate 12 |
| **Contra-tendência Gate 16** | `decision_engine.py` Final Validation | Duplicado do Gate 15 |
| **Weighted Vote Final** | `main.py` Final Validation | Duplicado do Gate 14 |
| **Volume check duplicado** | `signal_validator.py` | Checks 7 e 15 são idênticos |
| **Consistency checks mortos** | `consistency_validator.py` | `flow_ok`/`timing_ok` não existem mais no V18.4 |

### Ação prioritária: Realinhar Engine ↔ Bot

**Problema**: O SignalValidator no bot usa thresholds draconianos (quality 0,85, confidence 0,85, structural 0,80, institutional 0,85) que eliminam **~99%** dos sinais que passam no engine.

**Opção A (recomendada)**: Unificar os thresholds num único lugar de configuração, com um valor intermediário:
- Quality: 0,75 (meio-termo entre engine 0,60 e bot 0,85)
- Confidence: 0,80 (meio-termo entre engine 0,75 e bot 0,85)
- Structural: 0,60 (meio-termo entre engine 0,30 e bot 0,80)
- Institutional: 0,65 (meio-termo entre engine 0,45 e bot 0,85)

**Opção B**: Mover toda a lógica de validação para o Decision Engine e eliminar o SignalValidator como camada separada, mantendo um único pipeline com thresholds consistentes.

### Ação secundária: Gate de Liquidez Inteligente

Substituir o RVOL fixo (0,70) por um gate adaptativo que considere:
- Volume absoluto mínimo (USDT)
- Spread máximo
- Profundidade do book de ordens
- Volatilidade atual (ATR%)

Isso permitiria capturar oportunidades em pares com baixo RVOL mas alta liquidez real.

---

## 9. IMPACTO ESPERADO DAS RECOMENDAÇÕES

| Ação | Sinais adicionais | Risco | Complexidade |
|---|---|---|---|
| Alinhar Engine/Bot (Opção A) | **+200 a +400/mês** | Moderado | Média |
| Remover redundâncias | 0 (qualidade) | Nenhum | Baixa |
| Relaxar Quality p/ 0,55 | +500 no engine (0 no bot) | Nenhum | Baixa |
| RVOL adaptativo | Difícil estimar | Baixo-Moderado | Alta |
| Backtest comparativo | N/A (ferramenta) | Nenhum | Média |

---

## 10. PRÓXIMOS PASSOS

1. **Aprovar** esta RFC
2. **Implementar** alinhamento Engine/Bot (Opção A)
3. **Remover** redundâncias identificadas
4. **Corrigir** consistency_validator.py (gates mortos)
5. **Implementar** modo de backtest para cálculo de Win Rate por gate
6. **Monitorar** por 7 dias e recalibrar se necessário

---

## 11. ESTRATÉGIA DE ROLLBACK

- Cada alteração de threshold deve ser feita individualmente, não em lote
- Antes de cada alteração, registrar o número de sinais aprovados/rejeitados no período anterior (baseline)
- Se após 24h o Win Rate cair > 5%, reverter a alteração
- Alterações no SignalValidator: manter a configuração original comentada, não removida
