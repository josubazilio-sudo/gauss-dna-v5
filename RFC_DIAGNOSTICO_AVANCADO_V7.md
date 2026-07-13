# RFC — Diagnóstico Avançado V7.0 (Ferramenta de Auditoria Institucional)

Data: 2026-07-12

## Objetivo

Evoluir o módulo de diagnóstico do QuantOS para uma ferramenta de auditoria
institucional completa (10 blocos: resumo do scanner, funil granular,
top quase-aprovados, diagnóstico por ativo, ranking de bloqueadores, saúde
de mercado, recomendação automática, resumo executivo, estatísticas gerais),
sem tocar em Decision Engine, filtros, pesos, thresholds, geração de sinais
ou Paper Trading.

## Motivação

Levantamento do estado atual (`ENGINE/diagnostic/engine.py`,
`DiagnosticEngine`/`DiagnosticReport`) mostra que:

- O funil hoje (`self._funnel` em `main.py`) só tem 11 estágios largos
  (`ativos_analisados, api, candles, indicadores, estrutura, smart_money,
  entry_zone, consensus, quality_gate, decision_engine, aprovados`) — não há
  estágios granulares por filtro (Liquidez, Volume, ATR, RSI, ADX, RVOL,
  Tendência, Fluxo, Kalman, Score) como o bloco 2 pede.
- Os motivos de rejeição hoje viram chaves de string com o valor numérico
  embutido (`"RVOL 0.48 < 0.7": 1`), o que impede agregação por categoria —
  precisa virar `{categoria, contagem, perda}` estruturado.
- Existe `top_candidates` (top-10 por quality) mas não no formato completo
  pedido no bloco 3 (Score/Qualidade/Confiança/Timing/Categoria/motivo).
- Não há ranking de bloqueadores, bloco de saúde de mercado, recomendação
  automática nem resumo executivo — tudo novo, mas 100% derivável de campos
  já calculados (`ScannerScore`, `SignalDecision`, `Signal.classification`,
  `coherence`, `penalty_reasons`, etc. — ver mapeamento anexo).
- Não há teste ativo cobrindo `DiagnosticEngine` hoje (só um teste arquivado
  fora do CI).

## Arquivos Afetados

- `ENGINE/diagnostic/engine.py` — estender `DiagnosticReport` com os novos
  campos estruturados (funil granular com perda numérica, quase-aprovados
  estruturados, ranking de bloqueadores, saúde de mercado, recomendação,
  resumo executivo, estatísticas/distribuições). Novos métodos read-only que
  **apenas leem** campos já calculados de `Signal`/`SignalDecision`/
  `ScannerScore` — nenhum recálculo de indicador.
- `ENGINE/diagnostic/advanced_report.py` (novo arquivo) — funções puras que
  recebem os dados já coletados pelo `DiagnosticEngine` e produzem os 10
  blocos (texto formatado para terminal + estrutura para Telegram).
- `SERVICES/telegram/telegram_diagnostic_formatter.py` — adicionar formatação
  para o relatório avançado, gated por uma nova env var
  (`TELEGRAM_SEND_ADVANCED_DIAGNOSTICS`, default `false`) para não inflar o
  chat principal sem opt-in explícito.
- `main.py` — apenas nos pontos onde o funil e o diagnóstico já são
  alimentados (`_process_scan_result`, chamadas a `self._diag.record_*`):
  passar os campos granulares já disponíveis (rvol, adx, atr_percent,
  liquidity_score, flow_score, kalman_direction, timing_index, etc.) que já
  existem em `sig.scores`/`sd`, sem novo cálculo nem nova chamada de API.
- `TESTS/test_diagnostico_avancado_v7.py` (novo).

## Impacto Esperado

- Relatório de diagnóstico muito mais rico e acionável (10 blocos), útil
  para calibração futura de thresholds — sem qualquer efeito na lógica de
  trading.
- Zero mudança em `Decision Engine`, `scanner_config.py` (gates/pesos),
  geração de sinais ou Paper Trading.
- Zero aumento de chamadas de API — todos os campos usados já são
  computados durante o pipeline normal.

## Riscos

- Baixo, por ser presentation-only. Risco principal: acoplar sem querer o
  módulo de diagnóstico a alguma decisão real (ex.: usar um campo do
  relatório para alterar comportamento) — mitigado por revisão explícita de
  que `advanced_report.py` é **somente leitura** dos dados já calculados,
  nunca escreve de volta em `Signal`/`SignalDecision`/`ScannerScore`.
- Nota sobre o critério de validação: como esta RFC não altera lógica de
  sinal, a "Validação de Métricas" da Diretriz Permanente (Win Rate, Profit
  Factor, Drawdown etc.) **não se aplica no sentido literal** — não há
  como essas métricas mudarem já que nenhum sinal é afetado. A evidência de
  sucesso aqui é: (a) suite de testes 100% verde, (b) diff de sinais
  aprovados/rejeitados **idêntico** antes/depois em um mesmo ciclo real
  (prova de zero impacto comportamental), (c) duração de ciclo (via
  `CycleProfiler` já existente) sem regressão mensurável.

## Plano de Implementação

1. Bloco 1 (Resumo do Scanner) — manter dados já existentes, só reorganizar
   apresentação.
2. Bloco 2 (Funil granular) — estruturar `pipeline_funnel` como lista de
   `{estagio, quantidade, perda}` por filtro, usando os `*_ok` flags já
   presentes em `SignalDecision` (rvol_ok, adx_ok, trend_ok, flow_ok,
   kalman_ok, quality_ok, consensus_ok etc.) em vez de parsear strings.
3. Bloco 3 (Top quase-aprovados) — estender `top_candidates` para incluir
   todos os campos pedidos (Score/Qualidade/Confiança/Timing/Categoria +
   motivo estruturado de reprovação), mínimo 10 ativos.
4. Bloco 4 (Diagnóstico por ativo) — checklist ✔/✘ por filtro + status final
   + motivo principal, usando os campos já calculados por ativo.
5. Bloco 5 (Ranking de bloqueadores) — agregar `rejection_reasons`
   estruturado (do bloco 2) por categoria e ordenar por % de contribuição.
6. Bloco 6 (Saúde de mercado) — agregar médias/medianas do ciclo (liquidez,
   volume, ATR, RVOL, RSI, ADX, funding, BTC/ETH trend) e classificar em
   5 níveis (Excelente/Boa/Neutra/Ruim/Crítica) via thresholds fixos
   documentados no próprio módulo de diagnóstico (não no scanner_config).
7. Bloco 7 (Recomendação automática) — regra simples baseada no bloco 5
   (maior bloqueador) + bloco 6 (saúde de mercado).
8. Bloco 8 (Resumo executivo) — template de até 5 linhas combinando 6 e 7.
9. Bloco 9 (Estatísticas gerais) — taxas de aprovação/reprovação, tempo
   médio/ativo (via `CycleProfiler`), distribuição de scores/timing/tiers.
10. Testes unitários para cada bloco + teste de integração (rodar um ciclo
    real ou fixture de ciclo e verificar que o relatório é gerado sem
    exceção e sem alterar nenhum campo de `SignalDecision`).

## Critérios de Aceitação

- Todos os 10 blocos presentes e populados com dados reais (não fictícios).
- Nenhum campo de `Signal`/`SignalDecision`/`ScannerScore` é recalculado ou
  alterado pelo módulo de diagnóstico.
- Nenhuma chamada de API nova.
- Suite de testes 100% verde, incluindo os novos testes do módulo.
- Diff de sinais aprovados/rejeitados idêntico antes/depois (mesmo input).
- Duração de ciclo sem regressão mensurável (`CycleProfiler`).
- Documentação atualizada (CHANGELOG, relatório final).

## Plano de Rollback

Mudança isolada em `ENGINE/diagnostic/` + 1 novo arquivo de formatação
Telegram + leitura adicional de campos já existentes em `main.py`. Rollback
via `git revert` do(s) commit(s) desta RFC.
