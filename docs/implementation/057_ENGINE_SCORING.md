# QUANT OS

## DOCUMENTO 057 — ENGINE SCORING

VERSÃO 1.0

MILESTONE: 05 - ENGINE

PRIORIDADE: 🔴 MÁXIMA

DEPENDÊNCIAS: Market Intelligence (doc 055), Scanner (doc 056)

---

### OBJETIVO

Pontuar cada oportunidade gerada pelo Scanner usando múltiplos critérios quantitativos.

O Scoring Engine é onde a inteligência de trading é aplicada. Ele combina SMC, order flow, momentum, volatilidade e risco em um score único e normalizado.

---

### RESPONSABILIDADES

1. **Multi-criteria Scoring** — Aplicar múltiplos filtros com pesos configuráveis
2. **SMC Score** — Qualidade do padrão SMC detectado
3. **Order Flow Score** — Delta, CVD, volume profile
4. **Momentum Score** — RVOL, Kalman filter, EMA cross
5. **Risk Score** — Relação risco/retorno, distância ao SL, ATR
6. **Composite Score** — Score final ponderado (0.0 - 1.0)
7. **Score Breakdown** — Decomposição por critério para auditoria

---

### ARQUIVOS

```
ENGINE/scoring/
├── __init__.py
├── scoring_types.py           → Dataclasses ScoreResult, ScoreComponent
├── scoring_config.py          → Pesos de cada critério, thresholds
├── scoring_engine.py          → Coordenador principal
├── scoring_smc.py             → Score do padrão SMC
├── scoring_orderflow.py       → Score de order flow
├── scoring_momentum.py        → Score de momentum/RVOL
├── scoring_risk.py            → Score de risco
├── scoring_report.py          → Relatório detalhado de score
```

---

### DATACLASSES PRINCIPAIS

```python
@dataclass
class ScoreComponent:
    name: str                  # "smc", "orderflow", "momentum", "risk"
    value: float               # 0.0 - 1.0
    weight: float              # Peso na composição
    details: dict              # Detalhes do cálculo

@dataclass
class ScoreResult:
    opportunity: Opportunity
    composite_score: float     # 0.0 - 1.0
    components: list[ScoreComponent]
    approved: bool             # Passou no threshold mínimo?
    timestamp: datetime
    metadata: dict
```

---

### PESOS PADRÃO

```python
WEIGHTS = {
    "smc": 0.30,               # Qualidade do padrão SMC
    "orderflow": 0.25,         # Order flow confirmando
    "momentum": 0.25,          # RVOL + Kalman + EMA
    "risk": 0.20,              # Relação risco/retorno
}
SCORE_MINIMUM = 0.65          # Score mínimo para aprovação
```

---

### FLUXO INTERNO

```
Opportunity (do Scanner)
    │
    ▼
┌──────────────────┐
│  Scoring SMC     │ → Score da qualidade do padrão
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Scoring OrderFlow│ → Delta, CVD, volume
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Scoring Momentum │ → RVOL, Kalman, ADX
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Scoring Risk    │ → RR ratio, ATR distance
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Composite Score │ → Ponderado + threshold
└──────┬───────────┘
       │
       ▼
ScoreResult → para Decision Engine
```

---

### TESTES

25-35 testes cobrindo:
- Cálculo de cada score individual
- Composite score com pesos variados
- Threshold de aprovação
- Decomposição de score para auditoria
- Cenários de borda (valores extremos, dados ausentes)

---

FIM DO DOCUMENTO 057
