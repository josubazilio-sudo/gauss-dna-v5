# Changelog

## [20.3.0] - 2026-07-12
### Fixed — RFC V20.2: Correção de Consistência do Sinal
(Nota: o prompt original chamou esta RFC de "V20.2", colidindo com a
entrada de CHANGELOG anterior — arquivo mantido como
`RFC_V20_2_CONSISTENCIA_SINAL.md`, versão de CHANGELOG segue em 20.3.0.)

- **Classificação divergente eliminada**: `SERVICES/telegram/telegram_formatter.py`
  exibia DUAS classificações diferentes para o mesmo sinal — `overall_tier`
  (Bloco "Classificação e Qualidade") e `classification_label`
  (Bloco "Análise"), calculadas por sistemas independentes que já
  divergiam de fato em produção (`compute_overall_score()` já logava
  `"Classificacao divergente: scanner X vs overall_score Y"` como
  warning, sem nunca corrigir a exibição). Removida a segunda exibição
  — única fonte de verdade agora (`overall_tier`).
- **Fórmula de "Retorno sobre Margem" corrigida**:
  `ENGINE/common/operational.py:OperationalCalculator.calculate()`
  calculava `lucro_liquido_usdt / perda_maxima_usdt * 100` (na prática,
  o RR em %, não um retorno sobre margem). Corrigido para
  `lucro_liquido_usdt / margem_utilizada_usdt * 100` (retorno real sobre
  o capital comprometido na posição).
- **Penalização duplicada removida**: card mostrava duas listas de
  penalização de sistemas paralelos (`penalty_reasons` no bloco
  "Convicção" e `penalty_details` no bloco "Análise"). Mantida apenas
  `penalty_details` (mais completa: gate + peso perdido + motivo).
- **Nova validação final antes do envio**:
  `SERVICES/telegram/telegram_validator.py:validate_presentation_consistency()`
  verifica ordem de preços coerente com a direção (LONG/SHORT), RR
  exibido compatível com os preços reais (tolerância), e tier
  compatível com o `overall_score` numérico (reaproveita `_derive_tier()`
  já existente — não duplica a tabela de classificação). Chamada em
  `telegram_service.py:_format_and_queue()` — se falhar, cancela o
  envio e registra o erro no log em vez de mandar um card contraditório.
- Nenhuma mudança em Scanner, Decision Engine, Consensus, Confluence,
  Score, Quality Gate, filtros ou cálculos de entrada.
- 14 testes novos (`TESTS/test_rfc_v20_2_consistencia_sinal.py`). 1
  teste preexistente (`test_operational_calculator_separates_the_four_return_metrics`)
  atualizado: validava a fórmula antiga (incorreta) de retorno sobre
  margem, e usava `leverage=1.0` implícito — cenário em que retorno
  sobre margem e retorno sobre o ativo são matematicamente idênticos
  por definição (margem = valor nominal sem alavancagem), mascarando a
  necessidade de valores distintos. Ajustado para `leverage=5.0`.
- Suite completa: **181/181 passando**, zero regressão.
- Homologado e deployado no VPS, estável, sem tracebacks.

## [20.2.0] - 2026-07-12
### Fixed — 2 bugs revelados apos o fix do Coherence Score (V20.1)
Com sinais finalmente passando pela Validacao Final (V20.1), dois bugs
pre-existentes ficaram visiveis (o pipeline nunca havia chegado tao longe
antes):

- **`SERVICES/telegram/telegram_formatter.py`**: `_AttrDict`
  (`SERVICES/telegram/signal_compat.py`) embrulha automaticamente
  qualquer dict aninhado em outro `_AttrDict` ao ser acessado via
  atributo. Isso quebrava sistematicamente `isinstance(x, dict)` para
  `probability`, `coherence_score`, `weighted_vote`,
  `risk_decomposition`, `coherence_audit` e `overall_score`, causando
  `TypeError: float() argument must be a string or a real number, not
  '_AttrDict'` e derrubando a formatacao da mensagem (sinal aprovado
  nunca chegava ao Telegram). Corrigido com novo helper `_unwrap()`
  aplicado nos 6 pontos afetados.
- **`ENGINE/common/trade_registry.py`**: `TradeRegistry.open_trade()`
  chamava `OperationalCalculator.calculate()` com assinatura errada
  (`calculate(quality, entry_price, stop_loss, tp1)`) sempre que o
  sinal nao trazia `"operational"` pre-calculado — o que era SEMPRE o
  caso, ja que `main.py` nunca preenche essa chave. Gerava
  `TypeError: missing 1 required positional argument: 'balance'`,
  impedindo o registro do trade. Corrigido: chamada com argumentos
  nomeados corretos (`entry_price, stop_loss, take_profit_1, quantity,
  balance, leverage`), usando `quantity`/`balance`/`leverage` agora
  tambem repassados por `main.py` no dict do trade. Campos de saida
  remapeados para o schema atual do `OperationalCalculator`
  (`valor_nominal`, `margem_utilizada_usdt`, `lucro_liquido_usdt`,
  `perda_maxima_usdt`, `alavancagem_efetiva`).
- 9 testes novos (`TESTS/test_fix_telegram_attrdict_e_trade_registry.py`).
- Suite completa: 167/167 passando, zero regressao.
- Homologado no VPS: `AVICIUSDT SHORT` confirmado passando pela
  Validacao Final (`DEDUP: ... -> novo_sinal`, `status=APPROVED`) apos
  o fix do Coherence Score (V20.1); fix de Telegram/TradeRegistry
  deployado em seguida para o proximo sinal completar o ciclo inteiro.

## [20.1.0] - 2026-07-12
### Fixed — Bug critico: Coherence Score / Votacao Ponderada com campos ausentes
- Investigando por que sinais aprovados pelo Decision Engine (ex.: CHZUSDT
  SHORT, quality ~0.71-0.75, regime trending_down) travavam repetidamente
  na camada de "Validacao Final" (V18.4) com os MESMOS valores exatos
  (Coherence Score 56.2, Votacao Ponderada 63.2%) por 30+ minutos e
  multiplos ciclos, encontrado bug real (nao calibracao) em
  `ENGINE/common/operational.py:compute_institutional_coherence_score`
  e `compute_weighted_vote`:
  - `signal_data.get("flow_score", 0)` / `.get("momentum_score", 0)` —
    nenhum dos dois campos existia em `SignalDecision.to_dict()`. Sempre
    retornavam 0, zerando os componentes "fluxo" (peso 1.8) e "momentum"
    (peso 1.2).
  - `"BOS" in str(signal_data.get("patterns", []))` — `to_dict()` nao tem
    campo `patterns` (so contadores `bos`/`choch`). Sempre avaliava
    `str([])`, zerando o componente "padrao" (peso 0.8).
  - `trend in ("uptrend", "downtrend", ...)` — `MarketRegime` (enum real)
    usa `"trending_up"`/`"trending_down"`, nunca essas strings exatas.
    Zerava o componente "regime" (peso 1.5) para QUALQUER sinal em
    tendencia real, mesmo perfeitamente alinhado.
  - Impacto combinado: 5.3 de 14.4 pontos de peso (37%) zerados
    sistematicamente para sinais em tendencia — explicando por que
    setups de qualidade real ficavam presos abaixo dos limiares de
    60 (Coherence) e 70% (Votacao).
- `ENGINE/decision/signal_decision.py`: adicionados campos `flow_score` e
  `momentum_score` (populados de `scores.flow_score`/`scores.momentum_score`,
  ja calculados pelo pipeline — sem recalculo), incluidos em `to_dict()`.
- `ENGINE/common/operational.py`: `has_bos`/`has_choch` agora usam os
  contadores reais (`signal_data.get("bos", 0) > 0`); comparacao de
  tendencia trocada para substring (`"up" in trend`/`"down" in trend`),
  compativel com `MarketRegime.TRENDING_UP`/`TRENDING_DOWN`.
- Nenhuma mudanca de threshold (60/70% continuam os mesmos) — so os
  INPUTS do calculo foram corrigidos.
- 9 testes novos (`TESTS/test_fix_coherence_score_campos_ausentes.py`),
  reproduzindo o cenario real (CHZUSDT-like) antes/depois do fix. 4
  testes preexistentes (`test_decision_engine_recalibracao.py`) que
  usavam o formato antigo (`"patterns": [...]`) atualizados para o
  contrato real (`"bos"`/`"choch"`).
- Suite completa: 158/158 passando, zero regressao.
- **Incidente durante a implementacao**: `ENGINE/common/operational.py`
  foi acidentalmente sobrescrito com conteudo colado no editor (nao
  relacionado ao codigo) enquanto o arquivo estava aberto. Recuperado a
  partir da copia valida do VPS (ultimo deploy bem-sucedido antes do
  incidente) e as duas correcoes foram reaplicadas sobre essa base.

## [20.0.0] - 2026-07-12
### Added — QuantOS Analytics Platform (RFC V20.0)
- Novo pacote `ENGINE/analytics/` com 9 modulos (um por fase da RFC),
  desenhados como camada de CONSOLIDACAO sobre infraestrutura ja
  existente (`TradeRegistry`, `PaperTradingEngine`, `DiagnosticEngine`)
  em vez de recalcular Win Rate/Profit Factor/Drawdown/Expectancy uma 4a
  vez — decisao de design documentada na RFC.
- `trade_storage.py` (Fase 1): exporta snapshot de `TradeRegistry` para
  `MEMORY/analytics/trades.json` no schema pedido (ID/Data/Hora/Ativo/
  Direcao/Timeframe/Entrada/Stop/TP1/TP2/Score/Confidence/Quality/Setup/
  Status/Resultado/Lucro/Prejuizo/Duracao).
- `statistics.py` (Fase 2): consolida `TradeRegistry.get_statistics()` +
  calcula lucro diario/semanal/mensal, maiores sequencias win/loss,
  duracao media, win rate por ativo. Persiste em
  `MEMORY/analytics/metrics.json`.
- `dashboard.py` (Fase 3): funcao pura de consolidacao para exibicao em
  tempo real (scanner status, mercado, operacoes hoje, win rate, PF,
  drawdown, lucro, banca, melhor/pior ativo, melhor horario/timeframe,
  proximo ciclo).
- `risk_manager.py` (Fase 4): calculadora pura (banca+risco%+entrada+stop
  -> quantidade/valor posicao/perda maxima/lucro esperado/RR/alavancagem
  sugerida), reaproveita `OperationalCalculator` — nunca altera o sinal
  original.
- `journal.py` (Fase 5): diario automatico append-only (JSON Lines),
  idempotente entre ciclos, observacoes auto-geradas por setup/
  classificacao/resultado.
- `equity.py` (Fase 6): curva de banca diaria/semanal/mensal acumulada,
  rentabilidade, capital inicial/atual, reaproveitando drawdown ja
  calculado por `TradeRegistry`.
- `performance_insights.py` (Fase 7): melhor/pior ativo, horario, dia da
  semana, setup, timeframe, maior lucro/perda — calculado sobre o
  HISTORICO COMPLETO (nao apenas os 7 dias de `get_weekly_report()`).
- `app_cli.py` (Fase 8): camada de apresentacao somente-leitura (menu
  Dashboard/Scanner/Operacoes/Analytics/Gestao/Configuracoes). Limitacao
  documentada: implementado como formatacao de texto/CLI nesta RFC, nao
  como app Android nativo (fora do escopo deste ambiente).
- `api_routes.py` (Fase 9): funcoes puras (`get_dashboard`, `get_trades`,
  `get_metrics`, `get_risk`, `get_equity`) prontas para um framework HTTP
  futuro. **Nenhum servidor HTTP e iniciado** — decisao de seguranca
  documentada (abrir porta na VPS e mudanca de superficie de rede, fora
  do escopo desta RFC).
- `main.py`: hook unico de consolidacao ao fim de cada ciclo (export de
  trades, metricas, diario, curva de banca), protegido por try/except
  (fail-safe — erro aqui nunca derruba o ciclo de scan). Zero mudanca em
  Scanner, Decision Engine, Consensus, Confluence, Hard Gates, Thresholds.
- 64 testes novos (`TESTS/test_analytics_*.py`, um arquivo por fase).
  Suite completa: 149/149 passando, zero regressao.

## [19.4.0] - 2026-07-12
### Added — Diagnostico Avancado V7.0 (ferramenta de auditoria institucional)
- Novo modulo `ENGINE/diagnostic/advanced_report.py`, somente-leitura sobre
  dados ja calculados por `DiagnosticEngine`/`DecisionEngine` — nao altera
  Decision Engine, gates, thresholds, scoring ou Paper Trading.
- `DiagnosticReport.decisions`: snapshot completo de cada `SignalDecision`
  do ciclo (`sd.to_dict()`), populado por `main.py` via novo
  `DiagnosticEngine.record_decision()`.
- 10 blocos: Resumo do Scanner, Funil Granular (por gate real: RVOL, ADX,
  Estrutura, Entry Zone, Quality, Consensus, Confidence, Kalman, Risk/RR —
  ver nota de fidelidade abaixo), Top Quase-Aprovados, Diagnostico por
  Ativo, Ranking de Bloqueadores, Saude do Mercado, Recomendacao
  Automatica, Resumo Executivo, Estatisticas Gerais.
- Nota de fidelidade: RSI/ATR/Liquidez/Volume nao sao gates independentes
  com flag propria no DecisionEngine atual (alimentam scores compostos) —
  o funil granular usa apenas os gates reais (`*_ok`), evitando diagnostico
  ficticio.
- `TelegramDiagnosticFormatter.format_advanced()`, gated por
  `TELEGRAM_SEND_ADVANCED_DIAGNOSTICS` (default `false`).
- 19 testes novos (`TESTS/test_diagnostico_avancado_v7.py`), incluindo teste
  de nao-mutacao (modulo comprovadamente somente-leitura).

### Added — RFC V19.3: Prioridade Dinamica do Scanner
- Novo `PRIORITY_SCORE` (`ENGINE/scanner/priority_score.py`) usado
  EXCLUSIVAMENTE para reordenar a fila de varredura do scanner a cada
  ciclo — nao afeta Score Institucional, Confidence, Quality, Hard Gates,
  Decision Engine ou gestao de risco.
- Fonte de dados: ticker 24h em lote (`get_ticker_24h_snapshot()`, reaproveita
  a MESMA chamada bulk `/api/v3/ticker/24hr` ja usada em `get_symbols()` —
  zero chamadas de API novas por par) + cache de indicadores (RVOL, ADX,
  ATR%, momentum) do ciclo anterior (sem recalculo).
- Lista VIP configuravel via `SCANNER_VIP_PAIRS` (.env, bonus +20).
- Bonus para sinal aprovado recentemente via novo
  `SignalTracker.get_recently_approved_pairs()` (leitura apenas).
- Blacklist temporaria (RVOL/volume muito baixos vao para o fim da fila,
  nunca sao excluidos do scan).
- Divergencia documentada do prompt original: spread/liquidez real nao sao
  instrumentados no pipeline atual (valor fixo 0.0 em todo o codebase) —
  usa volume 24h como proxy, documentado como limitacao conhecida.
- Reescaneamento dos top 20 (pedido no prompt original) implementado como
  feature opcional `SCANNER_HOT_RESCAN_ENABLED` (default `false`), pois
  aumentaria chamadas de API/tempo de ciclo — decisao do usuario mantida
  desligada por padrao.
- 17 testes novos (`TESTS/test_priority_score_scanner.py`).
- Suite completa: 85/85 testes passando (49 preexistentes + 19 do
  Diagnostico Avancado V7.0 + 17 desta RFC), zero regressao.
- **Pendente (Diretriz Permanente):** RFC requer Paper Trading real com
  comparacao de metricas (Win Rate, sinais capturados a tempo) antes de
  ser considerada concluida — implementacao e testes aprovados, validacao
  de performance real em andamento.

## [19.2.0] - 2026-07-12
### Fixed — Estabilidade do AuditEngine (RFC V19.2)
- **Causa raiz de queda silenciosa do processo**: `audit_engine.py` criava uma
  thread do SO por sinal rejeitado (`threading.Thread(...).start()` em
  `main.py`), sem pool nem limite. Em poucas horas, ~34.000 sinais processados
  geraram ~34.000 threads, cada uma reescrevendo o arquivo `blockers.json`
  inteiro (leitura + append + rewrite completo, O(n) por chamada). Suspeito
  principal da exaustão de memória que derrubou o processo `quantos` sem
  traceback em 2026-07-12 13:16.
- `AuditEngine` reescrito: fila interna (`queue.Queue`) consumida por um único
  worker thread (`threading.Thread` único, criado uma vez no `__init__`), sem
  criação de thread por evento.
- `_safe_write` substituído por `_append_line`: grava uma linha JSON por
  evento (formato JSON Lines) em vez de reescrever o arquivo inteiro —
  operação O(1) por chamada.
- Rotação automática por tamanho (`rotate_bytes`, default 5 MB) para
  `blockers.jsonl` e demais arquivos recorrentes, evitando crescimento
  ilimitado. Nomes de rotação usam timestamp com microssegundos + sufixo
  incremental para evitar colisão (`WinError 183` em rotações no mesmo
  segundo, no Windows).
- `main.py`: removidas as duas chamadas `threading.Thread(target=audit.log_blocker, ...).start()`
  (linhas 523 e 586), substituídas por chamada direta `audit.log_blocker(...)`.
  Import morto de `threading` removido.
- Arquivos de saída renomeados de `.json` (array) para `.jsonl` (linhas):
  `MEMORY/audit/blockers.jsonl`, `MEMORY/paper_trading/cycles.jsonl`,
  `MEMORY/paper_trading/trades.jsonl`. Nenhum consumidor dependia do formato
  anterior (verificado via busca no código).
- Nenhuma alteração em lógica de sinais, gates, thresholds ou scoring.
- 7 testes novos (`TESTS/test_audit_engine_estabilidade.py`): sem thread por
  chamada, append-only, rotação, fail-safe silencioso, e verificação de que
  `main.py` não volta a usar thread por evento. Suite completa: 49/49 testes
  passando (42 anteriores + 7 novos), sem regressão.
- Homologação: processo reiniciado localmente, observado por ~16 min / 9
  ciclos de scan completos, memória e contagem de threads estáveis
  (sem crescimento), sem crashes.

## [19.0.0] - 2026-07-12
### Added — Classificação Fixa (V19.0)
- Tabela de classificação com ranges fixos e exclusivos: BRONZE(60-69), PRATA(70-79), OURO(80-89), DIAMANTE(90-100)
- Validação pós-classificação: score REALMENTE dentro da faixa
- Requisitos mínimos por classificação: RR, consenso, confiança

### Added — Expectativa Multi-Fator
- Nova `compute_expectancy_level()` com 11 fatores (Qualidade, Confiança, Consenso, Estrutura, Liquidez, Momentum, Risco, Tendência, Kalman, ATR, Volatilidade)
- Resultados: Baixa, Média, Alta, Muito Alta
- Pesos calibrados via EXPECTANCY_WEIGHTS

### Added — Penalizações com Origem e Peso
- Dataclass `Penalty` com reason, weight, source
- 11 tipos de penalização (ATR elevado, estrutura fraca, liquidez insuficiente, RVOL baixo, contra tendência, Kalman contrário, próximo de resistência/suporte, mercado lateral, spread elevado, baixo consenso)
- Cada penalização exibe peso no Telegram

### Added — Gate de Tendência (Gate 13)
- Rejeita LONG contra Trending_Down + Kalman DOWN
- Rejeita SHORT contra Trending_Up + Kalman UP
- Permite exceção apenas com CHOCH + BOS + volume + consenso confirmados

### Added — Retorno Operacional Padronizado
- 12 campos: preco_entrada, preco_tp, preco_stop, retorno_ativo_pct, retorno_margem_pct, retorno_patrimonio_pct, lucro_liquido_usdt, perda_maxima_usdt, valor_nominal, margem_utilizada_usdt, quantidade, alavancagem_efetiva

### Added — Estatísticas Avançadas Paper Trading
- Win Rate por classificação (`win_rate_by_classification`)
- Win Rate por símbolo (`win_rate_by_symbol`)
- Win Rate por timeframe (`win_rate_by_timeframe`)
- Win Rate LONG/SHORT
- Sharpe Ratio, Payoff
- Tempo médio até TP e Stop
- Motivos de perda e ganho

### Added — Autoaprendizado com Limites
- `LEARNING_MIN_SAMPLES = 100` para recalibração
- `LEARNING_MIN_SAMPLES_PER_CLASSIFICATION = 20`
- Fontes restritas a Paper Trading apenas

### Changed — Pesos de Qualidade (SCORE_WEIGHTS)
- structural: 0.10 → 0.14
- confidence: 0.08 → 0.12
- flow: 0.12 → 0.08
- timing: 0.10 → 0.06

### Changed — Índice Geral (OVERALL_SCORE_WEIGHTS)
- Novos pesos: quality 0.20, confidence 0.15, consensus 0.12, structure 0.10, liquidity 0.10, momentum 0.10, trend_alignment 0.08, kalman_alignment 0.08, risk_inverted 0.07
- Substituído entry_zone e risk_reward por momentum e risk_inverted

### Changed — Layout do Telegram
- Blocos reorganizados: Header → Classificação e Qualidade → Convicção e Expectativa → Preços → Operacional → Análise → Auditoria
- Penalizações exibidas com peso
- Indicadores financeiros padronizados

## [18.3.0] - 2026-07-11
### Added - Trade Registry (SQLite)
- `ENGINE/common/trade_registry.py`: SQLite-backed trade database com 31 campos
- `open_trade()`: registro automático de toda operação enviada (signal_id, asset, timeframe,
  direction, entry, stop, tp1-2, quality, confidence, overall_score, consensus,
  conviction, expectancy, trend, kalman, classification, RR, leverage, account_size,
  capital_per_trade, collateral, position_value, profit_est, loss_est)
- `close_trade()`: registro de resultado (WIN/LOSS/BREAKEVEN) com exit_price, time_to_tp1,
  time_to_stop, lucro_usdt, perda_usdt, retorno_pct, MAE, MFE, R-multiple

### Added - Estatísticas Automáticas
- Win Rate, Profit Factor, Drawdown, Payoff, Expectancy
- Média de Quality, Confidence, Overall Score, Consensus, RR
- Gross/Net P&L

### Added - Estatísticas por Categoria
- Por classificação (BRONZE/SILVER/GOLD/PLATINUM/DIAMOND): total, wins, losses, WR, avg retorno
- Por timeframe (30m/1h/4h/1D): total, wins, losses, WR, avg retorno
- Por direção (LONG/SHORT): total, wins, losses, WR, avg retorno

### Added - Ranking de Setups
- Combinações Trend+Kalman (ex: Trend_UPTREND+Kalman_UP)
- Win Rate, Profit Factor, total trades, avg retorno, avg overall score
- Filtro mínimo de trades configurável

### Added - Análise das Derrotas
- Para cada LOSS: identificação do gate mais fraco (Quality, Confidence, Consensus, OS, RR)
- Ranking dos motivos de perda com contagem e percentual
- Thresholds de referência: Quality≥0.70, Confidence≥0.75, Consensus≥0.70, OS≥75, RR≥2.0

### Added - Relatório Semanal
- Período de 7 dias: total ops, WR, PF, Drawdown, Retorno, Expectancy
- Melhor/Pior Ativo, Timeframe e Classificação
- Breakdown por classificação, timeframe e direção
- Top motivos de perda

### Changed
- `main.py`: integração TradeRegistry.open_trade() após aprovação de sinal
- `main.py`: integração TradeRegistry.close_trade() no check_exits do PaperTradingEngine
- `core/trading/paper_trading.py`: suporte a PaperTrade.position_value para PnL em USDT

## [18.2.0] - 2026-07-11
### Added - Overall Score (Índice Geral)
- Novo composite score 0-100: Quality (18%), Confidence (14%), Consensus (12%), Trend Alignment (10%), Kalman Alignment (10%), Structure (10%), Liquidity (8%), Smart Money (6%), Entry Zone (6%), Risk/Reward (6%)
- Barra de progresso visual `[████████░░]` no cartão Telegram
- Classificação automática: DIAMOND (95+), PLATINUM (90-95), GOLD (85-90), SILVER (75-85), BRONZE (60-75), REJEITADO (<60)
- Função `compute_overall_score()` em `ENGINE/common/operational.py`

### Added - Setup Strength (Força do Setup)
- Probabilidade: derivada do Overall Score
- Nível de Convicção: Muito Alta (avg≥0.85), Alta (≥0.70), Moderada (≥0.55), Baixa (<0.55)
- Expectativa: combinando Overall Score + RR (Alta/Moderada/Baixa)
- Tempo Estimado p/ TP1: derivado do timeframe + força da tendência

### Added - Bloco Operacional com Retorno %
- Retorno Esperado (TP1) em percentual sobre capital alocado
- Capital por Trade, Alavancagem, Lucro/Perda em USDT e %

### Added - Análise Institucional Reformulada
- Qualidade, Confiança, Consenso, Classificação
- Tendência, Kalman, RVOL, ADX, ATR, Fluxo, Estrutura, Liquidez

### Added - Rodapé de Auditoria
- Signal ID único, Versão do Motor (V18.2), Nº do Ciclo
- Tempo de processamento (ms), Timestamp UTC

### Added - Dashboard Metrics (summ.json)
- `record_trade_outcome()` para registrar resultados de trades (WIN/LOSS)
- Win Rate, Profit Factor, Drawdown, Net P&L
- Médias: Overall Score, Quality, Confidence, Consensus, Retorno
- Expectancy (avg win * WR - |avg loss| * (1-WR))
- Persistência em summary.json com rolling log de até 1000 trades

### Changed
- `telegram_formatter.py`: rewrite completo para layout V18.2 (9 blocos)
- `main.py`: injeção de overall_score, conviction_level, expectancy_level, time_to_tp1
- `signal_compat.py`: pass-through dos novos campos
- `ENGINE/diagnostic/engine.py`: DiagnosticReport com trade_outcomes, novos métodos dashboard
- `telegram_diagnostic_formatter.py`: bloco de dashboard metrics no relatório

## [18.1.0] - 2026-07-11
### Added - Novo Cartão de Sinal Profissional
- Layout reordenado: ENTRADA → TP1 → STOP LOSS (primeira linha operacional)
- Bloco de capital: Capital da Conta (via .env QUANTOS_ACCOUNT_SIZE)
- Cálculo automático: valor da operação, alavancagem, colateral, posição total
- Lucro estimado (TP1) e Perda Máxima (Stop) em USDT e percentual
- Risk/Reward na aba de valores operacionais
- Bloco de Qualidade, Confiança, Classificação, Tendência, Kalman
- Bloco de métricas: ADX, RVOL, ATR, Fluxo Institucional
- Motivos da Aprovação em bullet points (até 8)
- Penalizações em bullet points (até 4), apenas as realmente aplicadas

### Added - Alavancagem Inteligente (V18.1)
- Qualidade 95-100 → 25x | 90-94 → 22x | 85-89 → 20x | 80-84 → 18x
- Qualidade 75-79 → 15x | 70-74 → 12x | 65-69 → 10x | 60-64 → 8x
- Mínimo 8x, máximo 25x (configurável via QUANTOS_LEVERAGE_MAX)
- Capital por operação = 30% do Account Size (configurável)

### Added - Gerenciamento de Capital
- QUANTOS_ACCOUNT_SIZE no .env (default: 200 USDT)
- OperationalCalculator em ENGINE/common/operational.py
- Nenhum valor fixo no código — tudo via .env

### Added - Pipeline Telemetry (Funil de Gates)
- Rastreamento ativos_analisados → API → Candles → Indicadores → Estrutura
- Smart Money → Entry Zone → Consensus → Quality Gate → Decision Engine → Aprovados
- Exibição no diagnóstico Telegram com contagem de bloqueados por estágio
- Registro em pipeline_funnel no relatório do ciclo

### Added - Auditoria por Sinal
- Signal ID, Cycle ID, Engine Version, Processing Time
- Scores completos (quality, confidence, consensus, institutional, etc.)
- Status de cada gate (rvol_ok, adx_ok, structure_ok, entry_zone_ok, etc.)
- Penalty reasons aplicados

### Fixed - Pipeline Incompleto (causa raiz)
- DiagnosticEngine._record_final_decision_from_audit gerava falsos "Pipeline Incompleto"
- para TODOS os ativos sem sinal (~500/ciclo), pois eles param naturalmente em
- "estrutura" (sem entry_zone/consensus/decisao_final por design).
- Sintomas: bugs=500+ por ciclo → Health=0%, Dashboard inconsistente.
- Corrigido: ativos que param em estágios iniciais (carregamento/api/candles/
- indicadores/estrutura) recebem status "Sem sinal (filtro em: X)" em vez de
- "Pipeline Incompleto", sem gerar bug.

### Fixed - Silent Drops (falsos positivos)
- detect_silent_drops ignorava ativos sem sinal (param em estágios iniciais)
- Agora só considera silent drop real se o ativo passou de "estrutura"
- e desapareceu sem decisão final.

### Changed - Penalty Reasons
- generate_penalty_reasons() em scanner_signal.py detecta automaticamente:
  ATR elevado, Risco elevado, Kalman baixa confiança, Mercado lateral,
  Estrutura indefinida, Liquidez abaixo do ideal, Momentum fraco
- Penalty reasons propagadas via Signal → SignalDecision → to_dict() → Telegram

## [17.8.0] - 2026-07-11
### Fixed (segunda causa raiz — sinais aprovados bloqueados silenciosamente na validacao)
- Mesmo apos corrigir `_on_decision` ([17.7.0]), sinais aprovados (`DEDUP: ..._novo_sinal`) continuavam sem chegar ao Telegram, sem nenhum erro logado. Causa: `SERVICES/telegram/telegram_validator.py`'s `validate_consistency()` exigia 18 campos `_ok` de um DecisionEngine V10 ja removido (`market_ok`, `trend_ok`, `institutional_ok`, `confidence_ok`, `risk_ok`, `flow_ok`, `timing_ok`, `liquidity_ok`, `structural_ok`, `conviction_ok`). O DecisionEngine atual (8 hard gates, pos RFC_SIMPLIFICACAO.md) so define 8 desses campos; os outros 10 ficam `None` (default da dataclass `SignalDecision`) e nunca sao computados. `not None` avalia `True`, entao a funcao sempre retornava `False` e `_format_and_queue()` saia silenciosamente (`if not validate_consistency(data): return`, sem log) — todo sinal aprovado era descartado sem deixar rastro.
- Corrigido: `ok_fields` reduzido aos 8 campos que o motor atual realmente define (`rvol_ok`, `adx_ok`, `structure_ok`, `entry_zone_ok`, `entry_score_ok`, `quality_ok`, `consensus_ok`, `rr_ok`).
- Testado com o shape real de `SignalDecision.to_dict()` de um sinal aprovado (GSONUSDT): `validate_consistency` agora retorna `True` (antes retornava `False` sempre, para qualquer sinal).
- pm2 `quantos` reiniciado para carregar a correcao. Esta e provavelmente a causa raiz completa (junto com [17.7.0]) de nenhum sinal do DecisionEngine interno ter chegado ao Telegram do usuario ate agora — os envios `200 OK` anteriores (14:30-17:21) vieram de outra origem (provavelmente `BOTS/mexc/signals/signal_receiver.py`, sinais externos via `signal.generated`, nao investigado a fundo por estar fora do escopo desta correcao).

## [17.7.0] - 2026-07-11
### Fixed (bug critico — sinais aprovados nunca chegavam ao Telegram)
- `main.py` publica sinais aprovados via `Publisher.decision_made(data)` (evento `"decision.made"`), correto e necessario pois `BOTS/mexc/bot_engine.py` tambem escuta esse mesmo evento para executar a trade. Porem `SERVICES/telegram/telegram_service.py`'s `_on_decision` (handler de `"decision.made"`) era um **stub incompleto**: so verificava uma env var e dava `pass`, nunca formatando nem enviando nada. A logica real de formatacao/validacao/envio so existia em `_on_signal`, ligado ao evento `"signal.generated"` — que o pipeline atual (pos-simplificacao) nunca publica para sinais aprovados pelo DecisionEngine.
- Resultado: sinais passavam em todos os hard gates, passavam no dedup do `SignalTracker` (`DEDUP: ..._novo_sinal`), mas nunca chegavam ao Telegram — sem nenhum erro visivel, porque `_on_decision` retornava silenciosamente.
- Corrigido: extraida a logica comum de `_on_signal` para `_format_and_queue()`, agora usada tanto por `_on_signal` quanto por `_on_decision`. Confirmada compatibilidade de dados: `SignalDecision.to_dict()` ja inclui `pair` e todos os campos `_ok` (`quality_ok`, `rvol_ok`, `consensus_ok` etc.) que `telegram_validator.validate_consistency()` exige.
- Removido import morto de `os` em `telegram_service.py` (so era usado pelo stub removido).
- pm2 `quantos` reiniciado para carregar a correcao.

## [17.6.0] - 2026-07-11
### Fixed (sinais reais sendo perdidos no envio ao Telegram)
- `SERVICES/telegram/telegram_formatter.py` inseria texto dinamico (simbolo, `approval_reasons`) sem escapar caracteres especiais do `parse_mode='Markdown'` do Telegram. Motivos como `adx_muito_alto_possivel_exaustao` tem varios `_`; com contagem impar de `_`/`*`/`` ` ``/`[` na mensagem inteira, o Telegram responde `400 Bad Request: Can't parse entities: can't find end of the entity` e o sinal e descartado apos 3 tentativas (confirmado em `quantos.log` as 16:42:56-16:43:03).
- Confirmado via `grep` em `quantos.log` que **sinais reais ja foram enviados com sucesso (`200 OK`)** em varios horarios do dia (14:30, 15:05, 15:35, 16:09, 17:04, 17:11, 17:16, 17:21) — o bug so afeta sinais cujo texto de motivos tem numero impar de caracteres especiais, nao todos.
- Corrigido: adicionada `_escape_markdown()` e aplicada a todo texto dinamico (`symbol`, `timeframe`, `trend`, `kalman_direction`, `classification_label`, cada item de `approval_reasons`). Testado: mensagem com motivos contendo multiplos `_` agora sai com 0 caracteres especiais sem escape.
- pm2 `quantos` reiniciado para carregar a correcao.

## [17.5.0] - 2026-07-11
### Fixed (operacional — multiplas instancias concorrentes)
- Encontradas 3 instancias de `main.py` do QuantOS rodando simultaneamente (fora do controle do pm2, iniciadas manualmente por engano), competindo pelos mesmos arquivos de `MEMORY/audit/` e pela mesma cota de rate-limit da MEXC. Sintomas observados: `[AuditEngine ERROR] Falha ao gravar logs: [Errno 22] Invalid argument: 'MEMORY/audit/blockers.json'` (conflito de escrita concorrente) e `429 Client Error: Too Many Requests` da MEXC em volume.
- As 3 instancias soltas foram encerradas. A unica instancia legitima e gerenciada pelo pm2 (app `quantos`) foi reiniciada limpa.
- Confirmado: com apenas uma instancia rodando, os erros 429 pararam de aparecer nos logs.
- Identificado que o processo pm2 usa um snapshot de ambiente proprio (`QUANTOS_MODE=DEVELOPMENT`, `QUANTOS_MAX_SCAN_PAIRS=500`), independente do arquivo `.env` (que tem `LIVE`/`300`) — `load_dotenv()` nao sobrescreve variaveis ja definidas no ambiente do processo, entao o `.env` nunca chega a alterar esta instancia especifica. Mantido assim a pedido do usuario (configuracao estavel e segura: DEVELOPMENT = sem risco de autenticacao/ordem real).

### Validation
- Ciclo real com 500 pares, instancia unica, pos-fixes: `PROFILING ciclo #2: 82.3s total | 500 pares | candles=687.84s(avg=1375.68ms)`.
- Sinal real aprovado em todos os gates: `GSONUSDT 1d long | rvol=True adx=True struct=True entry_zone=True entry_score=True quality=True consensus=True rr=True | APROVADO`. Nao reenviado ao Telegram por dedup (`sem_mudancas_relevantes` — sinal identico ja registrado antes), comportamento correto do SignalTracker, nao um bug.

## [17.4.0] - 2026-07-11
### Fixed (bug critico de ordem de import — .env parcialmente ignorado)
- `main.py` nao chamava `load_dotenv()` no topo do arquivo. O `.env` so era carregado dentro de `BOTS/mexc/bot_config.py`, importado bem depois de `ENGINE/scanner/scanner_config.py` e `CORE/data_providers/mexc_provider.py` na cadeia de imports de `main.py`. Esses dois modulos leem `os.getenv(...)` no nivel de modulo (no momento do import), entao `QUANTOS_MAX_SCAN_PAIRS`, `QUANTOS_MEXC_MAX_CONCURRENT`, `QUANTOS_SCAN_MAX_WORKERS` e `QUANTOS_DISCOVERY_MODE` definidos no `.env` eram **sempre ignorados silenciosamente**, caindo nos defaults hardcoded (`MAX_SCAN_PAIRS=50` etc.), mesmo com o `.env` configurado corretamente.
- Confirmado com teste real: `.env` com `QUANTOS_MAX_SCAN_PAIRS=300` resultava em `Discovery AUTO: 50 / 1308 USDT pairs (limit: 50)` no log — o valor do `.env` nunca chegava a ser lido.
- Corrigido: `load_dotenv()` movido para a primeira linha executavel de `main.py`, antes de qualquer import de projeto.
- Este era provavelmente a causa raiz de por que ajustes de `MAX_SCAN_PAIRS` via `.env` nunca surtiam efeito em producao, contribuindo para a cobertura do scanner ficar presa em 50 pares mesmo quando reconfigurada.

### Validation
- `QUANTOS_MAX_SCAN_PAIRS=300` no `.env`: antes da correcao, log mostrava `Discovery AUTO: 50/1308 (limit: 50)`; depois, `Discovery AUTO: 300/1308 (limit: 300)`.
- Ciclo real completo com 300 pares (modo DEVELOPMENT, sem chaves MEXC, apos a correcao de Session HTTP do [17.3.0]): ciclo #1 = 92.8s (candles 1.92s/par media), ciclo #2 = 200.9s (candles 1.45s/par media). Projecao anterior para 500 pares era de 20-30min; equivalente agora fica na casa de poucos minutos.
- Observado um alerta transitorio do watchdog ("scanner NAO RESPONDE, tentativa 1/3") nos primeiros segundos apos o start, antes do primeiro heartbeat do scan loop — nao escalou a restart desta vez (ficou em 1/3), mas e o mesmo padrao de falso-positivo por timing de heartbeat descrito como problema recorrente. Registrado para investigacao futura (reforma do Watchdog/Health ainda pendente).

## [17.3.0] - 2026-07-11
### Added
- `ENGINE/diagnostic/cycle_profiler.py` — mede tempo real por etapa do pipeline (candles, indicadores, scanner, decisao_risco, telegram) por ciclo, gravando resumo em `MEMORY/profiling/cycle_<n>.json`. Instrumentado em `main.py` (`_fetch_and_scan`, `_process_scan_result`, `_scan_loop`) sem alterar nenhuma logica de negocio.

### Fixed (gargalo de performance identificado via profiling)
- `CORE/data_providers/mexc_provider.py`: `_fetch_klines`, `get_symbols` e `get_symbol_ticker` criavam uma conexao HTTP nova (`requests.get()`) a cada chamada. Medido: candles = ~34s/par em media (~99% do tempo de ciclo), enquanto indicadores+scanner+decisao somados custavam <1s para 5 pares. Isolado com teste direto: 1a chamada a `/klines` leva ~10s, chamadas seguintes com `Session` reutilizada levam ~0.3s (30x). Corrigido: `MexcDataProvider` agora mantem uma `requests.Session()` com `HTTPAdapter(pool_maxsize=MAX_CONCURRENT_REQUESTS)` reutilizada entre todas as chamadas.
- **Resultado medido** (5 pares, mesmo ambiente, antes/depois): candles 170.7s→22.1s total (34.132ms→4.412ms/par, ~7.7x), ciclo completo 42.1s→5.9s (~7.1x). Projecao para 50 pares: ~3min→~22s. Para 300-500 pares: ~20-30min (estimativa anterior do watchdog) → ~2-4min.
- Este era o gargalo real por tras da reducao de cobertura do scanner e das reinicializacoes do watchdog — nao excesso de modulos/logica, mas conexao HTTP recriada sem necessidade.

## [17.2.0] - 2026-07-11
### Removed (finalização do RFC_SIMPLIFICACAO.md)
- `ENGINE/execution/paper_engine.py` — movido para `archive/`: duplicava `CORE.trading.paper_trading` (o motor de paper trading em uso real).
- `CORE/utils/helpers.py`, `.lifecycle.py`, `.timer.py`, `.validators.py` — movidos para `archive/`: nunca importados por nenhum módulo alcançável a partir de `main.py`. `CORE/utils/timeframe_manager.py` (em uso) permanece no lugar.

### Fixed (regressões descobertas na homologação pós-arquivamento)
- `CORE/bootstrap/startup.py` importava `CORE.errors.handlers`, mas `CORE/errors/` havia sido arquivado numa etapa anterior do mesmo RFC — o bot não conseguia nem importar `main.py`. Restaurado `CORE/errors/exceptions.py` e `CORE/errors/handlers.py` (únicos arquivos realmente usados; `error_codes.py`, `recovery.py` e `validators.py` permanecem em `archive/`, sem importadores).
- `ENGINE/watchdog/watchdog_integration.py` registrava um monitor para o módulo `"mid"` (MIDashboard), removido pelo próprio RFC ("substituído por logs estruturados"), mas a integração do watchdog nunca foi atualizada. `_check_mid` sempre retornava `False` (nada seta `app._mid`), então o watchdog tentava reiniciar um módulo inexistente (`ENGINE.mid.mid_dashboard`) indefinidamente a cada ciclo, gerando erro e alerta recorrentes (não derrubava o processo, pois `Watchdog._loop` captura a exceção). Removido o registro `"mid"`, `_check_mid()` e o branch de restart correspondente.
- `ENGINE/validation/health_check.py` e `SERVICES/telegram/telegram_sender.py` procuravam `.env` em `TELEGRAM/.env` (pasta arquivada, substituída por `SERVICES/telegram/`). Bot não subia: `FileNotFoundError`. Corrigido para `.env` na raiz do projeto. Valores de `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` (vazios no `.env` atual) foram copiados do `TELEGRAM/.env` arquivado.

### Validation
- Grafo de dependências (AST, alcançabilidade a partir de `main.py`/`run.py`): 85 módulos alcançados antes e depois das remoções — nenhuma regressão.
- `python -m py_compile` nos arquivos tocados: OK.
- Boot completo de `QuantOSApp` (health check, startup, todos os engines, Telegram, watchdog, paper trading, discovery de símbolos reais via MEXC): sem exceções, 50 símbolos descobertos.
- Aviso não-bloqueante identificado, não corrigido nesta mudança (decisão do usuário, toca modo de execução): `.env` tem `QUANTOS_MODE=PRODUCTION`, mas `CORE/execution/mode_manager.py` só reconhece `DEVELOPMENT`/`PAPER_TRADING`/`LIVE` — cai em fallback seguro (`DEVELOPMENT`, dry-run).

## [17.1.0] - 2026-07-11
### Changed
- Recalibrados os gates operacionais para a escala real do scanner atual.
- `DecisionBrain` em estado `PRONTO` agora permite aprovacao controlada quando todos os hard gates, RR, precos e self-audit passam.
- Mantidos bloqueios para `OBSERVACAO`, `REJEITADO`, consenso insuficiente, RR invalido, precos invalidos e self-audit falho.

### Validation
- Testes direcionados: `python -m pytest TESTS/test_decision_engine_v10.py TESTS/test_decision_engine_minimal_fixes.py TESTS/test_scanner.py` -> 13 passed.
- Validacao real MEXC: `67USDT 4h short` aprovado com hard gates e self-audit aprovados.

## [2.3.0] - 2026-07-05
### Added
- FASE 04 — ENGINE: SCANNER INSTITUCIONAL completa
- ENGINE/scanner/ module (10 arquivos, 1146 linhas)
- Análise SMC completa: BOS, CHoCH, Order Blocks, FVG, Liquidity Sweep
- Market Structure (HH/HL, LH/LL, MM50, MM200, VWAP)
- 8 scores (Institutional, Structural, Market, Momentum, Liquidity, Risk, Confidence, Quality)
- Classificação: OURO SUPREMO, OURO, PRATA, BRONZE, REPROVADO
- Quality Gate integrado (6 gates de validação)
- Signal Builder com entry, SL, TP1, TP2, RR
- Multi-timeframe scanning (5 timeframes simultâneos)
- Multi-pair scanning
- 48 novos testes (500 totais, 100% passando)
- Integração total com Market Intelligence
- Performance: scan completo em <10ms por par

## [2.2.0] - 2026-07-05
### Added
- FASE 03 — KNOWLEDGE completa
- CORE/knowledge/ module (9 arquivos, engine completa)
- KNOWLEDGE/ data directory (7 áreas de conhecimento)
- 40 novos testes (371 totais)
- Doc 053 (KNOWLEDGE_ENGINE.md)

### Added
- FASE 04 — ENGINE: MARKET INTELLIGENCE completa
- ENGINE/market/ module (12 arquivos, 1003 linhas)
- Market Engine: análise completa de mercado (21 capacidades)
- Análise de tendência (ADX, EMA alignment, slope)
- Análise de momentum (RSI, RVOL)
- Análise de volatilidade (ATR, Bollinger Bands)
- Análise de liquidez (spread, funding, volume)
- Classificação de regime (trending, ranging, volatile, reversal, calm)
- Correlação (BTC, ETH, dominância)
- 8 scores (Market, Trend, Momentum, Volatility, Liquidity, Risk, Confidence, Institutional)
- Contexto Multi Timeframe
- 81 novos testes (452 totais, 100% passando)
- 8 spec docs (054-061)
- ENGINE/decision/ directory criado

## [2.1.0] - 2026-07-05
### Added
- FASE 02 — MEMORY completa
- CORE/memory/ module (11 arquivos, engine completa)
- MEMORY/ data directory persistente
- LessonRegistry: lições aprendidas imutáveis
- ImprovementLog: histórico de melhorias aprovadas/rejeitadas
- ParameterHistory: parâmetros vencedores/perdedores
- BacktestRecords: resultados de backtests com métricas
- ChangeLog: change tracking automático
- MemoryQuery: busca textual e filtros
- FileStore: persistência JSON com coleções
- DNAUpdater: atualização programática do PROJECT_DNA
- 56 novos testes (331 totais, 100% passando)

## [2.0.0] - 2026-07-05
### Changed
- Implementação COMPLETA do CORE (produção)
- Logger: singleton removido, agora usa stdlib logging
- Encryption: algoritmo real (Fernet/cryptography)
- Token Manager: tokens seguros via secrets.token_hex
- Todos os stubs substituídos por implementações reais
- Todos os __init__.py com exports explícitos
- Todas as funções com type hints, docstrings, error handling
- datetime.utcnow() substituído por datetime.now(timezone.utc)
- Injeção de dependência em todos os gerenciadores

### Added
- Testes unitários: 275 testes, 22 módulos, 100% passando
- audit_rules.py criado (arquivo faltante crítico)
- setup_logging() para configuração centralizada
- Backup: suporte a persistence backends

## [1.1.0] - 2026-07-05
### Added
- Milestone 02 - CORE ENGINE completa
- 10 documentos de implementação (041-050)
- 8 novos módulos CORE (155 arquivos totais)
- Config Validation, Version Manager, Baseline Manager
- Audit Engine, Metrics Engine, Security, Permission
- Resource Manager, Cache Manager, Scheduler
- Task Manager, State Manager, Notification Manager
- Documento 050 Final Review aprovado
- Auditoria PACOTE 03 aprovada (doc 051)

## [1.0.0] - 2026-07-05
### Added
- Milestone 01 - FOUNDATION completa
- 20 documentos oficiais de governança, arquitetura e padrões
- Estrutura de diretórios do repositório
- Sistema de governança (Governor, Guardian, Engineering Council)
- Padrões de código e interface contracts
- Base oficial de conhecimento
- Fluxo de desenvolvimento e processo de construção
