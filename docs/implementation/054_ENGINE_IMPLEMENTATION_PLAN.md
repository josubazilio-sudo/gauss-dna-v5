# QUANT OS

## DOCUMENTO 054 — ENGINE IMPLEMENTATION PLAN

VERSÃO 1.0

MILESTONE: 05 - ENGINE

PRIORIDADE: 🔴 MÁXIMA

DEPENDÊNCIAS: 001 a 053, FASE 01 (CORE), FASE 02 (MEMORY), FASE 03 (KNOWLEDGE)

---

### OBJETIVO

Construir o motor principal do QuantOS.

O ENGINE é o cérebro operacional — recebe dados brutos do mercado, aplica inteligência, gera scores, valida sinais e produz decisões executáveis.

Nenhum bot contém lógica de decisão. Toda inteligência reside no ENGINE.

---

### COMPONENTES

```
ENGINE/
├── scanner/          → Varredura de mercados, detecção de oportunidades
├── market/           → Análise de regime, liquidez, volatilidade, funding
├── scoring/          → Pontuação de entradas/saídas por múltiplos critérios
├── decision/         → Decisor final ponderando score + validação + risco
├── signals/          → Geração e formatação de sinais
├── validation/       → Confirmação/filtro de sinais antes da execução
└── optimizer/        → Otimização de parâmetros via backtest
```

**Nota:** O diretório `decision/` é adicionado nesta fase, resolvendo a discrepância entre a Arquitetura (doc 010, 011) que lista 7 componentes e a Estrutura de Repositório (doc 013) que listava 6 diretórios.

---

### FLUXO DE DADOS

```
Mercado (exchange)
    │
    ▼
┌─────────────┐
│   Scanner   │ → Detecta candidatos (pares, timeframe, direção)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Market    │ → Analisa regime, liquidez, volatilidade, funding
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Scoring   │ → Aplica filtros: SMC, order flow, momentum, RVOL, Kalman
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Decision   │ → Pondera score, risco, confiança → decide
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Validation │ → Confirma: spread, funding, notícia, consistência
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Signals   │ → Gera sinal formatado para o bot
└──────┬──────┘
       │
       ▼
     Bot (execução)
```

O Optimizer opera em paralelo: analisa resultados passados e ajusta parâmetros de Scoring, Decision e Validation.

---

### ORDEM DE IMPLEMENTAÇÃO

Cada submódulo segue: especificação → código → testes → documentação.

| Ordem | Submódulo | Depende de |
|-------|-----------|------------|
| 1 | Market Intelligence | CORE, KNOWLEDGE |
| 2 | Scanner | Market |
| 3 | Scoring | Market, Scanner |
| 4 | Decision | Scoring, CORE (Risk) |
| 5 | Validation | Decision, Market |
| 6 | Signals | Validation |
| 7 | Optimizer | Todos (opera em paralelo) |

---

### PADRÃO DE ARQUITETURA

Cada submódulo segue o mesmo padrão do CORE:

```
ENGINE/<submodulo>/
├── __init__.py
├── types.py              → Enums, dataclasses, tipos específicos
├── <submodulo>_engine.py  → Coordenador principal
├── <submodulo>_config.py  → Configuração e constantes
├── <submodulo>_report.py  → Relatórios
└── ...                   → Arquivos específicos do submódulo
```

Todos os engines herdam de `BaseEngine` (CORE/interfaces/base_engine.py).

---

### DEPENDÊNCIAS COM CORE

| Engine | Dependências CORE |
|--------|------------------|
| Market Engine | event_bus, config, logger |
| Scanner | Market Engine, event_bus, scheduler |
| Scoring | Market Engine, Scanner, state |
| Decision | Scoring, security, permission, notification |
| Validation | Decision, Market Engine, config_validator |
| Signals | Validation, notification |
| Optimizer | task_manager, metrics, cache, memory |

---

### REGRAS

1. Todo engine deve passar pelo Quality Gate (doc 023) antes de ser considerado pronto.
2. Todo engine deve ter cobertura de testes ≥ 90%.
3. Nenhum engine pode depender diretamente de um bot.
4. A comunicação entre engines ocorre por interfaces definidas (dataclasses), nunca por acesso direto.
5. Toda decisão do Decision Engine deve ser logada e auditável.
6. O Scanner deve completar uma varredura completa em ≤ 30 segundos.
7. Scores devem ser normalizados entre 0.0 e 1.0.
8. Sinais só são emitidos após validação positiva.

---

### ENTREGAS POR SUBMÓDULO

| Submódulo | Arquivos Esperados | Testes Esperados |
|-----------|-------------------|------------------|
| Market | 5-7 | 20-30 |
| Scanner | 5-7 | 20-30 |
| Scoring | 6-8 | 25-35 |
| Decision | 5-7 | 20-30 |
| Validation | 5-7 | 20-30 |
| Signals | 5-7 | 20-30 |
| Optimizer | 6-8 | 25-35 |

**Total estimado:** 40-50 arquivos, 150-200 testes.

---

### CHECKPOINT

Ao final da FASE 04 — ENGINE:

- Executar auditoria completa
- Criar Baseline v2.2.0
- Atualizar PROJECT_DNA
- Atualizar CHANGELOG
- Registrar métricas
- Iniciar FASE 05 — SERVICES

---

FIM DO DOCUMENTO 054
