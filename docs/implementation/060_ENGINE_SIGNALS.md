# QUANT OS

## DOCUMENTO 060 — ENGINE SIGNALS

VERSÃO 1.0

MILESTONE: 05 - ENGINE

PRIORIDADE: 🔴 MÁXIMA

DEPENDÊNCIAS: Validation (doc 059)

---

### OBJETIVO

Gerar e formatar sinais de trading prontos para execução pelos bots.

O Signals Engine é a saída do pipeline operacional. Ele transforma uma decisão validada em um sinal padronizado que qualquer bot pode consumir.

---

### RESPONSABILIDADES

1. **Signal Generation** — Criar sinal a partir da decisão validada
2. **Signal Formatting** — Padronizar formato para todos os bots
3. **Signal Enrichment** — Adicionar metadados (score, confiança, timeframe)
4. **Signal Expiry** — Gerenciar expiração de sinais não executados
5. **Signal Logging** — Registrar todos os sinais emitidos
6. **Cancel Signals** — Permitir cancelamento de sinais antes da execução

---

### ARQUIVOS

```
ENGINE/signals/
├── __init__.py
├── signals_types.py           → Enum SignalStatus, dataclass Signal
├── signals_config.py          → Configuração de expiração, formato
├── signals_engine.py          → Coordenador principal
├── signals_formatter.py       → Formatação para diferentes bots
├── signals_tracker.py         → Rastreamento de sinais emitidos
├── signals_report.py          → Relatório de sinais
```

---

### DATACLASSES PRINCIPAIS

```python
class SignalSide(Enum):
    LONG = "long"
    SHORT = "short"

class SignalStatus(Enum):
    ACTIVE = "active"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

@dataclass
class Signal:
    id: str                      # UUID do sinal
    pair: str
    side: SignalSide
    entry_price: float
    stop_loss: float
    take_profit: list[float]
    confidence: float            # 0.0 - 1.0
    score: float                 # Score final composto
    timeframe: str
    status: SignalStatus
    created_at: datetime
    expires_at: datetime
    executed_at: Optional[datetime]
    metadata: dict
```

---

### CONFIGURAÇÃO

```python
SIGNAL_CONFIG = {
    "signal_ttl_seconds": 300,           # Sinal expira em 5 minutos
    "max_active_signals": 5,             # Máximo de sinais ativos por par
    "require_validation": True,          # Exige validação para emitir
    "format_version": "1.0",             # Versão do formato
}
```

---

### FLUXO INTERNO

```
ValidationResult (do Validation)
    │
    ▼
┌──────────────────────┐
│  Signals Engine      │ → Cria Signal a partir do resultado
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Signals Formatter   │ → Formata para o bot alvo
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Signals Tracker     │ → Registra e monitora
└──────┬───────────────┘
       │
       ▼
Signal → para o Bot (via barramento de eventos)
```

---

### TESTES

20-30 testes cobrindo:
- Geração de sinal a partir de ValidationResult
- Formatação para diferentes bots
- Expiração de sinal
- Cancelamento de sinal
- Máximo de sinais ativos
- Rastreamento e log

---

FIM DO DOCUMENTO 060
