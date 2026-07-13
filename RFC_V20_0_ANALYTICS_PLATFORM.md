# RFC V20.0 — QuantOS Analytics Platform

Data: 2026-07-12

## Objetivo

Evoluir o QuantOS para uma plataforma de análise operacional, gestão de
risco e acompanhamento de performance, em módulos novos e desacoplados,
sem tocar em Scanner, Decision Engine, Consensus, Confluence, Hard Gates
ou Thresholds.

## Motivação e Divergências Necessárias (Documentadas)

Levantamento prévio (read-only) mostrou que boa parte do que esta RFC pede
**já existe** no projeto, em 3 lugares distintos:

- `ENGINE/common/trade_registry.py` (`TradeRegistry`, SQLite em
  `MEMORY/trades/trades.db`): já registra ID, timestamps, ativo, direção,
  timeframe, entry/stop/TP1/TP2, quality, confidence, overall_score,
  consensus, risk_reward, resultado, lucro/perda, tempo até TP/stop,
  setup_key — e já calcula `get_statistics()` (win_rate, profit_factor,
  drawdown, payoff, expectancy), `get_statistics_by_classification/
  timeframe/direction()`, `get_setup_ranking()`, `get_loss_analysis()`,
  `get_weekly_report()`.
- `CORE/trading/paper_trading.py` (`PaperTradingEngine.get_stats()`): win
  rate, profit factor, sharpe ratio, max drawdown, expectancy, payoff,
  win rate por classificação/símbolo/timeframe/direção, tempo médio até
  TP/stop.
- `ENGINE/diagnostic/engine.py` (`DiagnosticEngine.get_dashboard_metrics()`):
  win_rate, profit_factor, drawdown, avg_win/loss, expectancy,
  avg_overall_score, avg_retorno_pct — já persistido em
  `MEMORY/audit/summary.json`.

Recalcular Win Rate/Profit Factor/Drawdown/Expectancy uma 4ª vez violaria
diretamente a regra do próprio prompt ("baixo acoplamento, alta coesão")
e a regra permanente do projeto ("sem duplicação"). **Decisão de design**:
os módulos novos em `analytics/` são uma **camada de consolidação fina**
que LÊ dessas 3 fontes existentes (nunca recalcula do zero o que já está
correto e testado) e só implementa o que **não existe ainda**: lucro
diário/semanal/mensal, maiores sequências win/loss, curva de banca,
diário automático, e a camada de apresentação (dashboard/app/API).

Duas correções de convenção em relação ao prompt original (documentadas,
não silenciosas):
1. Pasta `analytics/` → colocada dentro do pacote já existente
   `ENGINE/analytics/` (que já contém `analytics_engine.py` e
   `trade_analytics.py`), em vez de uma pasta paralela na raiz —
   evita fragmentar a arquitetura.
2. `memory/trades.json`/`memory/metrics.json` → `MEMORY/analytics/*.json`
   (o projeto usa `MEMORY/` maiúsculo em todo o codebase — `MEMORY/audit`,
   `MEMORY/paper_trading.json`, `MEMORY/trades/`).

## Arquivos Criados (todos novos, dentro de `ENGINE/analytics/`)

- `trade_storage.py` (Fase 1) — exporta um snapshot consolidado de
  `TradeRegistry` para `MEMORY/analytics/trades.json`, no schema pedido
  (ID/Data/Hora/Ativo/Direção/Timeframe/Entrada/Stop/TP1/TP2/Score/
  Confidence/Quality/Setup/Status/Resultado/Lucro/Prejuízo/Duração).
  Não registra nada novo — `TradeRegistry.open_trade()/close_trade()`
  (já chamados em `main.py`) continuam sendo a fonte da verdade.
- `statistics.py` (Fase 2) — consolida `TradeRegistry.get_statistics()` +
  calcula o que falta (lucro diário/semanal/mensal, maior sequência
  win/loss, taxa de acerto por ativo). Persiste em
  `MEMORY/analytics/metrics.json`.
- `dashboard.py` (Fase 3) — função pura que monta o dict do dashboard a
  partir de `statistics.py` + `DiagnosticEngine.get_dashboard_metrics()` +
  status do scanner (`DiagnosticReport.health`). Sem novo cálculo.
- `risk_manager.py` (Fase 4) — wrapper fino sobre
  `OperationalCalculator.calculate()` (já retorna quantidade, valor de
  posição, perda máxima, lucro esperado) + `BotRiskManager.
  calculate_position_size()`, adicionando RR explícito e alavancagem
  sugerida (heurística simples, documentada). Nunca altera o sinal
  original — função pura, entrada/saída.
- `journal.py` (Fase 5) — para cada trade fechado em `TradeRegistry`,
  gera uma entrada de diário (entrada/stop/TP/resultado/lucro/tempo/
  observações auto-geradas do setup/classificação). Persiste em
  `MEMORY/analytics/journal.jsonl` (append-only, mesmo padrão da RFC
  V19.2 de estabilidade).
- `equity.py` (Fase 6) — curva de banca (diária/semanal/mensal) a partir
  do histórico de `TradeRegistry.get_closed_trades()`. Persiste em
  `MEMORY/analytics/equity.json`.
- `performance_insights.py` (Fase 7 — nome escolhido para não colidir com
  o já existente `analytics_engine.py`) — melhor/pior ativo, horário,
  dia, setup, timeframe, maior lucro/perda. Reaproveita
  `get_weekly_report()`/`get_setup_ranking()`/`get_loss_analysis()` já
  existentes; adiciona só o agrupamento por hora/dia da semana que não
  existe hoje.
- `app_cli.py` (Fase 8) — camada de apresentação somente-leitura (menu
  Dashboard/Scanner/Operações/Analytics/Gestão/Configurações), consome
  apenas os dicts produzidos pelos módulos acima. **Limitação
  transparente**: implementado como CLI/texto formatado nesta RFC, não
  como app Android nativo (fora do escopo realista deste ambiente de
  desenvolvimento) — a camada de dados fica pronta para um app real
  consumir depois.
- `api_routes.py` (Fase 9) — funções puras (`get_dashboard()`,
  `get_trades()`, `get_metrics()`, `get_risk(...)`, `get_equity()`)
  retornando dicts serializáveis em JSON, prontas para serem penduradas
  em um framework HTTP futuro. **Risco de segurança sinalizado**: esta
  RFC NÃO abre nenhuma porta/servidor HTTP em produção — isso seria uma
  mudança de superfície de ataque na VPS que merece decisão explícita
  separada, então fica preparado mas não implantado.

## Pontos de Integração em `main.py` (mínimos, não-invasivos)

Um único hook no fim de cada ciclo (mesmo ponto onde já fica o log do
Diagnóstico Avançado V7.0): chamar
`trade_storage.export_trades_json(self._trade_registry)` e
`statistics.compute_and_persist(self._trade_registry)`. Nenhuma mudança
em Scanner/Decision Engine/Consensus/Confluence/gates/thresholds.

## Testes

Cada módulo (Fases 1-7) recebe testes unitários próprios em
`TESTS/test_analytics_*.py`, usando dados sintéticos de trades (sem
depender de trades reais existirem). Fases 8-9 recebem testes de que as
funções retornam a estrutura esperada sem lançar exceção com dados vazios
e com dados de exemplo.

## Critérios de Aceitação

- Nenhuma duplicação de cálculo já existente e correto em
  `TradeRegistry`/`PaperTradingEngine`/`DiagnosticEngine`.
- Nenhuma alteração em Scanner, Decision Engine, Consensus, Confluence,
  Hard Gates, Thresholds (verificável: nenhum arquivo em
  `ENGINE/scanner/`, `ENGINE/decision/` além do já entregue nas RFCs
  anteriores desta sessão é tocado).
- Testes automatizados em todos os módulos novos, suite completa sem
  regressão.
- Nenhum servidor HTTP é iniciado automaticamente em produção.

## Plano de Implementação (sequencial, com testes antes de avançar)

Fase 1 → testes → Fase 2 → testes → ... → Fase 9, na ordem do prompt
original, sem pular etapas.

## Plano de Rollback

Todos os arquivos são novos e aditivos (nenhum arquivo existente tem
lógica removida, só 2 linhas de chamada em `main.py`). Rollback via
remoção dos novos arquivos + reversão das 2 linhas em `main.py`.
