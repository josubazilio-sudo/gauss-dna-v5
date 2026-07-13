# QUANTOS X V10.0 — ARTIFICIAL MARKET INTELLIGENCE OPERATING SYSTEM (AMI-OS)

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                  QUANTOS X V9.1 AMI-OS                            │
│  8 Cognitive Layers, Evidence Graph, Dynamic Weights, Meta AI    │
└──────────────────────────────────────────────────────────────────┘
```

## The 8 Cognitive Layers

### 1. Perception Layer
- **Responsibility**: Observe the market. No decisions.
- **Input**: Exchange API (OHLCV, Order Book, Trades, Funding, OI, Dominance, Correlation)
- **Output**: `MarketContext` (standardized object)
- **Location**: `ENGINE/market/market_engine.py`, `CORE/data_providers/`

### 2. Analysis Layer (Skills)
- **Responsibility**: Specialized technical analysis. No decisions.
- **Composition**: N independent Skills, each with a single specialty
- **Contract** (Universal):
  ```python
  @dataclass
  SkillOpinion:
      skill_name: str
      confidence: float    # 0.0-1.0
      risk: float          # 0.0-1.0
      probability: float   # 0.0-1.0
      evidence: List[str]  # structured facts (no direction keywords)
      observations: str    # technical text
      success: bool        # execution status
      metrics: SkillMetrics  # health score
  ```
- **Rules**:
  - Skills never communicate directly with each other
  - Skills never know the final decision
  - Skills never include direction, recommendation, or vote
  - Skills produce only structured evidence (e.g., "BOS confirmado", "RVOL 2.3x")
  - Skills can be deterministic algorithms OR AI models (same contract)
- **Phase 1 Skills**: SMC, Volume
- **Location**: `ENGINE/skills/`

### 3. Orchestration Layer (CEO AI)
- **Responsibility**: Coordinate, distribute, manage execution flow
- **Composition**: `SkillsEngine` — registers all skills, executes parallel analysis, collects opinions, publishes events
- **Rules**:
  - Never interprets indicators
  - Never approves operations
  - New skills added by registration only
- **Location**: `ENGINE/skills/skills_engine.py`

### 4. Reasoning Layer (Conselho Institucional)

**4a. Evidence Graph Builder**
- **Responsibility**: Build an Evidence Graph correlating convergent and divergent evidence from all skills
- **Method**: Evidence is grouped by directionality (compra/venda, alta/baixa) using structured evidence text analysis
- **Output**: EvidenceGraph with convergent and divergent evidence clusters
- **Location**: `ENGINE/council/evidence_graph.py`

**4b. Consensus Engine**
- **Responsibility**: Consolidate pareceres, detect conflicts, calculate global confidence/risk/consensus
- **Input**: `List[SkillOpinion]`
- **Output**: `CouncilVerdict`
  ```python
  @dataclass
  CouncilVerdict:
      direction: str           # LONG | SHORT | NEUTRAL (inferred from Evidence Graph)
      avg_confidence: float    # weighted by dynamic skill weight
      avg_risk: float          # weighted by dynamic skill weight
      consensus_score: float   # 0.0-1.0
      evidence_graph: EvidenceGraph  # full correlation structure
      conflictos: List[str]
      pareceres: List[SkillOpinion]
  ```
- **Direction inference**: NOT by keyword. Built from Evidence Graph — correlate evidence clusters to infer market context.
- **Dynamic weights**: Each skill weight adjusted by historical performance, market regime, setup type, volatility, current context
- **Location**: `ENGINE/council/consensus_engine.py`

### 5. Meta Intelligence Layer
- **Responsibility**: Answer pre-decision questions before engaging Decision Engine
- **Questions**:
  - Is information sufficient?
  - Is the market clear?
  - Are there relevant conflicts?
  - Is evidence quality sufficient?
  - Is there statistical advantage?
  - Is it worth continuing?
- **Output**: If ANY question answers negative → `AGUARDAR` immediately (short-circuit)
- **Purpose**: Avoid unnecessary processing, reduce low-quality signals
- **Location**: `ENGINE/meta/meta_intelligence.py`

### 6. Decision Layer (Decision Engine)
- **Responsibility**: Sole authority to decide
- **Input**: ONLY `CouncilVerdict` (never individual SkillOpinions)
- **Output**: `DecisionResult`
  ```python
  @dataclass
  DecisionResult:
      decision: str          # APROVADO | REJEITADO | AGUARDAR
      reasons: List[str]     # full justification
      risk_result: Optional[RiskResult]
  ```
- **Hard Gates** (applied only on CouncilVerdict — NEVER on raw indicators or individual skills):
  1. All skills executed successfully
  2. `avg_confidence >= 0.70`
  3. `avg_risk <= 0.40`
  4. `consensus_score >= 0.60`
  5. Evidence Graph quality >= threshold
  6. No critical conflicts in Evidence Graph
  7. `direction != NEUTRAL`
  8. `RiskManager.apply()` valid
  9. `RR >= 2.0`
- If any Hard Gate fails and doubt exists → `AGUARDAR` (not REJEITADO)
- **Location**: `ENGINE/decision/decision_engine.py`

### 7. Execution Layer
- **Responsibility**: Execute approved decisions only
- **Components**: Telegram, Paper Trading, Exchange bots, Logs, Audit
- **Rules**: Never creates signals. Never interprets indicators. Only receives approved ops.
- **Location**: `SERVICES/telegram/`, `CORE/trading/paper_trading.py`, `BOTS/`

### 8. Learning Layer
- **Responsibility**: Register and analyze results. Never auto-modifies production rules.
- **Records**: market context, pareceres, verdict, gates, risk, result, drawdown, WR, PF, expectancy
- **Output**: Recommendations only (for human or institutional review)
- **Location**: `AI/learning/`

## Official Data Flow

```
Perception Layer
  ↓ (MarketContext)
Skills (SMC, Volume, ...)
  ↓ (SkillOpinion[])
CEO AI (SkillsEngine)
  ↓ (SkillOpinion[])
Consensus Engine
  ├── Evidence Graph Builder
  ├── Conflict/convergence detection
  ├── Dynamic weight calculation
  └── CouncilVerdict
  ↓ (CouncilVerdict)
Meta Intelligence
  ├── Sufficient info? → NO → AGUARDAR
  ├── Market clear? → NO → AGUARDAR
  ├── Relevant conflicts? → YES → AGUARDAR
  ├── Evidence quality? → LOW → AGUARDAR
  └── ALL YES ↓
Decision Engine
  ├── Hard Gates (on CouncilVerdict only)
  ├── Risk Manager
  └── APROVADO | REJEITADO | AGUARDAR
  ↓ (DecisionResult)
Execution Layer (Telegram, Paper, Exchange)
  ↓
Learning Layer (register + analyze)
```

## Event Bus

```
[C Perception] ──market.data_ready──▶
  [CEO AI] ──skills.opinions_ready──▶
    [Reasoning] ──council.verdict_ready──▶
      [Meta] ──meta.hold (AGUARDAR) | meta.proceed──▶
        [Decision] ──decision.made──▶
          [Execution]
```

## Skill Health Score

Every skill tracks:
- `availability`: uptime ratio
- `avg_latency_ms`: average execution time
- `historical_success_rate`: % of times analysis completed
- `historical_precision`: accuracy vs actual market movements
- `last_execution`: timestamp
- `recent_errors`: count of consecutive failures
- `reliability`: composite score (0.0-1.0)

Council dynamically reduces weight of degraded skills.

## Dynamic Weights

Skill weights are calculated per cycle:
- Base weight (from config)
- Adjusted by health score (degraded skills lose weight)
- Adjusted by market regime (Trend stronger in trends, SMC stronger in reversals)
- Adjusted by context (volatility, setup type)

Weights are never static.

## Evidence Graph

```
SkillOpinion[].evidence
  │
  ▼
EvidenceGraph:
  convergent_evidence: Dict[str, List[str]]  # grouped by theme
  divergent_evidence: Dict[str, List[str]]   # conflicting themes
  direction_clusters: Dict[str, float]       # LONG/SHORT evidence mass
  evidence_quality: float                    # overall quality score
  conflicts: List[str]
```

Direction emerges from evidence mass, not keywords.

## Decision Memory (Institutional Knowledge Base)

Every decision stores:
- `MarketContext` (hash+snapshot)
- `SkillOpinion[]` (every parecer)
- `CouncilVerdict` (full)
- `DecisionResult` (with reasons)
- `RiskResult` (SL/TP/RR)
- Trade outcome (filled later)
- Pipeline hash (reproducible)

**Location**: `MEMORY/decisions/` (SQLite or JSON)

## Research Lab Isolation Path

```
Research Lab (LAB/)
  │
  ├── New skill prototype
  ├── New indicator
  ├── New algorithm
  │
  ▼
Backtest (ENGINE/backtest/)
  │
  ▼
Paper Trading (CORE/trading/paper_trading.py)
  │
  ▼
Statistical Validation (AUDIT/)
  │
  ▼
Approval → Production

Never bypass this path.
```

## Principle of Uncertainty

When any of the following is true:
- Insufficient evidence
- Weak consensus
- Conflict between specialists
- Elevated risk
- Undefined market context
- Low evidence quality

The institutional response is: **AGUARDAR**

Missing an opportunity is preferable to unnecessary risk.

## Phase 1 Implementation Plan

### New files (14):
| # | File | Purpose |
|---|------|---------|
| 1 | `ENGINE/skills/skill_opinion.py` | SkillOpinion + SkillMetrics dataclasses |
| 2 | `ENGINE/skills/base.py` | SkillInterface ABC |
| 3 | `ENGINE/skills/smc_skill.py` | SMC Skill |
| 4 | `ENGINE/skills/volume_skill.py` | Volume Skill |
| 5 | `ENGINE/skills/skills_engine.py` | CEO AI orchestrator |
| 6 | `ENGINE/council/council_types.py` | CouncilVerdict dataclass |
| 7 | `ENGINE/council/council_config.py` | Weights, thresholds, config |
| 8 | `ENGINE/council/evidence_graph.py` | Evidence Graph builder |
| 9 | `ENGINE/council/consensus_engine.py` | Consensus Engine |
| 10 | `ENGINE/meta/meta_intelligence.py` | Meta Intelligence layer |
| 11 | `ENGINE/meta/meta_config.py` | Meta thresholds |
| 12 | `ENGINE/decision/decision_types.py` | DecisionResult + Decision enum |
| 13 | `ENGINE/decision/decision_memory.py` | Decision memory/knowledge base |
| 14 | `ENGINE/skills/skill_health.py` | Skill health metrics registry |

### Modified files (5):
| # | File | Change |
|---|------|--------|
| 15 | `ENGINE/decision/decision_engine.py` | Read only CouncilVerdict; 9 gates; AGUARDAR |
| 16 | `ENGINE/decision/signal_decision.py` | Add AGUARDAR support |
| 17 | `ENGINE/risk/risk_manager.py` | Adjust for new flow |
| 18 | `ENGINE/scanner/scanner_engine.py` | Reduce to data processor |
| 19 | `main.py` | Wire new architecture |

### Deprecated (2):
| # | File | Reason |
|---|------|--------|
| 20 | `ENGINE/scanner/decision_engine.py` | Replaced by V9 architecture |
| 21 | `ENGINE/scanner/evidence_registry.py` | Audit moved to Decision Memory |

## Principles

- Low coupling, high cohesion
- Single responsibility per module
- Determinism: same inputs → same outputs
- Evidence-based reasoning (Evidence Graph)
- Dynamic skill weighting
- Meta Intelligence as pre-decision filter
- Full auditability via Decision Memory
- Every decision explainable in natural language
- Capital preservation over opportunity capture
- AGUARDAR is always a valid decision
