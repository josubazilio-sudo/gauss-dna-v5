# RFC: Simplificação da Arquitetura QuantOS V17

## Objetivo

Reduzir o QuantOS de 488 arquivos .py para ~70 essenciais, eliminando código
morto, duplicações, engines concorrentes e cálculos repetidos — sem alterar
a estratégia de trading.

## Motivação

49% dos arquivos são código morto ou duplicado. Cálculos como apply_risk(),
RSI e RVOL são executados 2x por ciclo. Há 2 engines de decisão concorrentes,
2 paper tradings, 2 telegram services e 3 sistemas de monitoramento paralelos.

## Escopo da Mudança

### O QUE MUDA (arquivos)

- **main.py** — Simplificado: pipeline direto sem DecisionBrain, SelfAudit,
  MIDashboard, AnalyticsEngine (movidos para observabilidade opcional)
- **scanner_engine.py** — Não recalcula RSI/RVOL (usa do MarketContext).
  apply_risk() removido (será chamado 1x no DecisionEngine)
- **decision_engine.py** — Reduzido de 21 para 8 hard gates.
  apply_risk() chamado 1x aqui (não mais no scanner)
- **scanner_config.py** — Thresholds mantidos, removidas referências a
  módulos mortos (ProbabilityEngine, LearningEngine)
- **scanner_scoring.py + market_scoring.py** — Unificados

### O QUE É REMOVIDO (arquivos movidos para /archive)

- TELEGRAM/ → archive/ (duplicata de SERVICES/telegram/)
- AI/ → archive/ (nunca integrado)
- ENGINE/council/ → archive/ (V10 nunca ativado)
- ENGINE/world/ → archive/ (V10)
- ENGINE/skills/ → archive/ (V10)
- ENGINE/meta/ → archive/ (V10)
- ENGINE/policy/ → archive/ (V10)
- ENGINE/core/ → archive/ (V10)
- ENGINE/memory/ → archive/ (V10)
- ENGINE/mid/ → archive/ (substituído por logs)
- ENGINE/execution/paper_engine.py → archive/
- ENGINE/news/ → archive/
- ENGINE/learning/ → archive/
- ENGINE/probability/ → archive/
- ENGINE/backtest/ → archive/
- ENGINE/explanation/ → archive/
- CORE/audit/ → archive/
- CORE/baseline/ → archive/
- CORE/metrics/ → archive/
- CORE/permission/ → archive/
- CORE/resource/ → archive/
- CORE/version/ → archive/
- CORE/notification/ → archive/
- CORE/knowledge/ → archive/
- CORE/scheduler/ → archive/
- CORE/service_registry/ → archive/
- CORE/task/ → archive/
- CORE/security/ → archive/
- CORE/dependency/ → archive/
- CORE/cache/ → archive/
- CORE/state/ → archive/
- CORE/logger/ → archive/
- CORE/errors/ → archive/
- CORE/config/ → archive/
- CORE/interfaces/ → archive/
- CORE/utils/ → archive/
- SERVICES/telegram_bot/ → archive/
- SERVICES/audit/ → archive/ (vazio)
- SERVICES/backtest/ → archive/ (vazio)
- SERVICES/documentation/ → archive/ (vazio)
- SERVICES/performance/ → archive/ (vazio)
- SERVICES/versioning/ → archive/ (vazio)
- AUDIT/ → archive/ (scripts standalone)
- SCRIPTS/ → archive/
- TESTS/ → archive/ (serão reescritos)

### O QUE É SIMPLIFICADO

1. **DecisionEngine**: 21 gates → 8 gates essenciais:
   - GATE 1: Dados de mercado válidos
   - GATE 2: RVOL >= 0.70
   - GATE 3: ADX >= 25
   - GATE 4: BOS ou CHOCH confirmado
   - GATE 5: Entry Zone >= 0.40
   - GATE 6: Quality >= 0.45
   - GATE 7: Consensus >= 0.50
   - GATE 8: RR >= 2.0 (apply_risk chamado ANTES deste gate)

2. **DecisionBrain**: Removido do pipeline principal.
   Contra-tese e julgamento duplicam a lógica dos hard gates.

3. **SelfAuditEngine**: Removido. As validações finais de preço
   (stop_loss > 0, entry > 0, tp > 0) são feitas no DecisionEngine.

4. **ConfluenceEngine**: Removido. A lógica de confluência está
   duplicada nos scores do scanner.

5. **MIDashboard**: Removido. Substituído por logs estruturados.

6. **AnalyticsEngine**: Removido do pipeline principal.
   Exportação para SQLite/CSV será opcional via script separado.

### NOVO FLUXO DO PIPELINE

```
main.py

_fetch_and_scan() [paralelo, ThreadPoolExecutor]
  |
  +-- provider.get_all_timeframes()
  +-- MarketEngine.analyze()
  |     +-- compute_all_emas
  |     +-- compute_adx
  |     +-- analyze_momentum (RSI, RVOL) ← ÚNICA chamada
  |     +-- analyze_volatility (ATR, BB)
  |     +-- classify_regime
  |     +-- compute_all_scores
  +-- ScannerEngine.scan()
        +-- scan_all_patterns
        +-- analyze_structure
        +-- compute_all_scanner_scores (usa RSI/RVOL do MarketContext)
        +-- calculate_entry_zone
        +-- compute_flow/timing/conviction
        +-- build_signal
        +-- ConsensusEngine.compute()
        +-- rank_pipeline

_process_scan_result() [sequencial]
  |
  +-- DecisionEngine.evaluate_signal()
  |     +-- 8 Hard Gates
  |     +-- apply_risk() ← ÚNICA chamada
  |     +-- GATE 8: RR >= 2.0
  +-- SignalTracker (dedup)
  +-- Publisher
  +-- PaperTradingEngine
  +-- Watchdog
  +-- Telegram

Serviços auxiliares:
  +-- HealthMonitor (ping periódico)
  +-- Logs
```

## Impacto Esperado

- Redução de 488 arquivos → ~70
- Performance: ciclo 2x mais rápido (sem cálculos duplicados)
- Manutenibilidade: fluxo linear, sem engines concorrentes
- Risco: baixo (estratégia não muda, apenas a arquitetura)

## Riscos

1. Regressão se algum módulo archive for necessário — Rollback:
   restaurar /archive
2. Thresholds podem precisar de ajuste fino após simplificação —
   manter valores atuais
3. Compatibilidade Windows/Linux/VPS preservada (não mudamos
   dependências ou paths)

## Critérios de Aceitação

- [ ] main.py inicia sem erros
- [ ] Pipeline completo roda (Scanner → Market → Decision → Risk → Telegram)
- [ ] apply_risk chamado 1x (não 2x)
- [ ] RSI/RVOL calculados 1x
- [ ] Health check passa
- [ ] Telegram envia sinais
- [ ] Paper trading registra entradas/saídas
- [ ] Relatório de auditoria mostra < 100 arquivos
