# QUANT OS

## DOCUMENTO 059 — ENGINE VALIDATION

VERSÃO 1.0

MILESTONE: 05 - ENGINE

PRIORIDADE: 🔴 MÁXIMA

DEPENDÊNCIAS: Decision (doc 058), Market Intelligence (doc 055)

---

### OBJETIVO

Validar a decisão antes da geração do sinal.

O Validation Engine é a última barreira antes do sinal ser emitido. Ele confirma se a decisão ainda é válida (preço não moveu, liquidez não evaporou, funding não virou) e aplica filtros finais de consistência.

---

### RESPONSABILIDADES

1. **Price Check** — Verificar se o preço atual está dentro da zona aceitável
2. **Liquidity Re-check** — Confirmar liquidez no momento da validação
3. **Funding Re-check** — Verificar funding rate atual
4. **Spread Check** — Confirmar spread dentro do aceitável
5. **Consistency Check** — Verificar se múltiplos timeframes ainda concordam
6. **Validation Report** — Relatório completo da validação

---

### ARQUIVOS

```
ENGINE/validation/
├── __init__.py
├── validation_types.py         → Enum ValidationStatus, dataclass ValidationResult
├── validation_config.py        → Thresholds de validação
├── validation_engine.py        → Coordenador principal
├── validation_price.py         → Verificação de preço e slippage
├── validation_liquidity.py     → Re-check de liquidez e spread
├── validation_consistency.py   → Consistência multi-timeframe
├── validation_report.py        → Relatório de validação
```

---

### DATACLASSES PRINCIPAIS

```python
class ValidationStatus(Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"

@dataclass
class ValidationResult:
    decision: DecisionResult
    status: ValidationStatus
    price_check: bool
    liquidity_check: bool
    funding_check: bool
    spread_check: bool
    consistency_check: bool
    details: dict
    timestamp: datetime
```

---

### CONFIGURAÇÃO

```python
VALIDATION = {
    "max_price_deviation": 0.002,       # 0.2% máximo de desvio do preço original
    "max_spread_bps": 5,                # Spread máximo em basis points
    "liquidity_min_usdt": 50000,        # Liquidez mínima em USDT
    "funding_max_absolute": 0.01,       # Funding máximo absoluto
    "consistency_min_timeframes": 2,    # Mínimo de timeframes concordando
    "validation_ttl_seconds": 60,       # Validação expira em 60s
}
```

---

### FLUXO INTERNO

```
DecisionResult (do Decision)
    │
    ▼
┌──────────────────────┐
│  Validation Price    │ → Preço atual vs. preço da decisão
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Validation Liquidity │ → Spread, profundidade
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Validation Funding   │ → Funding atual
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│Validation Consistency│ → Timeframes concordam?
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Validation Engine   │ → Consolida e decide
└──────┬───────────────┘
       │
       ▼
ValidationResult → para Signals Engine
```

---

### TESTES

20-30 testes cobrindo:
- Validação aprovada (tudo ok)
- Rejeição por slippage
- Rejeição por spread alto
- Rejeição por funding
- Expiração da validação
- Consistência multi-timeframe

---

FIM DO DOCUMENTO 059
