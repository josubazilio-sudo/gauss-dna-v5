# Relatório Final — RFC V20.2: Correção de Consistência do Sinal

Data: 2026-07-12

## Resumo Executivo

Corrigidas 3 inconsistências reais de apresentação do sinal (classificação
divergente, fórmula de retorno sobre margem incorreta, penalização
duplicada) e adicionada uma validação final que cancela o envio ao
Telegram e loga o erro caso os dados do sinal sejam internamente
incoerentes. Nenhuma mudança em Scanner, Decision Engine, Consensus,
Confluence, Score, Quality Gate, filtros ou cálculos de entrada.

## Arquivos Modificados

- `SERVICES/telegram/telegram_formatter.py` — classificação exibida uma
  única vez (Bloco "Classificação e Qualidade"); lista de penalização
  exibida uma única vez (Bloco "Análise", `penalty_details`); variáveis
  mortas resultantes removidas (`cls_label`, `penalties_list`,
  `penalty_texts`, função `_bullet()`).
- `ENGINE/common/operational.py` — `retorno_margem_pct` corrigido para
  usar `margem_utilizada_usdt` como denominador (era `perda_maxima_usdt`).
- `SERVICES/telegram/telegram_validator.py` — nova função
  `validate_presentation_consistency()`.
- `SERVICES/telegram/telegram_service.py` — chama a nova validação
  antes de formatar/enfileirar o envio.
- `TESTS/test_rfc_v20_2_consistencia_sinal.py` (novo, 14 testes).
- `TESTS/test_rfc_v18_4_consolidacao.py` — 1 teste atualizado (validava
  a fórmula antiga; ajustado cenário de leverage para expor a
  diferença real entre as 3 métricas de retorno).

## Achados Confirmados em Produção

- `compute_overall_score()` já detectava e logava a divergência de
  classificação (`"Classificacao divergente: scanner %s vs overall_score
  %.1f -> %s"`), mas nunca a corrigia na exibição — o card mostrava
  literalmente o que o log já apontava como inconsistente.
- `retorno_margem_pct` estava, na prática, calculando o RR em
  porcentagem (lucro/perda máxima), rotulado como "retorno sobre
  margem" — dois conceitos financeiros diferentes.

## Testes Executados

- 14 testes novos cobrindo: fórmula corrigida de retorno sobre margem
  (com comparação explícita contra a fórmula antiga para provar a
  mudança), validação de consistência (preços fora de ordem por
  direção, RR incompatível com preços, tier incompatível com score,
  casos válidos LONG/SHORT), e o card formatado (classificação aparece
  uma única vez, penalização aparece uma única vez).
- Suite completa: **181/181 passando**, zero regressão.

## Auditoria

- Nenhum arquivo em `ENGINE/scanner/` ou `ENGINE/decision/` foi tocado.
- `validate_presentation_consistency()` reaproveita `_derive_tier()`
  já existente (importado de `operational.py`) — não duplica a tabela
  `CLASSIFICATION_RANGES`, confirmado por teste dedicado.
- Nenhuma variável morta introduzida; as que ficaram órfãs após a
  remoção de código duplicado foram removidas na mesma mudança.

## Homologação

- Sintaxe e import de todos os arquivos verificados.
- Deploy no VPS confirmado: processo estável, sem tracebacks nos logs
  pós-restart.

## Riscos Remanescentes

- Baixo: a nova validação de consistência pode, em tese, bloquear um
  sinal genuinamente aprovado se outro bug (não coberto por esta RFC)
  produzir dados incoerentes — esse é o comportamento intencional do
  item 4 da RFC (bloquear e logar em vez de exibir dado quebrado).
  Recomenda-se observar os logs por `"envio cancelado por
  inconsistencia de apresentacao"` nos próximos dias para confirmar que
  isso não está descartando sinais válidos por falso-positivo.

## Estratégia de Rollback

Mudanças isoladas em 3 arquivos de apresentação/validação + 1 arquivo
de teste. `git revert` do(s) commit(s) desta RFC restaura o
comportamento anterior.

## Próxima Fase Recomendada

Monitorar produção por alguns ciclos para confirmar que nenhum sinal
válido está sendo bloqueado pela nova validação de consistência, e que
o card do Telegram exibe exatamente uma classificação e uma lista de
penalização por sinal.
