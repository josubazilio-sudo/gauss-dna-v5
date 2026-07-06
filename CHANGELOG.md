# Changelog

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
