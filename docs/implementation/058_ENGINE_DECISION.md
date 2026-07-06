# QUANT OS

## DOCUMENTO 058 — ENGINE DECISION

VERSÃO 1.0

MILESTONE: 05 - ENGINE

PRIORIDADE: 🔴 MÁXIMA

DEPENDÊNCIAS: Scoring (doc 057), CORE (Security, Permission, Risk)

---

### OBJETIVO

Decidir se uma oportunidade será convertida em sinal ou descartada.

O Decision Engine é o guardião da qualidade. Ele não apenas verifica o score, mas pondera o contexto completo: risco atual, exposição, confiança do sistema, funding, horário e regras institucionais.

---

### RESPONSABILIDADES

1. **Score Threshold** — Verificar se o composite score atinge o mínimo
2. **Risk Check** — Conferir exposição atual, drawdown, posições abertas
3. **Contextual Check** — Horário, funding, notícias agendadas
4. **Permission Check** — Verificar permissões do bot e do usuário
5. **Confidence Weight** — Ajustar score com base na confiança do sistema
6. **Final Decision** — APPROVED, REJECTED, PENDING_REVIEW

---

### ARQUIVOS

```
ENGINE/decision/
├── __init__.py
├── decision_types.py          → Enum Decision, dataclass DecisionResult
├── decision_config.py         → Thresholds, regras de decisão
├── decision_engine.py         → Coordenador principal
├── decision_risk.py           → Análise de risco contextual
├── decision_rules.py          → Regras de decisão (horário, funding, etc.)
├── decision_report.py         → Relatório de decisão
```

---

### DATACLASSES PRINCIPAIS

```python
class Decision(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"

@dataclass
class DecisionResult:
    score_result: ScoreResult
    decision: Decision
    reasons: list[str]           # Motivos da decisão
    risk_metrics: dict
    confidence: float            # 0.0 - 1.0
    timestamp: datetime
    expires_at: datetime         # Validade da decisão
```

---

### REGRAS DE DECISÃO

```python
DECISION_RULES = {
    "score_minimum": 0.65,           # Score mínimo
    "max_open_positions": 3,         # Máximo de posições simultâneas
    "max_exposure_percent": 5.0,     # Exposição máxima por par (%)
    "max_daily_drawdown": 3.0,       # Drawdown máximo diário (%)
    "min_confidence": 0.5,           # Confiança mínima do sistema
    "blocked_hours": [],             # Horários bloqueados
    "funding_rate_max": 0.01,        # Funding rate máximo
    "decision_ttl_seconds": 300,     # Decisão expira em 5 minutos
}
```

---

### FLUXO INTERNO

```
ScoreResult (do Scoring)
    │
    ▼
┌──────────────────┐
│  Score Threshold │ → Score ≥ mínimo?
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Decision Rules  │ → Horário, funding, notícias
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Decision Risk   │ → Exposição, drawdown, posições
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Decision Engine │ → Pondera tudo e decide
└──────┬───────────┘
       │
       ▼
DecisionResult → para Validation Engine
```

---

### TESTES

20-30 testes cobrindo:
- Decisão com score acima/abaixo do threshold
- Rejeição por exposição máxima
- Rejeição por drawdown diário
- Decisão com funding rate alto
- Confiança do sistema baixa
- Decisão aprovada (cenário ideal)

---

FIM DO DOCUMENTO 058
