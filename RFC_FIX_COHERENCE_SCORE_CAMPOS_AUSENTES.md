# RFC — Correção de Bug: Coherence Score / Votação Ponderada com Campos Ausentes

Data: 2026-07-12

## Objetivo

Corrigir um bug (não recalibração de threshold) na camada de "Validação
Final" (`ENGINE/common/operational.py:compute_institutional_coherence_score`
e `compute_weighted_vote`, adicionadas externamente na V18.4) que le
campos inexistentes no dicionário recebido, zerando sistematicamente
componentes do score para qualquer sinal em tendência.

## Motivação (Bug Confirmado)

Investigando por que o CHZUSDT SHORT (regime `trending_down`, quality
~0.71-0.75, aprovado pelo Decision Engine dezenas de vezes) sempre trava
na Validação Final com os MESMOS valores exatos (Coherence Score 56.2,
Votação Ponderada 63.2%, sem nenhuma variação em 30+ minutos e múltiplos
ciclos), encontrei 4 problemas nas duas funções:

1. `signal_data.get("flow_score", 0)` e `signal_data.get("momentum_score", 0)`
   — nenhum dos dois campos existe em `SignalDecision.to_dict()` (que é o
   `data` passado a essas funções em `main.py`). Sempre retornam 0.
2. `"BOS" in str(signal_data.get("patterns", []))` — `to_dict()` não tem
   campo `patterns` (só `bos`/`choch` como contadores inteiros). Sempre
   avalia `str([])`, `has_bos`/`has_choch` sempre `False`.
3. `trend in ("uptrend", "downtrend", ...)` — `MarketRegime` (enum real
   do projeto, `ENGINE/market/market_types.py`) usa `"trending_up"`/
   `"trending_down"`, nunca `"uptrend"`/`"downtrend"`. A comparação nunca
   bate para nenhum regime de tendência real (só "ranging" bate, por
   coincidência de nome).

Impacto combinado: os componentes "fluxo" (peso 1.8), "momentum" (peso
1.2), "padrão" (peso 0.8) e "regime" (peso 1.5) — **5.3 de 14.4 pontos de
peso (37%)** — são zerados sistematicamente para QUALQUER sinal em
tendência (`trending_up`/`trending_down`), mesmo quando perfeitamente
alinhado. Isso explica por que sinais de qualidade real (quality
0.71-0.75, todos os hard gates do Decision Engine aprovados) ficam presos
abaixo dos limiares de 60 (Coherence) e 70% (Votação) — não por serem
ruins, mas por um bug de leitura de campos.

## Arquivos Afetados

- `ENGINE/decision/signal_decision.py` — adicionar campos `flow_score` e
  `momentum_score` a `SignalDecision` (mesmo padrão já usado para
  `institutional_score`/`structural_score`/`market_score`/
  `liquidity_score`), populados em `from_signal()` a partir de
  `scores.flow_score`/`scores.momentum_score` (já calculados pelo
  pipeline, sem novo cálculo), e incluídos em `to_dict()`.
- `ENGINE/common/operational.py` — em `compute_institutional_coherence_score`
  e `compute_weighted_vote`: (a) trocar a checagem de padrão para usar
  `signal_data.get("bos", 0) > 0 or signal_data.get("choch", 0) > 0` em
  vez de parsear uma lista `"patterns"` inexistente; (b) trocar a
  comparação de tendência para substring (`"up" in trend or "alta" in trend`
  / `"down" in trend or "baixa" in trend`), mesmo padrão já usado em outras
  partes do próprio arquivo e em `decision_engine.py` para checar
  `kalman_direction`/regime.

## Impacto Esperado

- Sinais em tendência real e bem alinhados deixam de ser incorretamente
  penalizados por um bug de leitura de campo — Coherence Score e Votação
  Ponderada passam a refletir a real coerência institucional do sinal.
- Nenhuma mudança em Decision Engine, Hard Gates, thresholds de aprovação
  do scanner, scoring de Quality/Confidence/Consensus. A correção é
  estritamente sobre a Validação Final (camada V18.4, pós-aprovação).

## Riscos

- Baixo a médio: com o bug corrigido, MAIS sinais vão passar pela
  Validação Final do que passam hoje (já que hoje ela reprova
  sistematicamente sinais de tendência bons). Isso é o efeito PRETENDIDO
  da correção (corrigir falso-negativo), mas precisa ser observado em
  produção para confirmar que não introduz falso-positivo (sinal ruim
  passando indevidamente). Mitigação: threshold de 60/70% continua
  intacto — só os INPUTS do cálculo são corrigidos, não os limiares.

## Testes

- Testes unitários para `compute_institutional_coherence_score` e
  `compute_weighted_vote` com dados sintéticos reproduzindo exatamente o
  bug (regime `trending_down`, sem `flow_score`/`momentum_score`/
  `patterns` no dict) confirmando o score ANTES da correção, e o score
  CORRIGIDO depois (usando `bos`/`choch`/`flow_score`/`momentum_score`
  reais).
- Teste de regressão: `SignalDecision.to_dict()` agora inclui
  `flow_score`/`momentum_score`.
- Suite completa sem regressão.

## Critérios de Aceitação

- Um sinal SHORT em regime `trending_down` com módulos realmente
  alinhados (kalman down, estrutura forte, fluxo bom, etc.) deve atingir
  Coherence Score condizente (não mais capado por bug).
- Nenhuma mudança de threshold (60/70% continuam os mesmos).
- Suite de testes 100% verde.
- Homologação: observar se sinais reais (ex.: CHZUSDT) que hoje travam
  na Validação Final passam a ser aprovados quando genuinamente
  coerentes.

## Plano de Rollback

Mudança isolada: 2 campos novos em dataclass (aditivo) + correção de 2
comparações de string em 2 funções. `git revert` do(s) commit(s).
