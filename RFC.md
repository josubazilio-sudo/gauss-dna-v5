# RFC V19.1 — AUTO-OTIMIZACAO DO TAKE PROFIT

Data: 2026-07-11

## Objetivo
Transformar o modulo TP Adaptativo (V19.0) em um sistema autoevolutivo baseado em estatisticas reais de Paper Trading. O sistema registra cada saida, calcula eficiencia do TP, detecta rejeicoes proximas do alvo, valida resistencias, e apos 300 trades sugere parametros otimizados. Nenhum parametro e alterado automaticamente — apenas sugerido em relatorio.

## Motivacao
O TP Adaptativo V19.0 calcula TP1 baseado em ATR+resistencia, mas nao aprende com o resultado dos trades. Sem retroalimentacao, erros sistematicos (TP sempre muito longe, resistencia falsa, trailing muito curto) nunca sao corrigidos. V19.1 fecha esse loop usando dados reais de Paper Trading.

## Arquivos Afetados
### Criar
- `ENGINE/analytics/trade_analytics.py` — modulo central de registro e analise de saidas
- `ENGINE/analytics/__init__.py` — package init

### Modificar
- `ENGINE/risk/tp_adaptativo.py` — adicionar ResistanceScore, calibrar com dados historicos
- `ENGINE/risk/resistance_scanner.py` — adicionar ResistanceScore (toques, volume, TF, OB, Liquidity, BOS, CHoCH, FVG)
- `ENGINE/risk/risk_manager.py` — integrar resistance score >= 75 para reducao de TP
- `CORE/trading/paper_trading.py` — registrar MFE, MAE, max profit antes reversao, TP efficiency no fechamento
- `main.py` — corrigir passagem de OHLC vazio para TP calculation, integrar trade_analytics
- `CHANGELOG.md`
- `ARCHITECTURE.md`
- `BASELINE.md`
- `TEST_REPORT.md`
- `HOMOLOGATION_REPORT.md`

## Impacto Esperado
- TP Efficiency visivel (quanto % do TP proposto foi alcancado)
- Deteccao de TP_TOO_FAR (preco chegou >90% do TP e reverteu)
- Resistencia com score >= 75 reduz TP
- Apos 300 trades: relatorio com ATR ideal, trailing ideal, partial ideal, distancia ideal
- RR minimo institucional (2.0) sempre preservado
- Melhoria do Profit Factor sem aumentar Drawdown

## Riscos
- Trade Analytics consome CPU/IO moderado (JSON + eventos)
- Sugestoes de aprendizado podem ser ignoradas — nunca aplicadas automaticamente
- Fix do OHLC vazio (main.py linha 653) pode alterar TP calculado em relacao ao V19.0

## Plano de Implementacao

### Modulo 1 — Trade Analytics
Criar `ENGINE/analytics/trade_analytics.py`:
- `record_entry(symbol, direction, entry, sl, tp1, tp2, scores)` — salva dados do trade em JSON
- `record_exit(signal_id, exit_price, exit_reason, mfe, mae, max_profit_before_reversal, tp_efficiency)` — registra saida
- `get_trade(signal_id)` — consulta trade especifico
- `get_stats()` — estatisticas agregadas
- Banco: JSON em `ENGINE/analytics/trades/` (um arquivo por trade)

### Modulo 2 — TP Efficiency
Adicionar funcao em `trade_analytics.py`:
```python
def compute_tp_efficiency(max_reached: float, tp_proposed: float) -> float
```
Classificacao:
- 95-100: Excelente
- 85-95: Boa
- 70-85: Media
- <70: Ruim

### Modulo 3 — Rejeicao do TP
Em `trade_analytics.py`:
```python
def detect_tp_too_far(max_price, entry, tp1, direction) -> bool
```
Se preco chegou a >= 90% do TP e reverteu ate SL -> `TP_TOO_FAR = True`

### Modulo 4 — Resistance Validated Score
Adicionar em `resistance_scanner.py`:
```python
class ValidatedResistance:
    price: float
    score: float  # 0-100
    touch_count: int
    volume_confirmation: bool
    order_block: bool
    liquidity: bool
    bos: bool
    choch: bool
    fvg: bool
```
Score baseado em: toques, volume, timeframe, OB, Liquidity, BOS, CHoCH, FVG.
Somente reduzir TP quando `score >= 75`.

### Modulo 5 — Aprendizado
Em `trade_analytics.py`:
```python
def generate_learning_report(trades: List) -> LearningReport
```
Apos cada 300 trades, calcular:
- ATR ideal (ATR medio dos trades vencedores)
- Trailing ideal (distancia trailing media dos wins)
- Partial ideal (% partial que maximizou lucro)
- Distancia ideal do TP (MFE medio / ATR)
Gerar relatorio com antes/depois, expectativa, PF.

Nunca modificar automaticamente. Apenas sugerir.

### Modulo 6 — Dashboard
Adicionar metricas ao relatorio de estatisticas:
- TP Efficiency Media
- Partial TP % (quantos trades usaram partial)
- Trailing Wins (quantos wins com trailing ativo)
- TP Too Far (contagem)
- TP Ajustado (contagem)
- RR Medio
- Lucro medio TP1
- Lucro medio TP2

### Modulo 7 — Seguranca
Em `risk_manager.py`:
- `calculate_take_profits()`: nunca permitir RR < RR_MIN_RR (2.0)
- Se TP adaptativo gerar RR < 2.0, usar fixed TP baseado em RR_MIN_RR
- Validar na saida do `apply()` antes de retornar RiskResult

## Rollback
- Reverter `ENGINE/analytics/` (criar backup antes)
- Reverter `ENGINE/risk/tp_adaptativo.py` para versao V19.0
- Reverter `ENGINE/risk/resistance_scanner.py` para versao V19.0
- Reverter `CORE/trading/paper_trading.py` para versao V18.3 (sem V19)
- Reverter `main.py` passagem de OHLC

## Criterios de Aceitacao
- TP Efficiency registrada em 100% dos trades fechados
- TP_TOO_FAR detectado corretamente
- Resistance Score >= 75 reduz TP
- Relatorio de aprendizado gerado apos 300 trades
- RR nunca < 2.0
- Testes unitarios passando (minimo 20 novos)
- Testes de integracao passando
- Win Rate, PF, Drawdown, Expectativa preservados ou melhores
