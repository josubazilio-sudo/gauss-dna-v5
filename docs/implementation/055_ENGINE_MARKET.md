# QUANT OS

## DOCUMENTO 055 — ENGINE MARKET INTELLIGENCE

VERSÃO 1.0

MILESTONE: 05 - ENGINE

PRIORIDADE: 🔴 MÁXIMA

---

### OBJETIVO

Analisar as condições de mercado em tempo real para alimentar os demais engines.

O Market Intelligence Engine é a primeira camada do pipeline — ele processa dados brutos e produz um diagnóstico estruturado do mercado.

---

### RESPONSABILIDADES

1. **Regime Detection** — Identificar tendência (alta/baixa/lateral) e força
2. **Volatility Analysis** — Calcular volatilidade atual vs. histórica (ATR, BB)
3. **Liquidity Analysis** — Avaliar liquidez disponível, spreads, profundidade
4. **Funding Analysis** — Monitorar funding rate para pares perpétuos
5. **Correlation Analysis** — Correlação entre pares e setores
6. **Market Regime Classification** — Classificar em: trending, ranging, volatile, calm

---

### ARQUIVOS

```
ENGINE/market/
├── __init__.py
├── market_types.py           → Enum RegimeType, dataclasses MarketSnapshot, RegimeInfo
├── market_config.py          → Parâmetros de análise (períodos, thresholds)
├── market_engine.py          → Coordenador principal
├── market_analyzer.py        → Análise técnica (ATR, BB, EMA, ADX)
├── market_liquidity.py       → Análise de liquidez e funding
├── market_regime.py          → Classificador de regime
├── market_report.py          → Relatório de condições de mercado
```

---

### DATACLASSES PRINCIPAIS

```python
@dataclass
class MarketSnapshot:
    pair: str
    timestamp: datetime
    price: float
    volume: float
    volatility: float          # ATR atual
    liquidity_score: float     # 0.0 - 1.0
    funding_rate: float
    regime: RegimeType
    regime_confidence: float   # 0.0 - 1.0

@dataclass
class RegimeInfo:
    type: RegimeType           # TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE, CALM
    strength: float            # 0.0 - 1.0
    adx: float
    trend_slope: float
    channel_width: float       # Largura do canal (ranging)
```

---

### FLUXO INTERNO

```
Raw data (OHLCV)
    │
    ▼
┌──────────────────────┐
│   Market Analyzer    │ → ADX, ATR, EMA, BB, volume profile
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Market Regime      │ → Classifica trending/ranging/volatile
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Market Liquidity   │ → Spread, funding, depth
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Market Engine      │ → Compõe MarketSnapshot
└──────────┬───────────┘
           │
           ▼
      MarketSnapshot → para Scanner e Scoring
```

---

### CONFIGURAÇÃO

```python
REGRIME_ADX_TRENDING = 25          # ADX acima disso é trending
REGRIME_ADX_STRONG = 40            # ADX acima disso é tendência forte
VOLATILITY_ATR_PERIOD = 14
VOLATILITY_BB_PERIOD = 20
VOLATILITY_BB_STD = 2.0
LIQUIDITY_SPREAD_MAX = 0.001       # Spread máximo aceitável (0.1%)
LIQUIDITY_DEPTH_MIN = 100000       # Profundidade mínima em USDT
FUNDING_RATE_WARN = 0.01           # Funding acima disso = alerta
```

---

### TESTES

20-30 testes cobrindo:
- Classificação de regime em diferentes cenários
- Cálculo de ATR, ADX, BB
- Análise de liquidez com spreads variados
- Relatório de mercado

---

FIM DO DOCUMENTO 055
