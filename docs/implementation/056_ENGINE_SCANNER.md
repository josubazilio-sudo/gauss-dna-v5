# QUANT OS

## DOCUMENTO 056 — ENGINE SCANNER

VERSÃO 1.0

MILESTONE: 05 - ENGINE

PRIORIDADE: 🔴 MÁXIMA

DEPENDÊNCIAS: Market Intelligence (doc 055)

---

### OBJETIVO

Varrer múltiplos mercados, timeframes e pares para detectar oportunidades de trading.

O Scanner é o ponto de entrada do pipeline operacional. Ele produz uma lista de candidatos que serão analisados pelo Scoring Engine.

---

### RESPONSABILIDADES

1. **Multi-pair Scanning** — Varrer pares configurados (spot, futuros)
2. **Multi-timeframe Analysis** — Analisar M5, M15, H1, H4, D1
3. **Pattern Detection** — Identificar SMC padrões (Order Blocks, FVG, Liquidity Sweep, BOS, CHoCH)
4. **Opportunity Ranking Preliminar** — Score inicial para filtrar candidatos
5. **Scanner Cycle** — Ciclo completo em ≤ 30 segundos (meta de performance)

---

### ARQUIVOS

```
ENGINE/scanner/
├── __init__.py
├── scanner_types.py          → Dataclasses ScanResult, Opportunity, Pattern
├── scanner_config.py         → Pares, timeframes, thresholds
├── scanner_engine.py         → Coordenador do ciclo de varredura
├── scanner_patterns.py       → Detecção de padrões SMC
├── scanner_ranker.py         → Rankeamento preliminar
├── scanner_report.py         → Relatório de varredura
```

---

### DATACLASSES PRINCIPAIS

```python
@dataclass
class Pattern:
    type: PatternType          # ORDER_BLOCK, FVG, LIQUIDITY_SWEEP, BOS, CHOCH
    direction: Direction       # BULLISH, BEARISH
    timeframe: str
    confidence: float          # 0.0 - 1.0
    price_level: float
    description: str

@dataclass
class ScanResult:
    pair: str
    timestamp: datetime
    patterns: list[Pattern]
    market_snapshot: MarketSnapshot
    preliminary_score: float   # 0.0 - 1.0
    timeframes_analyzed: list[str]

@dataclass  
class Opportunity:
    pair: str
    direction: Direction       # LONG, SHORT
    entry_price: float
    targets: list[float]
    stop_loss: float
    pattern: Pattern
    score: float
    timeframe: str
```

---

### FLUXO INTERNO

```
Start Scan Cycle
    │
    ▼
Get configured pairs & timeframes
    │
    ▼
For each pair:
    ├── Get MarketSnapshot from Market Engine
    ├── For each timeframe:
    │   ├── Detect SMC patterns
    │   └── Score opportunity
    │
    ▼
Rank all opportunities
    │
    ▼
Filter top candidates (by score threshold)
    │
    ▼
Return ScanResult list → para Scoring Engine
```

---

### PERFORMANCE

O Scanner DEVE completar um ciclo completo em ≤ 30 segundos para até 50 pares e 5 timeframes.

Estratégias para atingir a meta:
- Processamento paralelo por par (thread pool)
- Cache de dados OHLCV entre ciclos
- Pipeline assíncrono entre Market Engine, Scanner e Scoring

---

### CONFIGURAÇÃO

```python
DEFAULT_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", ...]
DEFAULT_TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"]
SCORE_THRESHOLD = 0.6             # Score mínimo para passar para Scoring Engine
MAX_CANDIDATES = 10               # Máximo de candidatos por ciclo
SCAN_INTERVAL_SECONDS = 30        # Intervalo entre ciclos
PARALLEL_WORKERS = 10             # Threads para varredura paralela
```

---

### TESTES

20-30 testes cobrindo:
- Detecção de padrões SMC em dados sintéticos
- Ranking de oportunidades
- Filtro por threshold
- Performance do ciclo de varredura

---

FIM DO DOCUMENTO 056
