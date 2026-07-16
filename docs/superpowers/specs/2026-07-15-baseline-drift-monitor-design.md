# RFC V25.7 — Baseline Drift Monitor + Validacao Cientifica

## Objetivo

Criar um sistema permanente de monitoramento da saude operacional do QuantOS
que valide estatisticamente cada alteracao de parametro, detecte desvios de
baseline em tempo real e gere relatorios periodicos automaticos.

Nenhum Gate, Threshold ou parametro deve ser alterado sem evidencias
estatisticas a partir desta versao.

## Principios

1. Nunca ajustar parametros por percepcao — apenas por dados.
2. Toda alteracao deve ter justificativa estatistica.
3. Toda alteracao deve ter comparacao Antes x Depois.
4. Toda alteracao deve ter analise de impacto.
5. Se uma alteracao reduzir significativamente a qualidade, o sistema deve
   recomendar reversao.

## Arquitetura

Tres classes em `ENGINE/analytics/baseline_monitor.py`:

```
BaselineRegistry  →  dados historicos em memoria (deques com maxlen)
       ↓
BaselineAnalyzer  →  calculos estatisticos (stateless)
       ↓
BaselineReporter  →  formatacao para log + Telegram (stateless)
```

Nenhuma classe nova em `ENGINE/diagnostic/`. O arquivo `fast_diagnostic.py`
existente permanece inalterado (compatibilidade).

## BaselineRegistry

### CycleSnapshot (dataclass)

```python
@dataclass
class CycleSnapshot:
    cycle: int
    timestamp: float
    total_analyzed: int
    total_approved: int
    total_rejected: int
    approval_rate: float
    avg_quality: float
    avg_confidence: float
    avg_consensus: float
    avg_rr: float
    gate_percentages: Dict[str, float]
    gate_counts: Dict[str, int]
```

### ParameterChange (dataclass)

```python
@dataclass
class ParameterChange:
    param_name: str
    old_value: Any
    new_value: Any
    reason: str
    timestamp: float
    version: str
    cycle_applied: int
    validated: bool = False
    impact: Optional[str] = None
    impact_data: Optional[Dict] = None
```

### Metodos

- `record_cycle(snapshot: CycleSnapshot)` — append ao deque, atualiza gate_history
- `record_change(param, old, new, reason, version)` — registra alteracao manual
- `cycles_24h` — filtra ultimas ~24h (288 ciclos)
- `cycles_7d` — filtra ultimos ~7d (2016 ciclos)
- `get_gate_trend(gate, hours=24)` — media hist, media recente, delta, status
- `get_gate_trends()` — aplica para todos os gates
- `get_summary_stats()` — medias gerais

## BaselineAnalyzer

Classe stateless que recebe um `BaselineRegistry` e produz analises.

### Metodos

- `top_rejection_gates(registry, n=10, period="24h")` — ranking ordenado
- `gate_with_greatest_growth(registry)` — maior aumento 24h vs historico
- `gate_with_greatest_reduction(registry)` — maior reducao
- `potential_bottlenecks(registry)` — gates >= 25% ou delta >= +10pp
- `potential_bugs(registry)` — gates com delta >= 25pp
- `change_impact(registry, change)` — compara 24h antes vs 24h depois
- `all_changes_validate(registry)` — valida changes pendentes com dados
- `scanner_health(registry)` — trend de approval_rate

### Classificacao de Impacto

| Impacto | Criterio |
|---------|----------|
| 🟢 Positiva | Sinais >= +5% E Win Rate >= -1% E Profit Factor >= +0.05 |
| 🔴 Negativa | Win Rate <= -3% OU Profit Factor <= -0.10 OU Drawdown >= +5% |
| 🟡 Neutra | Demais casos |

## BaselineReporter

Formata dados do Registry + Analyzer para consumo humano.

### Metodos

- `build_30min_report(registry)` — dicionario completo com todos os blocos
- `format_30min_log(report)` — texto para logger (prefixo "30MIN|")
- `format_30min_telegram(report)` — resumo para Telegram com emojis
- `build_change_report(change, impact)` — validacao de alteracao individual

### Estrutura do Relatorio 30min

```python
{
    "scanner_health": {...},
    "market": "Forte | Fraco | Lateral",
    "total_analyzed": 120,
    "total_approved": 3,
    "approval_rate": 2.5,
    "top_rejection_reasons": [...],    # Top 10
    "top_near_approved": 5,
    "gate_greatest_growth": {...},
    "gate_greatest_reduction": {...},
    "potential_bottlenecks": [...],
    "potential_bugs": [...],
    "baseline_comparison": {...},
    "pending_validations": [...],
}
```

## Integracao no main.py

### Init (no `__init__`)

```python
self._baseline_registry = BaselineRegistry()
self._baseline_analyzer = BaselineAnalyzer()
self._baseline_reporter = BaselineReporter(self._baseline_analyzer)
```

### Fim de cada ciclo (apos rejection_summary)

```python
snapshot = CycleSnapshot(
    cycle=self._scan_count,
    timestamp=time.time(),
    total_analyzed=rejection_summary.get("total_analyzed", 0),
    total_approved=rejection_summary.get("total_approved", 0),
    total_rejected=rejection_summary.get("total_rejected", 0),
    approval_rate=rejection_summary.get("approval_rate", 0.0),
    avg_quality=rejection_summary.get("avg_quality", 0.0),
    avg_confidence=rejection_summary.get("avg_confidence", 0.0),
    avg_consensus=rejection_summary.get("avg_consensus", 0.0),
    avg_rr=rejection_summary.get("avg_rr", 0.0),
    gate_percentages=rejection_summary.get("gate_percentages", {}),
    gate_counts=rejection_summary.get("gate_counts", {}),
)
self._baseline_registry.record_cycle(snapshot)
```

### Timer 30 minutos

```python
_now = time.time()
if _now - self._baseline_registry._last_30min_report >= 1800:
    self._baseline_registry._last_30min_report = _now
    report = self._baseline_reporter.build_30min_report(self._baseline_registry)
    for _line in self._baseline_reporter.format_30min_log(report).split("\n"):
        log.info("30MIN| %s", _line)
    self._telegram.send_30min_report(
        self._baseline_reporter.format_30min_telegram(report)
    )
```

### Registro de change manual (exemplo)

```python
self._baseline_registry.record_change(
    param="CONSENSUS_MINIMUM_SCORE",
    old=0.55, new=0.50,
    reason="RFC V25.6 - Ajuste para permitir sinais sem perder qualidade",
    version="RFC V25.6"
)
```

### Seguranca

Toda a integracao protegida por try/except com log.warning em caso de falha.

## Arquivos Alterados/Criados

| Arquivo | Acao |
|---------|------|
| `ENGINE/analytics/baseline_monitor.py` | ★ CRIADO — 3 classes (~450 linhas) |
| `main.py` | MODIFICADO — init + fim de ciclo + timer 30min |
| `TESTS/test_rfc_v25_7_baseline_monitor.py` | ★ CRIADO — ~25-30 testes |

## Criterios de Aceitacao

1. BaselineRegistry acumula dados de ciclo corretamente (append, janela, maxlen)
2. Gate trends detectam variacao normal vs anormal (delta >= 25pp)
3. ParameterChange registra e valida apos 24h com dados reais
4. Relatorio de 30min contem todos os blocos especificados
5. Relatorio de 30min e enviado ao log + Telegram
6. Change impact classifica como 🟢🟡🔴 corretamente
7. Toda integracao e fail-safe (try/except)
8. 100% dos testes unitarios existentes continuam passando
9. 25-30 novos testes criados e passando
