# RFC V25.8 — Feedback Loop Operacional (Signal Quality Validation)

## Objetivo

Fechar o ciclo de aprendizagem do QuantOS ligando os resultados reais
dos trades (Paper Trading) aos Gates que aprovaram os sinais.

O sistema deve avaliar a QUALIDADE REAL dos sinais gerados, não apenas
o processo de geracao.

## Principios

1. Toda recomendacao deve ser baseada em resultados reais, nao em teoria.
2. Nenhum parametro deve ser alterado automaticamente.
3. O principal criterio continua sendo qualidade institucional
   (Win Rate, Profit Factor, Drawdown, Expectativa).
4. Nao adiantam mais sinais se a qualidade cair.

## Arquitetura

### Estrutura de Arquivos

```
ENGINE/
├── analytics/
│   ├── signal_feedback.py     ★ NOVO — 4 classes
│   └── ...
TESTS/
└── test_rfc_v25_8_signal_feedback.py  ★ NOVO
main.py                                 MODIFICADO — 3 pontos
```

### TradeRecord — Campo Novo

```python
@dataclass
class TradeRecord:
    ...
    gate_snapshot: Optional[Dict[str, Any]] = None
    # {
    #   "rvol_ok": True/False/None,
    #   "adx_ok": True/False/None,
    #   "structure_ok": True/False/None,
    #   "entry_zone_ok": True/False/None,
    #   "quality_ok": True/False/None,
    #   "consensus_ok": True/False/None,
    #   "confidence_ok": True/False/None,
    #   "rr_ok": True/False/None,
    #   "kalman_ok": True/False/None,
    #   "consensus": float,
    #   "quality": float,
    #   "confidence": float,
    #   "coherence_score": float,
    #   "weighted_vote": float,
    # }
```

O campo e opcional (default None) — trades existentes continuam funcionando.

## Componentes

### SignalFeedbackRegistry

Gerencia leitura/escrita do gate_snapshot.

```python
class SignalFeedbackRegistry:
    def __init__(self, trade_registry, trade_analytics):
        self._trade_registry = trade_registry
        self._trade_analytics = trade_analytics
        self._analyzer = GatePerformanceAnalyzer(self)
        self._simulator = NearApprovedSimulator()
        self._learning = LearningEngine(self._analyzer, self._simulator)

    def record_entry(self, signal_id: str, gate_snapshot: Dict) -> None
        # Atualiza TradeRecord.gate_snapshot + TradeRegistry coluna

    def get_trades_by_gate(self, gate_name: str) -> List[TradeRecord]
        # Filtra trades onde gate_snapshot[gate_name] == True

    @property
    def analyzer(self) -> GatePerformanceAnalyzer
    @property
    def simulator(self) -> NearApprovedSimulator
    @property
    def learning_engine(self) -> LearningEngine

    @property
    def all_closed_trades(self) -> List[TradeRecord]
        # Retorna todos os trades fechados com gate_snapshot
```

### GatePerformanceAnalyzer

Agrega performance dos trades por gate.

```python
class GatePerformanceAnalyzer:
    def __init__(self, registry: SignalFeedbackRegistry): ...

    def gate_performance(self, gate_name: str) -> Dict[str, Any]
        # Retorna: count, win_rate, profit_factor, avg_rr,
        #          drawdown, avg_time_to_tp

    def gate_performances(self) -> Dict[str, Dict[str, Any]]
        # Aplica gate_performance para todos os gates com dados

    def gate_performance_report(self) -> str
        # Texto formatado para log
```

### NearApprovedSimulator

Simula resultados virtuais dos quase aprovados.

```python
class NearApprovedSimulator:
    def __init__(self):
        self._virtual: Dict[str, Dict] = {}
        # virtual[signal_id] = {
        #     "entry": float, "stop": float, "tp1": float,
        #     "symbol": str, "direction": str, "outcome": None/"WIN"/"LOSS",
        #     "gate_blocked": str
        # }

    def register(self, signal_id: str, entry: float, stop: float,
                 tp1: float, symbol: str, direction: str,
                 gate_blocked: str) -> None
        # Registra sinal rejeitado para simulacao virtual

    def record_outcome(self, signal_id: str, price: float) -> None
        # Se price >= tp1 → WIN, se price <= stop → LOSS
        # Edge: considerar tempo decorrido (se passou mt tempo sem atingir,
        # contar como LOSS)

    def report(self) -> Dict[str, Any]
        # Retorna: total, wins, losses, win_rate, profit_factor,
        #          pending, por_gate: {gate: {wins, losses, wr, pf}}

    def get_pending(self) -> List[Dict]
        # Sinais ainda sem outcome
```

### LearningEngine

Gera recomendacoes baseadas em evidencias.

```python
class LearningEngine:
    def recommendations(self) -> List[str]
        # Retorna lista de recomendacoes textuais
        # Ex: "Gate CONSENSO: WR 68%, PF 2.45 - Gate eficiente, manter"
        # Ex: "Gate EXAUSTAO bloqueou 38 sinais, 31 seriam STOP - Gate eficiente"
        # Ex: "Gate CONSENSO bloqueou 24 sinais, 18 seriam WIN - Possivel excesso"

    def threshold_report(self, param: str, old: float, new: float,
                         before: Dict, after: Dict) -> str
        # Compara performance antes/depois da alteracao
        # Ex: "CONSENSUS_MINIMUM_SCORE 0.55→0.50: WR 67%→66.8%, PF 2.48→2.50.
        #       Alteracao validada."

    def _classify_gate(self, gate: str, wr: float, blocked_count: int,
                       virtual_wins: int) -> str
        # Returns: "eficiente", "excesso_restricao", "ineficaz", "inconclusivo"
```

## Integracao no main.py

### Init

```python
self._signal_feedback = SignalFeedbackRegistry(
    self._trade_registry, self._trade_analytics
)
```

### Entrada de trade (aprox. linha 870)

```python
self._signal_feedback.record_entry(
    signal_id=trading_data.get("signal_id"),
    gate_snapshot={
        "rvol_ok": best_sd.rvol_ok,
        "adx_ok": best_sd.adx_ok,
        "structure_ok": best_sd.structure_ok,
        "quality_ok": best_sd.quality_ok,
        "consensus_ok": best_sd.consensus_ok,
        "confidence_ok": best_sd.confidence_ok,
        "rr_ok": best_sd.rr_ok,
        "entry_zone_ok": best_sd.entry_zone_ok,
        "consensus": best_sd.consensus,
        "quality": best_sd.quality,
        "confidence": best_sd.confidence,
        "coherence_score": coherence_score,
        "weighted_vote": weighted_vote,
    }
)
```

### Final do ciclo

```python
try:
    _perf = self._signal_feedback.analyzer.gate_performance_report()
    for _line in _perf.split("\n"):
        log.info("GATE_PERF| %s", _line)
    _recs = self._signal_feedback.learning_engine.recommendations()
    for _r in _recs:
        log.info("LEARNING| %s", _r)
except Exception as e:
    log.warning("SignalFeedback: erro: %s", e)
```

Tambem registrar quase aprovados no NearApprovedSimulator no bloco
de processamento de rejeitados (aprox. linha ~952).

## TradeRegistry — Migracao SQLite

```sql
ALTER TABLE trades ADD COLUMN gate_snapshot TEXT DEFAULT '{}';
```

A migration e feita na inicializacao do TradeRegistry com try/except
(caso a coluna ja exista).

## Testes

- `TESTS/test_rfc_v25_8_signal_feedback.py` — ~25 testes
- Registry: record_entry, get_trades_by_gate
- Analyzer: gate_performance, gate_performances
- Simulator: register, record_outcome, report
- Learning: recommendations, threshold_report, _classify_gate

## Criterios de Aceitacao

1. gate_snapshot e populado corretamente na entrada do trade
2. GatePerformanceAnalyzer computa WR/PF/RR/drawdown por gate
3. NearApprovedSimulator registra e avalia resultados virtuais
4. LearningEngine gera recomendacoes sem alterar parametros
5. Tudo protegido por try/except (fail-safe)
6. Schema do TradeRegistry migrado via ALTER TABLE
7. ~25 testes passando
8. 100% dos testes existentes continuam passando
