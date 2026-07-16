# RFC V21.0 — SINGLE SOURCE OF TRUTH

**Arquitetura Institucional — Decisão Única e Irrevogável**

- **Data**: 2026-07-13
- **Versão Atual**: V18.4
- **Versão Proposta**: V21.0
- **Status**: RFC — Aguardando Aprovação

---

## 1. SUMÁRIO EXECUTIVO

### Problema

A auditoria V20 (7 dias de log, 699.907 linhas) revelou:

| Métrica | Valor |
|---|---|
| Sinais que passam no Decision Engine | 772 |
| Sinais que chegam ao Telegram | 708 |
| Rejeitados pelo SignalValidator (bot) | 2.598 |
| Rejeitados pela Final Validation | 2 |
| Rejeitados por dedup/cache | 252 |
| **Total de rejeições pós-engine** | **2.852** |
| Post-Engine re-evaluations of approval | **28+** |
| Points that can override engine decision | **12** |
| Duplicate validation checks | **16** |
| Conflicting thresholds (engine vs bot) | **4** |

O sistema atual valida o mesmo sinal **28+ vezes** após a decisão do Decision Engine, com **12 pontos** onde uma decisão já aprovada pode ser revertida.

### Solução

Unificar toda a validação em **um único pipeline**, criar o **InstitutionalSignal** como objeto canônico, e transformar todos os consumidores downstream em **leitores passivos** que nunca recalculam regras de negócio.

### Impacto Esperado

| Métrica | Antes | Depois |
|---|---|---|
| Pontos de validação duplicada | 28+ | 1 (pipeline único) |
| Objetos de sinal diferentes | 8 (Signal, SignalDecision x2, SignalData, SignalRecord, ActiveOperation, _AttrDict, dict) | 1 (InstitutionalSignal) |
| Thresholds conflitantes | 4 pares | 0 |
| Manutenção necessária por alteração | 5+ arquivos | 1 (InstitutionalPipeline) |
| Tempo de debug médio | Alto (rastrear entre camadas) | Baixo (trace único) |

---

## 2. DIAGNÓSTICO COMPLETO — 28 REAVALIAÇÕES PÓS-DECISÃO

### 2.1 Cálculos Sintéticos (14)

Após o Decision Engine aprovar (`sd.approved = True`), main.py recalcula:

| # | Score | Onde | Redundância |
|---|---|---|---|
| 1 | overall_score | `operational.py:compute_overall_score()` | Recalcula peso de 10 scores já conhecidos |
| 2 | conviction_level | `operational.py:compute_conviction_level()` | Média de confidence, quality, consensus |
| 3 | expectancy_level | `operational.py:compute_expectancy_level()` | 13 fatores, todos já no SignalDecision |
| 4 | time_to_tp1 | `operational.py:estimate_time_to_tp1()` | Apenas estimativa (não bloqueante) |
| 5 | penalties | `operational.py:compute_penalties()` | Reinterpreta scores como penalidades |
| 6 | confluence_score | `operational.py:compute_confluence_score()` | 8 alinhamentos recalculados |
| 7 | risk_decomposition | `operational.py:compute_risk_decomposition()` | 6 componentes de risco recalculados |
| 8 | main_reason | `operational.py:compute_main_reason()` | Sumário textual |
| 9 | mtf_conflict | `operational.py:detect_mtf_conflict()` | Conflito entre timeframes |
| 10 | probability | `operational.py:compute_probability()` | **Novo score de probabilidade (0-100)** |
| 11 | coherence_audit | `operational.py:compute_coherence_audit()` | 7 módulos reavaliados |
| 12 | coherence_score | `operational.py:compute_institutional_coherence_score()` | **Novo score (0-100) que pode bloquear** |
| 13 | weighted_vote | `operational.py:compute_weighted_vote()` | **Nova aprovação booleana que pode bloquear** |
| 14 | penalty_details | `operational.py:compute_coarse_penalty_details()` | Detalhamento de gates |

### 2.2 Final Validation (9)

Após os cálculos, main.py reaplica 9 gates:

| # | Check | Fonte | Gate Original | Problema |
|---|---|---|---|---|
| 1 | Kalman LONG+DOWN | SignalDecision | Gate 12 | **Duplicado** |
| 2 | Kalman SHORT+UP | SignalDecision | Gate 12 | **Duplicado** |
| 3 | OURO + score < 70 | overall_score | Novo | Não existia no engine |
| 4 | PLATINA + score < 80 | overall_score | Novo | Não existia no engine |
| 5 | DIAMANTE + score < 90 | overall_score | Novo | Não existia no engine |
| 6 | Ranging + alta expectativa | coherence_audit | Novo | Não existia no engine |
| 7 | Classificação divergente | classification_label | Novo | Não existia no engine |
| 8 | Coherence Score < 60 | coherence_score | Novo | Não existia no engine |
| 9 | Weighted Vote < 70% | weighted_vote | Gate 14 | **Duplicado** |

### 2.3 Pré-Envio (5)

| # | Check | Módulo | Problema |
|---|---|---|---|
| 1 | Impact Score | `UpdateEngine.calculate_impact_score()` | Recalcula 18+ deltas |
| 2 | Candle Dedup | `SignalCacheEngine.can_send()` | Cache paralelo |
| 3 | Dados obrigatórios | `telegram_validator.validate_signal_data()` | Campos já existentes no SD |
| 4 | 8 gates _ok | `telegram_validator.validate_consistency()` | **Todos já passaram no engine** |
| 5 | Preços/RR/Tier | `telegram_validator.validate_presentation_consistency()` | Já válidos no SD |

---

## 3. ARQUITETURA PROPOSTA

### 3.1 Novo Pipeline

```
                    ┌─────────────┐
                    │   Scanner   │
                    │  (detecção) │
                    └──────┬──────┘
                           │ Signal (raw)
                           ▼
                    ┌─────────────┐
                    │  Decision   │
                    │   Engine    │
                    │  (16 gates) │
                    └──────┬──────┘
                           │ SignalDecision
                           ▼
                    ┌─────────────┐
                    │    Risk     │
                    │   Engine    │
                    │ (SL/TP/RR)  │
                    └──────┬──────┘
                           │ Enriched SD
                           ▼
                    ┌─────────────┐
                    │   Score     │
                    │  Computor   │
                    │ (14 scores) │
                    └──────┬──────┘
                           │ Complete SD
                           ▼
                    ┌─────────────┐
                    │   Final     │
                    │  Validation │
                    │ (9 checks)  │
                    └──────┬──────┘
                           │ APPROVED/REJECTED
                           ▼
                    ┌─────────────────────┐
                    │   Institutional     │
                    │  Signal (canônico)  │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │   Telegram   │   │    Logger    │   │    Cache     │
   │  (formatar)  │   │  (registrar) │   │ (dedup c/   │
   │              │   │              │   │  DecisionID) │
   └──────────────┘   └──────────────┘   └──────┬───────┘
                                                │
          ┌─────────────────────────────────────┼─────────┐
          ▼                                     ▼         ▼
   ┌──────────────┐                    ┌──────────────┐
   │  Dashboard   │                    │  REST API    │
   │  (consumir)  │                    │  (expor)     │
   └──────────────┘                    └──────────────┘
```

### 3.2 Fluxo de Decisão

```
Scanner emite Signal (raw, sem decisão)
  │
  ▼
Pipeline.InstitutionalPipeline.process(signal)
  │
  ├── 1. DecisionEngine.evaluate(signal) → SignalDecision
  │     ├── Gate 1-16 (todas as validações)
  │     ├── RiskManager.apply() (SL/TP/RR)
  │     └── Sets sd.approved = True/False
  │
  ├── 2. ScoreComputor.compute(sd) → enriched_sd
  │     ├── overall_score, conviction, expectancy
  │     ├── probability, coherence, weighted_vote
  │     └── confluence, risk_decomposition, penalties
  │
  ├── 3. FinalValidation.validate(enriched_sd) → InstitutionalSignal
  │     ├── Re-checks Kalman (uma vez, centralizado)
  │     ├── Re-checks tier/score alignment
  │     ├── Re-checks coherence + weighted_vote
  │     └── Produz InstitutionalSignal (único objeto de saída)
  │
  └── 4. Publica InstitutionalSignal via EventBus
        ├── Se approved → Telegram (formata apenas)
        ├── Se approved → SignalCache (dedup por DecisionID)
        ├── Se approved → Logger (salva)
        ├── Se rejected → Logger (salva motivo)
        └── Se rejected → Diagnostic (estatística)
```

### 3.3 InstitutionalSignal

Objeto canônico que substitui TODOS os objetos de sinal existentes:

```python
@dataclass(frozen=True)
class InstitutionalSignal:
    # Identificação
    decision_id: str           # QE-2026-07-13-0000001
    trace_id: str              # SIG-20260713-XXXXX (rastreabilidade)
    timestamp: datetime
    engine_version: str        # "V21.0"

    # Ativo
    symbol: str                # "BTCUSDT"
    exchange: str              # "MEXC"
    timeframe: str             # "1h"
    direction: Direction       # LONG / SHORT

    # Preços (decididos pelo Risk Engine)
    entry_price: Decimal
    stop_loss: Decimal
    take_profit_1: Decimal
    take_profit_2: Optional[Decimal]
    risk_reward: float

    # Scores da decisão (imutáveis após decisão)
    quality: float
    confidence: float
    entry_score: float
    consensus_score: float
    conviction: float
    institutional_score: float

    # Indicadores (registro do momento da decisão)
    rvol: float
    adx: float
    atr: float
    volatility: float
    trend: str
    market_regime: str
    kalman_direction: str
    flow: float
    liquidity: float
    structure_strength: float
    momentum: float

    # Scores sintéticos (calculados uma vez no pipeline)
    overall_score: float
    overall_tier: str
    probability: float
    coherence_score: float
    weighted_vote_concordance: float
    weighted_vote_approved: bool

    # Decisão (final e irrevogável)
    approved: bool
    approval_reason: str       # "APROVADO - Todos os filtros"
    rejection_reason: str      # preenchido se rejected
    rejection_gate: str        # "RVOL", "ADX", etc.
    warnings: List[str]

    # Rastreamento
    pipeline_trace: PipelineTrace
    metadata: Dict[str, Any]
```

### 3.4 Decision ID

Formato: `QE-YYYY-MM-DD-NNNNNNN`

- `QE` = Quantos Engine
- `YYYY-MM-DD` = data
- `NNNNNNN` = sequencial (7 dígitos, zeriado)

O DecisionID é gerado na entrada do pipeline e **persiste por todo o ciclo de vida do sinal**, incluindo operação, updates e encerramento.

---

## 4. MUDANÇAS EM CADA MÓDULO

### 4.1 Módulos a Remover

| Módulo | Arquivo | Motivo |
|---|---|---|
| SignalValidator | `BOTS/mexc/signals/signal_validator.py` | TransportValidator substitui (16 checks agora no engine) |
| TelegramValidator | `SERVICES/telegram/telegram_validator.py` | Validação duplicada dos gates |
| ConsistencyValidator | `ENGINE/validation/consistency_validator.py` | Dead code — nunca chamado no pipeline |
| _AttrDict / wrap_signal | `SERVICES/telegram/signal_compat.py` | InstitutionalSignal já é objeto tipado |
| SignalDecision (scanner_types) | `ENGINE/scanner/scanner_types.py` | Substituído por InstitutionalSignal |
| SignalCacheEngine | `ENGINE/deduplication/signal_cache.py` | Substituído por cache baseado em DecisionID |
| SelfAuditEngine | `ENGINE/decision/self_audit.py` | Lógica incorporada ao pipeline trace |

### 4.2 Módulos a Modificar

| Módulo | Mudança |
|---|---|
| `decision_engine.py` | Incorporar as 9 validações da Final Validation + os 14 cálculos sintéticos |
| `main.py` | Reduzir de ~1294 para ~500 linhas. Remover toda lógica de validação pós-engine |
| `telegram_service.py` | Remover `validate_consistency`, `validate_presentation_consistency`, `wrap_signal`. Apenas formatar |
| `telegram_formatter.py` | Remover `_unwrap()`, `_get()`. Receber InstitutionalSignal diretamente |
| `active_signal_manager.py` | Usar DecisionID como chave. Armazenar InstitutionalSignal completo |
| `update_engine.py` | Comparar InstitutionalSignal antigo vs novo (já tem todos os campos) |
| `signal_tracker.py` | Usar DecisionID. Armazenar InstitutionalSignal |
| `paper_trading.py` | Receber InstitutionalSignal diretamente |
| `bot_engine.py` | Remover SignalValidator. Usar TransportValidator |
| `signal_receiver.py` | Receber InstitutionalSignal (não mais dict) |
| `operational.py` | Incorporado ao pipeline como ScoreComputor |
| `publishers.py` | Publicar InstitutionalSignal (não mais dict genérico) |
| `event_bus.py` | Tipos de evento baseados em InstitutionalSignal |

### 4.3 Módulos Não Alterados

| Módulo | Motivo |
|---|---|
| `scanner_engine.py` | Continua gerando Signal (raw) — não muda |
| `scanner_types.py` | Signal mantido como entrada do pipeline |
| `scanner_config.py` | Thresholds movidos para config central, mas valores não mudam |
| `risk_manager.py` | Continua calculando SL/TP/RR — chamado pelo pipeline |
| `consensus_engine.py` | Continua calculando consenso — chamado pelo scanner |
| `confluence_engine.py` | Continua calculando confluência — chamado pelo scanner |
| `diagnostic/engine.py` | Apenas consome estatísticas — não valida |
| `health_monitor.py` | Independendente do pipeline de sinais |
| `watchdog/` | Independendente do pipeline de sinais |

### 4.4 Dependências entre Módulos (Nova Arquitetura)

```
InstitutionalPipeline
  ├── importa: DecisionEngine, RiskManager, ScoreComputor, FinalValidation
  ├── produz: InstitutionalSignal
  └── publica: EventBus[InstitutionalSignal]

TelegramService
  ├── assina: EventBus[InstitutionalSignal]
  ├── importa: InstitutionalSignal (tipo)
  └── formata: (sem validação)

BotEngine
  ├── assina: EventBus[InstitutionalSignal]
  ├── importa: TransportValidator (sintaxe/JSON)
  └── executa: se approved=True

Dashboard
  └── consome: InstitutionalSignal (via API/DB)

Logger
  └── registra: InstitutionalSignal (via EventBus)
```

---

## 5. TRANSPORT VALIDATOR

Substitui o SignalValidator. **NÃO** valida regras de negócio — apenas integridade do transporte.

```python
class TransportValidator:
    def validate(signal: InstitutionalSignal) -> TransportResult:
        # Apenas verifica:
        # 1. JSON válido
        # 2. Campos obrigatórios preenchidos
        # 3. Nenhum valor None/NaN em campos críticos
        # 4. Tipos corretos (str, float, bool)
        # 5. Timestamps válidos
        # 6. Preços > 0
        # NÃO verifica: quality, confidence, RVOL, ADX, trend, kalman, etc.
```

---

## 6. DECISION LOGGER

```python
class DecisionLogger:
    def log(signal: InstitutionalSignal):
        entry = {
            "decision_id": signal.decision_id,
            "timestamp": signal.timestamp.isoformat(),
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            "direction": signal.direction,
            "approved": signal.approved,
            "approval_reason": signal.approval_reason,
            "rejection_reason": signal.rejection_reason,
            "rejection_gate": signal.rejection_gate,
            "pipeline_trace": signal.pipeline_trace.to_dict(),
            "quality": signal.quality,
            "confidence": signal.confidence,
            "overall_score": signal.overall_score,
            "coherence_score": signal.coherence_score,
            "weighted_vote": signal.weighted_vote_concordance,
        }
        # Salva em: logs/decisions/YYYY-MM-DD/decision_id.json
```

---

## 7. AUDIT REPLAY

```python
class AuditReplay:
    @staticmethod
    def get_decision(decision_id: str) -> InstitutionalSignal:
        # Carrega do log
        pass

    @staticmethod
    def trace(decision_id: str) -> PipelineTrace:
        # Retorna o trace completo do pipeline
        pass

    @staticmethod
    def why_entered(decision_id: str) -> str:
        # Por que foi aprovado
        pass

    @staticmethod
    def why_exited(trade_id: str) -> str:
        # Por que saiu (TP/SL/cancelamento)
        pass
```

---

## 8. BACKTEST POR GATE

O InstitutionalSignal mantém todos os scores que passaram por cada gate. Com isso, é possível:

```python
class GateBacktest:
    @staticmethod
    def win_rate_by_gate(gate_name: str, threshold: float) -> dict:
        # Analisa logs de decisões passadas
        # Para cada decisão, verifica se passaria com novo threshold
        # Retorna win rate estimado, profit factor, drawdown
        pass
```

---

## 9. PLANO DE MIGRAÇÃO

### Fase 1 — InstitutionalSignal (dia 1-2)

1. Criar dataclass `InstitutionalSignal` em `ENGINE/pipeline/institutional_signal.py`
2. Criar `DecisionID` generator
3. Criar `PipelineTrace` dataclass
4. Criar `InstitutionalPipeline.process()` que unifica DecisionEngine → ScoreComputor → FinalValidation
5. Adicionar testes unitários

### Fase 2 — Consumers (dia 3-4)

1. Modificar `TelegramService` para receber InstitutionalSignal
2. Modificar `ActiveSignalManager` para usar DecisionID
3. Modificar `SignalTracker` para usar InstitutionalSignal
4. Substituir `wrap_signal()` por acesso direto a InstitutionalSignal
5. Remover `TelegramValidator`
6. Adicionar testes de integração

### Fase 3 — Bot Layer (dia 5-6)

1. Substituir `SignalValidator` por `TransportValidator`
2. Modificar `SignalReceiver` para receber InstitutionalSignal
3. Remover `SignalCacheEngine` — substituir por cache baseado em DecisionID
4. Remover `SelfAuditEngine`
5. Adicionar testes de integração bot

### Fase 4 — Cleanup (dia 7-8)

1. Remover `_AttrDict`, `wrap_signal`, `signal_compat.py`
2. Remover `ConsistencyValidator` (dead code)
3. Remover `telegram_validator.py`
4. Simplificar `main.py` (~500 linhas)
5. Adicionar `DecisionLogger`
6. Adicionar `AuditReplay`
7. Remover `SelfAuditEngine`
8. Full regression tests

### Fase 5 — Documentação (dia 9)

1. Atualizar ARCHITECTURE.md
2. Atualizar CHANGELOG.md
3. Atualizar TEST_REPORT.md
4. Remover referências a módulos removidos
5. Gerar documentação da nova API

---

## 10. COMPATIBILIDADE RETROATIVA

### APIs Externas

- Nenhuma API externa é quebrada — o InstitutionalSignal será serializado como JSON com os mesmos campos que o dict atual
- Campos adicionais (`decision_id`, `pipeline_trace`) são adicionados, não removidos

### Dados Persistentes

- `MEMORY/state/signals.json` — formato continua compatível (InstitutionalSignal serializado)
- `MEMORY/state/active_operations.json` — migração automática na primeira execução
- `paper_trading.json` — compatível

### Integrações

- Telegram: mensagens mantêm o mesmo formato (formatter continua igual, só muda a fonte de dados)
- Dashboard: consumirá InstitutionalSignal serializado
- REST API: expor InstitutionalSignal diretamente

---

## 11. RISCOS E MITIGAÇÕES

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Bug na unificação dos 16+9 gates | Média | Fase 1: testes unitários exaustivos comparando output do pipeline antigo vs novo |
| Perda de campo durante migração | Alta | Teste de schemas: InstitutionalSignal.to_dict() deve conter todos os campos do dict atual |
| Quebra no Telegram formatting | Média | Fase 2: teste side-by-side das mensagens antigas vs novas |
| Regressão no bot engine | Média | Fase 3: paper trading comparativo antes/depois |
| Esquecimento de alguma validação | Baixa | Auditoria V20 já mapeou 100% dos gates |

---

## 12. CRITÉRIOS DE ACEITAÇÃO

1. [ ] Pipeline único processa sinal e produz InstitutionalSignal com todos os 28 checks
2. [ ] InstitutionalSignal.approved é a ÚNICA fonte de verdade para decisão
3. [ ] Nenhum módulo downstream recalcula quality/confidence/RVOL/ADX/Kalman/trend
4. [ ] Telegram formata sem validar (0 validações no TelegramService)
5. [ ] TransportValidator verifica apenas JSON/campos/tipos (0 regras de negócio)
6. [ ] DecisionID único rastreia o sinal do scanner ao encerramento
7. [ ] PipelineTrace registra todos os gates + tempos
8. [ ] AuditReplay permite consultar qualquer decisão por DecisionID
9. [ ] main.py reduz de 1294 para ~500 linhas
10. [ ] 100% dos testes existentes passam sem modificação
11. [ ] Nenhuma API externa quebrada
12. [ ] Dados persistentes migram automaticamente

---

## 13. ESTRATÉGIA DE ROLLBACK

1. **Fase 1**: Manter `decision_engine.py` e `main.py` atuais em paralelo. Novo pipeline em `ENGINE/pipeline/`. Alternar via env var `QUANTOS_PIPELINE_VERSION=v18|v21`.
2. **Fase 2**: Manter `wrap_signal()` como fallback. Se `_AttrDict` não for mais criado, o TelegramFormatter tem `_unwrap()` que retorna dict.
3. **Fase 3-4**: Manter `SignalValidator` desativado (não removido) por 2 ciclos de scan. Se algo falhar, reativar.
4. **Rollback total**: `git revert` + restaurar `main.py` e configs de importação.
