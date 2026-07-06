# QUANT OS

## DOCUMENTO 061 — ENGINE OPTIMIZER

VERSÃO 1.0

MILESTONE: 05 - ENGINE

PRIORIDADE: 🔴 MÁXIMA

DEPENDÊNCIAS: Todos os engines (Market, Scanner, Scoring, Decision, Validation, Signals)

---

### OBJETIVO

Otimizar parâmetros de todos os engines usando resultados de backtest e dados históricos.

O Optimizer opera em paralelo ao pipeline principal. Ele analisa resultados passados, executa backtests com variações de parâmetros e propõe ajustes para melhorar performance.

---

### RESPONSABILIDADES

1. **Parameter Optimization** — Buscar parâmetros ótimos para cada engine
2. **Backtest Integration** — Executar backtests com diferentes configurações
3. **Walk-forward Analysis** — Validar robustez dos parâmetros
4. **Parameter Versioning** — Versionar parâmetros testados
5. **Optimization Report** — Relatório comparativo de performance
6. **Auto-tune** — Ajuste automático de parâmetros com base em métricas recentes

---

### ARQUIVOS

```
ENGINE/optimizer/
├── __init__.py
├── optimizer_types.py          → Dataclasses ParamSet, OptimizationResult
├── optimizer_config.py         → Configuração do otimizador
├── optimizer_engine.py         → Coordenador principal
├── optimizer_search.py         → Algoritmos de busca (grid, random, bayesian)
├── optimizer_backtest.py       → Execução de backtests
├── optimizer_walkforward.py    → Walk-forward analysis
├── optimizer_report.py         → Relatório de otimização
```

---

### DATACLASSES PRINCIPAIS

```python
@dataclass
class ParamSet:
    name: str                    # Nome do conjunto
    params: dict                 # Parâmetros
    metrics: dict                # Métricas resultantes (WR, PF, DD, etc.)
    score: float                 # Score combinado da otimização
    version: str
    created_at: datetime

@dataclass
class OptimizationResult:
    param_sets: list[ParamSet]   # Conjuntos testados
    best: ParamSet               # Melhor conjunto
    improvement: dict            # Melhoria vs. baseline
    walk_forward_score: float    # Score walk-forward
    recommendations: list[str]   # Recomendações
```

---

### PARÂMETROS OTIMIZÁVEIS

| Engine | Parâmetros Otimizáveis |
|--------|----------------------|
| Market | ADX threshold, ATR period, BB std |
| Scanner | SCORE_THRESHOLD, MAX_CANDIDATES |
| Scoring | WEIGHTS (smc, orderflow, momentum, risk) |
| Decision | score_minimum, max_exposure, max_drawdown |
| Validation | max_price_deviation, max_spread, consistency_min |
| Signals | signal_ttl, max_active_signals |

---

### ALGORITMOS DE BUSCA

```python
SEARCH_ALGORITHMS = {
    "grid": GridSearch,           # Busca exaustiva em grade
    "random": RandomSearch,       # Busca aleatória
    "bayesian": BayesianSearch,   # Otimização Bayesiana (recomendado)
}
```

---

### FLUXO INTERNO

```
Start Optimization
    │
    ▼
Define parameter space
    │
    ▼
┌──────────────────────┐
│  Search Algorithm    │ → Gera combinações de parâmetros
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Backtest Engine     │ → Executa backtest para cada combinação
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Walk-forward        │ → Valida robustez
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Report & Recommend  │ → Melhor conjunto + recomendações
└──────┬───────────────┘
       │
       ▼
OptimizationResult → proposto para aprovação no ChangeLog
```

---

### TESTES

25-35 testes cobrindo:
- Grid search com parâmetros simples
- Random search
- Walk-forward analysis
- Geração de relatório
- Comparação com baseline
- Validação de limites de parâmetros

---

FIM DO DOCUMENTO 061
