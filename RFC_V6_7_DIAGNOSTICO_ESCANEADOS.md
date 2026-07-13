# RFC V6.7 — Diagnóstico Baseado Apenas nas Moedas Escaneadas

Data: 2026-07-12

## Objetivo

Reestruturar o Diagnóstico Avançado para que todas as estatísticas sejam
calculadas exclusivamente sobre os ativos que chegaram ao motor final de
escaneamento (`report.decisions`, alimentado por `SignalDecision.to_dict()`),
e não sobre todas as moedas da exchange (`report.total_assets`).

Atualmente `build_general_stats()` usa `report.total_assets` como denominador
para métricas como `tempo_medio_por_ativo_ms` e `ativos_por_minuto`, o que
distorce o diagnóstico ao incluir 272+ moedas que nunca geraram sinal.

## Diagnóstico

### 1. `total_assets` vs decisões reais

`report.total_assets` reflete todas as moedas que a exchange oferece (ex. 272).
`report.decisions` contém apenas os ativos que passaram pelo scanner e
chegaram ao DecisionEngine (ex. 30-50). Métricas como `tempo_medio_por_ativo_ms`
dividem a duração do ciclo por 272 em vez de 50, subestimando o custo real
por ativo analisado.

### 2. Pipeline funnel não exposto no sumário

O `build_scanner_summary()` (bloco 1) retorna apenas dados genéricos
(exchange, total_assets, erros, duração). Os estágios do funil
(`pipeline_funnel`) existem no `DiagnosticReport` mas não são aproveitados
pelo advanced_report para gerar o resumo do ciclo.

### 3. Sem indicadores de eficiência

Não há métricas como `Escaneadas / Válidas` ou `Aprovadas / Escaneadas`
que permitam avaliar se o scanner está excessivamente restritivo ou
permissivo.

### 4. Market statistics sem filtro

Médias de RSI, ADX, RVOL, ATR etc. não são calculadas no advanced_report.
Quando forem adicionadas, devem usar APENAS os ativos escaneados.

## Arquivos Afetados

- `ENGINE/diagnostic/advanced_report.py` — novo bloco RESUMO DO CICLO,
  correção de denominadores em estatísticas gerais, novas funções de
  market statistics, guarda para decisions vazia, métricas de eficiência.
- `TESTS/test_diagnostico_avancado_v7.py` — novos testes para o bloco
  de ciclo, market statistics, guarda vazio, eficiência.

## Impacto Esperado

- Resumo do ciclo com estágios reais do funil.
- Todas as médias calculadas exclusivamente sobre ativos escaneados.
- Indicadores de eficiência do scanner (Escaneadas/Válidas, Aprovadas/Escaneadas).
- Guarda "Sem ativos suficientes" quando nenhuma moeda chega ao scanner final.
- Bloco de market statistics (RSI, ADX, RVOL, ATR médios) filtrado pelos
  ativos escaneados.

## Riscos

- Baixo: mudanças de apresentação em módulo somente-leitura de diagnóstico.
  Nenhuma alteração em Scanner, Decision Engine, gates, thresholds,
  scoring, cálculos de entrada ou Paper Trading.
- A introdução do guard de decisions vazia pode fazer o relatório devolver
  estrutura diferente quando não há dados — consumidores (main.py,
  telegram_diagnostic_formatter) devem tratar isso.

## Plano de Implementação

1. `build_cycle_summary(report)` — novo bloco RESUMO DO CICLO
   - Exchange, Válidas, Escaneadas, Aprovadas, Reprovadas
   - Taxa Aprovação, Score Médio, Qualidade Média, Convicção Média
   - Eficiência do Scanner, Taxa de Conversão, Taxa de Rejeição

2. `build_market_statistics(report)` — novo bloco
   - RSI médio, ADX médio, RVOL médio, ATR médio
   - Usa `report.indicators` filtrado pelos símbolos em `report.decisions`

3. Modificar `build_general_stats()` — usar `len(decisions)` como denominador
   para tempo_medio_por_ativo_ms e ativos_por_minuto

4. Adicionar guarda em `build_advanced_report()`:
   - Se `not decisions`: retorna estrutura mínima com mensagem

5. Adicionar `"resumo_ciclo"` e `"mercado_estatisticas"` ao dicionário retornado

## Testes

- `test_cycle_summary_computes_all_fields` — verifica estrutura do RESUMO
- `test_cycle_summary_empty_decisions` — guarda vazio
- `test_cycle_summary_approval_rate` — taxa de aprovação correta
- `test_cycle_summary_efficiency_metrics` — eficiência e conversão
- `test_market_statistics_computes_averages` — médias corretas
- `test_market_statistics_empty_indicators` — sem indicadores
- `test_general_stats_uses_decisions_not_assets` — denominador corrigido
- Testes existentes: adaptados para novos blocos

## Critérios de Aceitação

- RESUMO DO CICLO usa exclusivamente `report.decisions` para contagens.
- `build_general_stats` não usa mais `report.total_assets` como denominador
  principal para tempo médio por ativo.
- Guarda "Sem ativos suficientes" funciona quando decisions está vazia.
- Eficiência do Scanner e Taxa de Conversão/Rejeição computadas.
- Market statistics (RSI, ADX, RVOL, ATR) usam apenas dados dos ativos
  escaneados.
- Nenhuma alteração em Scanner/Decision Engine/Consensus/Confluence/Score/
  Quality Gate/filtros/cálculos de entrada.
- Suite completa sem regressão.

## Plano de Rollback

Mudanças isoladas em 1 arquivo de diagnóstico. `git revert` do(s) commit(s)
desta RFC restaura o comportamento anterior.
