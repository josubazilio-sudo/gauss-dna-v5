# QUANTOS X V10.0 — ARTIFICIAL MARKET INTELLIGENCE OPERATING SYSTEM (AMI-OS)

## Architecture Overview

12 Cognitive Layers. Universal Contract. World Model. Skill Registry. Dual Memory. Evidence Graph. Policy Engine. Observability.

---

## The 12 Cognitive Layers

### 1. Perception Layer
- **Responsibility**: Observe the market. No decisions.
- **Input**: OHLCV, Order Book, Trades, Funding, OI, Dominance, Correlation, News, Economic Calendar, On-chain
- **Output**: `MarketContext` (standardized)
- **Location**: `ENGINE/market/`, `CORE/data_providers/`

### 2. World Model (NEW)
- **Responsibility**: Global model of market state. Used by all cognitive layers for context.
- **Contains**: Market regime, macro state, global liquidity, correlation, dominance, volatility, system state, skill health, relevant events
- **Location**: `ENGINE/world/world_model.py`

### 3. Analysis Layer (Skills)
- **Responsibility**: Specialized technical analysis. No decisions.
- **Input**: `MarketContext` + `WorldModel`
- **Contract** (Universal, immutable):
  ```python
  @dataclass(frozen=True)
  class SkillOpinion:
      skill_name: str
      confidence: float    # 0.0-1.0
      risk: float          # 0.0-1.0
      probability: float   # 0.0-1.0
      evidence: List[str]  # structured facts only
      observations: str    # technical text
      success: bool
      metrics: SkillMetrics
  ```
- **Forbidden**: LONG, SHORT, BUY, SELL, APPROVE, REJECT, recommendation, direction
- **Location**: `ENGINE/skills/`

### 4. Skill Registry (NEW)
- **Responsibility**: Central registry for all skills
- **Registration**: Each skill auto-registers name, category, version, author, dependencies, capabilities, priority, computational cost
- **Rule**: New skills added by registration only — no core changes needed
- **Location**: `ENGINE/skills/skill_registry.py`

### 5. CEO AI (Orchestrator)
- **Responsibility**: Discover, register, execute skills in parallel. Control timeout. Detect failures. Publish events.
- **Rules**: Never interprets indicators. Never decides operations.
- **Location**: `ENGINE/skills/skills_engine.py`

### 6. Consensus Engine
- **Responsibility**: Consolidate all SkillOpinions
- **Sub-modules**:
  - **Evidence Graph Builder**: Correlate convergent/divergent evidence (no keyword inference)
  - **Health Score Calculator**: Availability, latency, precision, reliability per skill
  - **Dynamic Weight Calculator**: Weight by regime, volatility, setup, performance, health
  - **Consensus Calculator**: Global confidence, risk, probability, consensus score
- **Output**: `CouncilVerdict`
- **Location**: `ENGINE/council/consensus_engine.py`

### 7. Meta Intelligence
- **Responsibility**: Pre-decision cognitive filter
- **Questions**: Sufficient info? Market clear? Statistical advantage? Evidence quality? Relevant conflicts? Worth continuing?
- **Output**: Any NO → `AGUARDAR` (short-circuit)
- **Location**: `ENGINE/meta/meta_intelligence.py`

### 8. Decision Engine
- **Responsibility**: Sole authority to decide
- **Input**: ONLY `CouncilVerdict`
- **Process**: Hard Gates → Risk Validation → Policy Validation
- **Output**: `DecisionResult` (APROVADO | REJEITADO | AGUARDAR)
- **Location**: `ENGINE/decision/decision_engine.py`

### 9. Policy Engine
- **Responsibility**: Institutional compliance and operational limits
- **Rules**: Max operations/day, max daily risk, max exposure, correlation, trading hours, max drawdown, circuit breaker
- **Authority**: Can block even if Decision Engine approves
- **Location**: `ENGINE/policy/policy_engine.py`

### 10. Risk Manager
- **Responsibility**: Calculate risk parameters post-approval only
- **Calculates**: Entry, Stop, BE, Trailing, TP, RR, Leverage, Collateral, Position Size
- **Rule**: Never participates in the decision
- **Location**: `ENGINE/risk/risk_manager.py`

### 11. Execution Layer
- **Responsibility**: Execute approved signals only
- **Components**: Telegram, Paper Trading, Exchange, Logs, Audit
- **Location**: `SERVICES/telegram/`, `CORE/trading/`, `BOTS/`

### 12. Learning Layer
- **Responsibility**: Register and analyze results. Never auto-modifies production.
- **Records**: Setup, context, result, drawdown, WR, PF, Sharpe, Sortino, expectancy
- **Output**: Recommendations only
- **Location**: `AI/learning/`

---

## Dual Memory

### Operational Memory (Short-term)
- Current system state
- Cache
- Immediate context
- **Location**: `MEMORY/operational/`

### Institutional Memory (Long-term)
- Full history
- SkillOpinions[], CouncilVerdict, EvidenceGraph, DecisionResult, PolicyResult, RiskResult, TradeResult
- Cryptographic hash per decision
- Component versions
- Reproducible years later
- **Location**: `MEMORY/institutional/`

---

## Evidence Graph

No keyword-based direction inference. Direction emerges from evidence correlation.

**Example**:
| Skill | Evidence |
|-------|----------|
| Trend | EMA200 crescente, Higher High |
| SMC | BOS, CHoCH |
| Volume | RVOL elevado |
| Liquidity | Sweep confirmado |
| Macro | BTC favorável |

Council interprets relationships between evidence clusters.

---

## Observability

Complete metrics system:
- Time per layer, per skill
- Latency
- Average consensus
- Average health
- AGUARDAR rate
- Approval rate
- Rejection reasons (top N)
- CPU / memory usage
- Total cycle time

**Location**: `CORE/observability/`

---

## Official Data Flow

```
Perception Layer
  │ MarketContext
  ▼
World Model
  │ MarketContext + WorldModel
  ▼
Skills (SMC, Volume, ...)
  │ SkillOpinion[]
  ▼
Skill Registry → CEO AI (SkillsEngine)
  │ SkillOpinion[]
  ▼
Consensus Engine
  ├── Evidence Graph Builder
  ├── Health Score Calculator
  ├── Dynamic Weight Calculator
  └── Consensus Calculator
  │ CouncilVerdict
  ▼
Meta Intelligence
  ├── Sufficient info?  → NO → AGUARDAR
  ├── Market clear?     → NO → AGUARDAR
  └── ALL CLEAR ↓
Decision Engine
  ├── Hard Gates
  ├── Policy Engine
  └── Risk Manager
  │ APROVADO | REJEITADO | AGUARDAR
  ▼
Execution Layer
  │
  ▼
Learning Layer + Dual Memory + Observability
```

---

## Event Bus

```
market.data_ready → world.model_updated → skills.opinions_ready →
  council.verdict_ready → meta.hold | meta.proceed →
    decision.made → execution.order
```

---

## Implementation Plan (5 Phases)

### Phase 1 — Foundation
Create:
1. `SkillOpinion` + `SkillMetrics` dataclasses
2. `SkillRegistry` (central registry)
3. `SkillsEngine` (CEO AI orchestrator)
4. `EventBus` integration (existing + extend)
5. `OperationalMemory`
6. `InstitutionalMemory` (DecisionMemory)
7. `BaseSkill` ABC (SkillInterface)

### Phase 2 — Intelligence
Create:
1. SMC Skill, Volume Skill
2. `EvidenceGraph`
3. `ConsensusEngine`
4. `DynamicWeights`
5. `HealthScore`
6. `WorldModel`

### Phase 3 — Cognition
Create:
1. `MetaIntelligence`
2. `DecisionEngine` (rewrite)
3. `PolicyEngine`
4. `RiskManager` adjustments

### Phase 4 — Execution
Integrate:
1. Telegram
2. Exchange (existing BOTS)
3. Paper Trading
4. Audit
5. Observability

### Phase 5 — Evolution
Create:
1. `LearningEngine`
2. `ResearchLab`
3. New skills (Trend, Liquidity, Momentum, Timing, etc.)
4. AI model integration
5. Statistical optimization
6. Distributed scalability

---

## Principles

- Clean Architecture, SOLID, DDD, Event-Driven
- Interface First — immutable contracts
- Low coupling, high cohesion
- Dynamic skill weights (never fixed)
- Evidence Graph (no keyword inference)
- Dual Memory (operational + institutional)
- Full observability
- Capital preservation over profit
- AGUARDAR is always a valid decision
