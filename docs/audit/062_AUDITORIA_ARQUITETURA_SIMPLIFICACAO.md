# 062 — Auditoria Completa de Arquitetura (Missão Simplificação)

**Data:** 2026-07-11
**Fase do processo:** Fase 1 (RFC) / Fase 5 (Auditoria) — nenhuma remoção foi executada ainda.
**Objetivo:** Classificar todos os arquivos do QuantOS em ESSENCIAL / IMPORTANTE / OPCIONAL / OBSOLETO, mapear dependências e propor uma arquitetura limpa: Scanner → Candles → Indicadores → Filtros → Score → Gestão de Risco → Telegram.

## Metodologia

Auditoria manual de 170 arquivos não é confiável nem verificável. Em vez disso:

1. **Grafo de dependências via AST**: parseei todos os `.py` de `ENGINE/`, `CORE/`, `BOTS/`, `SERVICES/`, `TOOLS/` e raiz, resolvendo imports absolutos e relativos (incluindo imports condicionais/lazy dentro de funções).
2. **Alcançabilidade a partir dos pontos de entrada reais**: fiz busca em largura a partir de `main.py`, `run.py` e `audit_engine.py`.
3. **Confirmação de que não há outro ponto de entrada oculto**: `grep` por `if __name__ == "__main__"` em todo o repo. Fora de `archive/` (já isolado por você), os únicos entry points ativos são `main.py`, `run.py` (que só chama `main.py`), `ENGINE/scanner/scanner_config.py` (self-test de config) e `BOTS/mexc/TESTS/test_bot_mexc.py` (teste). **Não existe dashboard, analytics runner ou script separado rodando em produção.**
4. **Corroboração por dados em disco**: cruzei os módulos "nunca importados" com o estado de `MEMORY/` (3589 arquivos). Os diretórios `MEMORY/dna/`, `MEMORY/lessons/`, `MEMORY/institutional/`, `MEMORY/improvements/`, `MEMORY/parameters/`, `MEMORY/recalibration/`, `MEMORY/changes/`, `MEMORY/backtests/` estão **vazios (0 arquivos)** — exatamente os diretórios que o subsistema morto `CORE/memory/*` escreveria. Isso confirma independentemente que esse subsistema nunca rodou. Já `MEMORY/audit/` (3571 arquivos) e `MEMORY/paper_trading.json` estão ativos e recentes — escritos por `audit_engine.py` e `CORE.trading.paper_trading`, ambos no caminho vivo.

Resultado: **170 arquivos totais → 85 alcançáveis a partir de `main.py`, 85 não alcançáveis.** Descontando `__init__.py` triviais (pacotes cujos submódulos são importados diretamente, então o pacote "não alcançado" não significa nada) e 1 arquivo de teste, sobram **57 arquivos / ~5.514 linhas de código genuinamente desconectados da execução real**.

Nota técnica: 2 arquivos (`SERVICES/telegram/telegram_formatter.py` e `SERVICES/telegram/__init__.py`) têm um BOM (U+FEFF) no início, o que quebrou o parser AST do meu script — mas o Python importa esses arquivos normalmente em produção (confirmado, pois `main.py` os usa). Não é um bug funcional, só uma inconsistência de encoding que vale limpar por padronização.

---

## 1. ESSENCIAL — pipeline real em produção (mapeado ao fluxo desejado)

| Etapa do fluxo | Módulos |
|---|---|
| **Conexão com a Exchange** | `BOTS.mexc.exchange.connector`, `.api_manager`, `.auth_manager`, `.websocket_manager` |
| **Candles / Market Data** | `CORE.data_providers` (`base`, `config`, `mock`, `historical`, `mexc_provider`, `binance_provider`), `ENGINE.market.market_engine`, `.market_types` |
| **Indicadores** | `ENGINE.market.market_volatility` (ATR), `.market_trend` (EMA/tendência), `.market_momentum` (RSI), `.market_regime`, `.market_scoring`, `.market_liquidity` (RVOL), `ENGINE.indicators.kalman` |
| **Estrutura (BOS/CHoCH)** | `ENGINE.scanner.scanner_structure`, `.scanner_patterns`, `.scanner_types` |
| **Filtros / Scanner** | `ENGINE.scanner.scanner_engine`, `.scanner_config`, `.scanner_scoring`, `.scanner_ranker`, `.scanner_signal`, `.entry_zone`, `.flex_scoring`, `.ssr` |
| **Score / Decisão** | `ENGINE.decision.decision_engine`, `.signal_decision`, `ENGINE.consensus.consensus_engine`/`consensus_config`, `ENGINE.confluence.confluence_engine`/`confluence_config`, `ENGINE.common.score_normalizer` |
| **Gestão de Risco** | `ENGINE.risk.risk_manager` (cálculo de SL/TP/RR na decisão), `BOTS.mexc.trading.risk_manager` (circuit breaker de execução), `.position_manager`, `.order_manager`, `.execution_engine` |
| **Execução na corretora** | `BOTS.mexc.execution.order_executor`, `.position_monitor`, `.stop_manager`, `.take_profit_manager`, `.trailing_stop_manager`, `.break_even_manager`, `BOTS.mexc.protection.emergency`/`.recovery` |
| **Telegram** | `SERVICES.telegram.telegram_service`, `.telegram_sender`, `.telegram_formatter`, `.telegram_validator`, `.signal_compat`, `BOTS.mexc.notification.engine` (publica eventos internos que o Telegram consome) |
| **Sinais / Dedup** | `ENGINE.signals.signal_tracker`, `BOTS.mexc.signals.signal_receiver`/`.signal_validator` |
| **Infra base** | `CORE.bootstrap.startup`, `CORE.config.settings`/`.environment`/`.constants`, `CORE.events.event_bus`/`.events`/`.publishers`, `CORE.execution.mode_manager`, `CORE.utils.timeframe_manager`, `BOTS.mexc.bot_engine`/`.bot_config`/`.bot_types` |

**Nota sobre "duplicação" que investiguei e descartei:** `ENGINE.risk.risk_manager` e `BOTS.mexc.trading.risk_manager` têm nomes parecidos mas escopos diferentes — o primeiro calcula SL/TP/RR na hora de gerar o sinal (estratégia), o segundo é um circuit breaker de perdas consecutivas na execução ao vivo (operação). Não é duplicação, é responsabilidade única corretamente separada. Da mesma forma, `BOTS.mexc.notification.engine` não compete com o Telegram: ele só publica eventos (trade aberto/TP/stop) no `EventBus`, que o `SERVICES.telegram` consome. Também está correto.

## 2. IMPORTANTE — suporte operacional (alcançado, mas fora do fluxo mínimo que você descreveu)

- `ENGINE.diagnostic.engine` + `audit_engine.py` (grava em `MEMORY/audit/`, ativo e volumoso — 3571 arquivos)
- `ENGINE.watchdog.watchdog` / `.watchdog_integration`
- `CORE.health.health_monitor`
- `CORE.trading.paper_trading`
- `ENGINE.validation.health_check`

Essas peças não fazem parte do fluxo "Scanner→Candles→Indicadores→Filtros→Score→Risco→Telegram" que você pediu para manter como núcleo, mas são redes de segurança operacionais (saúde do processo, paper trading, auditoria de decisões). **Decisão precisa ser sua**: mantenho como estão, ou você quer que eu avalie se algum pode ser cortado/simplificado numa próxima RFC?

## 3. OPCIONAL — pode ser removido sem afetar a estratégia

- **Pastas vazias, zero arquivos**: `BOTS/binance/`, `BOTS/bybit/`, `BOTS/future/` (stubs de exchanges nunca implementadas), `TOOLS/`, `KNOWLEDGE/`, `LAB/`, `CONFIG/`, `DATA/`, `LOGS/` — puro scaffolding sem conteúdo algum.
- `CORE.utils.helpers` (19 linhas), `.lifecycle` (63), `.timer` (36), `.validators` (22) — utilitários genéricos nunca importados por ninguém no caminho vivo.

## 4. OBSOLETO — código morto confirmado (57 arquivos, ~5.514 linhas)

Nenhum destes é importado, direta ou indiretamente, a partir de `main.py`/`run.py`. Agrupados por subsistema:

| Cluster | Arquivos | Linhas | Observação |
|---|---:|---:|---|
| `ENGINE/decision/` versão V10 (`decision_engine_v10.py`, `decision_context.py`, `decision_trace.py`, `decision_types.py`, `decision_config.py`, `self_audit.py`) | 6 | 1.277 | **Já superado** por `ENGINE.decision.decision_engine` (o que roda de fato). Exatamente o tipo de "versão antiga do Brain" que você pediu para não recriar — já existe, já foi substituída, só falta remover. |
| `ENGINE/decision_brain/` (`decision_brain.py`, `counter_thesis.py`, `decision_brain_types.py`, `judgment.py`, `thesis_builder.py`) | 5 | 699 | Um segundo sistema de "raciocínio"/tese de decisão, paralelo ao que roda. Nunca foi ligado ao `main.py`. |
| `ENGINE/scanner/decision_engine.py` | 1 | 107 | **Um terceiro `decision_engine`**, este dentro do pacote scanner. Confirma sua suspeita de "motores de decisão sobrepostos": existem 3 implementações de decision engine no repo, só 1 está viva. |
| `ENGINE/scanner/` extras (`auto_calibration.py`, `quality_gate.py`, `setup_detector.py`, `scanner_report.py`, `evidence_registry.py`, `backtest/__init__.py`) | 6 | 738 | Camadas de calibração/gate/backtest do scanner nunca ligadas ao fluxo real. |
| `CORE/memory/` completo (`memory_engine.py`, `backtest_records.py`, `change_log.py`, `dna_updater.py`, `file_store.py`, `improvement_log.py`, `lesson_registry.py`, `memory_query.py`, `memory_report.py`, `memory_store.py`, `parameter_history.py`) | 11 | 978 | Sistema de "memória institucional / DNA / lições aprendidas" nunca executado — confirmado pelos diretórios `MEMORY/dna/`, `/lessons/`, `/institutional/` etc. vazios. |
| `CORE/config/` validação (`config_checker.py`, `environment_checker.py`, `loader.py`, `rules.py`, `schema.py`, `validation.py`, `validation_report.py`) | 7 | 217 | Camada de validação de config paralela, nunca chamada (a app usa `CORE.config.settings` direto). |
| `CORE/health/` extras (`alerts.py`, `diagnostics.py`, `heartbeat.py`, `metrics.py`, `status_registry.py`) | 5 | 119 | Siblings de `health_monitor.py` (esse sim é usado) nunca ligados. |
| `CORE/events/` extras (`dispatcher.py`, `event_registry.py`, `subscribers.py`) | 3 | 66 | Camada de pub-sub alternativa/antiga, paralela ao `event_bus.py`+`publishers.py` que está em uso. |
| `ENGINE.analytics.analytics_engine` | 1 | 261 | O módulo de Analytics inteiro (mencionado no seu próprio processo de Fase 8) nunca é chamado por nada em produção. |
| `ENGINE.execution.paper_engine` | 1 | 230 | **Segundo motor de paper trading**, duplicando `CORE.trading.paper_trading` (esse sim em uso). Duplicação real, não falso positivo. |
| `ENGINE.validation.consistency_validator` | 1 | 284 | Sibling não usado de `health_check.py`. |
| `ENGINE.market.market_correlation` + `.market_report` | 2 | 113 | Siblings não usados de `market_engine.py`. |
| `SERVICES.telegram.telegram_diagnostic_formatter` | 1 | 371 | Formatter de diagnóstico completo, nunca chamado (provavelmente feito para o Analytics/Diagnostic que também não roda). |
| `SERVICES.telegram.telegram_commands` / `.telegram_health` / `.telegram_logger` | 3 | 0 | Arquivos vazios (stubs nunca preenchidos). |
| `CORE.bootstrap.shutdown` | 1 | 21 | Rotina de shutdown "oficial" que existe mas não é chamada — `main.py` faz o shutdown inline em `QuantOSApp.stop()`. Vale avaliar se isso é um bug (deveria estar ligado) antes de remover, não é claramente lixo. |

---

## Resumo executivo

- **170 arquivos Python ativos** (fora `venv/`, `archive/`, `__pycache__`).
- **85 essenciais/importantes** (o bot real de ponta a ponta).
- **57 arquivos / ~5.514 linhas confirmadamente mortos**, sem nenhum ponto de entrada que os alcance.
- **3 implementações paralelas de "decision engine"** (1 viva, 2 mortas) e **2 de paper trading** (1 viva, 1 morta) — evidência direta de "motores sobrepostos" que sua missão pediu para eliminar.
- **6 diretórios totalmente vazios** (`BOTS/binance`, `BOTS/bybit`, `BOTS/future`, `TOOLS`, `KNOWLEDGE`, `LAB`, `CONFIG`, `DATA`, `LOGS`) — puro scaffolding.
- Nenhum arquivo foi apagado ou movido nesta etapa — isso é só o levantamento (Fase 1/5 do seu processo obrigatório).

## Próxima etapa recomendada

Conforme seu próprio processo (RFC → Implementação → Testes → ... → Liberação), o próximo passo é uma **RFC específica de remoção**, dividida em lotes por risco crescente:

1. **Lote 1 (risco mínimo)**: `CORE/memory/*` (11 arquivos, subsistema isolado, dados vazios confirmam que nunca rodou) + diretórios vazios de exchanges/scaffolding.
2. **Lote 2 (risco baixo)**: `ENGINE/decision_brain/*`, `ENGINE/scanner/decision_engine.py`, `ENGINE/decision/*_v10*` — os motores de decisão duplicados já superados.
3. **Lote 3 (risco baixo-médio)**: `CORE/config/*` validação, `CORE/health/*` extras, `CORE/events/*` extras, `ENGINE.execution.paper_engine`, `ENGINE.validation.consistency_validator`, `ENGINE.market.market_correlation/.market_report`.
4. **Lote 4 (decisão sua)**: `ENGINE.analytics.analytics_engine` + `SERVICES.telegram.telegram_diagnostic_formatter` — só remover se você confirmar que não pretende reativar Analytics/Diagnostics no futuro próximo.

Quer que eu já escreva a RFC do Lote 1 para aprovação, ou prefere revisar esta auditoria primeiro?

---

## Adendo (2026-07-11, mesma data) — Finalização do RFC_SIMPLIFICACAO.md já aprovado

Depois de escrever este relatório, descobri que já existia um `RFC_SIMPLIFICACAO.md` (sessão anterior) cobrindo praticamente o mesmo escopo, **parcialmente executado**: a maior parte das pastas do plano já tinha sido movida para `archive/`. Cruzando o plano contra o disco, faltavam apenas 2 itens:

1. `ENGINE/execution/paper_engine.py` (duplicava `CORE.trading.paper_trading`) — **movido para `archive/`**.
2. `CORE/utils/helpers.py`, `.lifecycle.py`, `.timer.py`, `.validators.py` (nunca importados) — **movidos para `archive/`**, mantendo `timeframe_manager.py` (em uso).

Ao validar que nada quebrou (Fase 6 — Homologação), o boot completo do `QuantOSApp` revelou **3 regressões reais deixadas pela execução incompleta do RFC anterior** (não causadas pelas 2 remoções acima, pré-existentes):

1. `CORE/bootstrap/startup.py` importava `CORE.errors.handlers`, mas `CORE/errors/` já tinha sido arquivado — o bot não subia (`ModuleNotFoundError`). Restaurados os 2 arquivos realmente usados (`exceptions.py`, `handlers.py`).
2. `ENGINE/watchdog/watchdog_integration.py` monitorava o módulo `"mid"` (MIDashboard), que o próprio RFC mandou remover — o watchdog tentava reiniciar um módulo inexistente indefinidamente. Removida a integração órfã.
3. `ENGINE/validation/health_check.py` e `SERVICES/telegram/telegram_sender.py` apontavam para `TELEGRAM/.env` (pasta arquivada) — bot não subia (`FileNotFoundError`). Corrigido para `.env` na raiz; valores reais de Telegram copiados do arquivo antigo.

Após as correções: **boot completo sem exceções, 85 módulos alcançáveis a partir de `main.py` (idêntico a antes das remoções), 50 símbolos reais descobertos via MEXC.** Detalhes em `CHANGELOG.md` [17.2.0].

**Pendência não resolvida, decisão sua**: `.env` tem `QUANTOS_MODE=PRODUCTION`, valor não reconhecido por `CORE/execution/mode_manager.py` (só aceita `DEVELOPMENT`/`PAPER_TRADING`/`LIVE`) — cai em fallback seguro para `DEVELOPMENT`. Não alterei porque isso decide se o bot autentica e opera ao vivo; me avise qual modo você quer.

Os achados **novos** desta auditoria (`CORE/memory/*`, `ENGINE/decision_brain/*`, `ENGINE/scanner/decision_engine.py`, cluster V10, etc.) permanecem no lugar, aguardando uma RFC própria — não fazem parte do escopo do RFC já aprovado.
