# RFC V19.0 — EVOLUÇÃO FINAL PARA PRODUÇÃO

Data: 2026-07-12

## Objetivo

Auditoria completa e implementação de melhorias focadas em confiabilidade operacional,
coerência entre módulos e aumento da taxa de acerto, sem criar regressões.

O foco NÃO é gerar mais sinais. O foco é gerar sinais MELHORES.

## Motivação

Após análise aprofundada do pipeline do QuantOS, foram identificadas inconsistências
críticas que comprometem a qualidade dos sinais e a confiabilidade do sistema:

1. **Classificação fora da faixa** — `classify_signal()` usa composite score com thresholds
   0.88/0.78/0.68/0.58, mas QUALITY_TIERS usa min_score 92/82/72/62 em escala 0-100.
   Não há validação que impeça classificação incompatível com o score real.

2. **Expectativa simplista** — `compute_expectancy_level()` usa apenas overall_score + RR,
   ignorando 10 fatores institucionais.

3. **Penalizações genéricas** — `penalty_reasons` exibe apenas texto sem origem nem peso.

4. **Tendência sem regra clara** — Gate 12 existe mas não impede LONG contra Trending_Down
   ou SHORT contra Trending_Up sem confirmação estrutural.

5. **Qualidade do Setup sem recalibração** — Pesos permitem setups medianos receberem
   classificação alta.

6. **Papel Trading sem estatísticas avançadas** — Falta Win Rate por classificação,
   Sharpe, Payoff, acerto por ativo/timeframe.

7. **Autoaprendizado sem limites** — Não há proteção contra recalibração prematura.

## Arquivos Afetados

### Modificar
- `ENGINE/scanner/scanner_scoring.py` — Nova classificação, recalibragem de pesos
- `ENGINE/scanner/scanner_config.py` — Novos thresholds e pesos
- `ENGINE/scanner/quality_gate.py` — Alinhar stage2_ranking com classificação oficial
- `ENGINE/common/operational.py` — Nova expectativa, nova convicção, penalizações detalhadas
- `ENGINE/decision/decision_engine.py` — Gate de tendência mais rigoroso
- `ENGINE/consensus/consensus_engine.py` — Ajustes de thresholds
- `ENGINE/scanner/evidence_registry.py` — Registro de penalizações
- `ENGINE/scanner/scanner_engine.py` — Pontos de coleta de penalizações
- `CORE/trading/paper_trading.py` — Estatísticas avançadas, autoaprendizado
- `ENGINE/common/score_normalizer.py` — Nova função scale_0_100
- `ENGINE/analytics/trade_analytics.py` — Limites de autoaprendizado
- `ENGINE/learning/auto_calibration.py` — Aprendizado via Paper Trading
- `SERVICES/telegram/telegram_formatter.py` — Novo layout
- `ENGINE/scanner/scanner_types.py` — Novos campos para penalizações
- `main.py` — Integração dos novos cálculos

### Testes
- `TESTS/test_classification_v19.py`
- `TESTS/test_expectancy_v19.py`
- `TESTS/test_penalties_v19.py`
- `TESTS/test_trend_gate_v19.py`
- `TESTS/test_paper_stats_v19.py`
- `TESTS/test_auto_learning_v19.py`

## Plano de Implementação

### Fase 3 — Classificação (Tabela Fixa)
**Arquivos**: `scanner_scoring.py`, `scanner_config.py`, `scanner_types.py`

Criar tabela de classificação com ranges fixos e exclusivos:
- DIAMANTE: 90-100 (índice >= 90)
- OURO: 80-89 (índice >= 80)
- PRATA: 70-79 (índice >= 70)
- BRONZE: 60-69 (índice >= 60)
- REPROVADO: < 60

A classificação usa o Índice Geral (0-100), não o composite score.
Validação: após definir classificação, verificar se o score REALMENTE está na faixa.
Se estiver fora, rejeitar o sinal.

### Fase 4 — Expectativa
**Arquivos**: `operational.py`

Reescrever `compute_expectancy_level()` para considerar:
- Qualidade (weight 0.15)
- Confiança (weight 0.13)
- Consenso (weight 0.12)
- Estrutura (weight 0.10)
- Liquidez (weight 0.10)
- Momentum (weight 0.10)
- Risco invertido (weight 0.08)
- Tendência alinhada (weight 0.08)
- Kalman alinhado (weight 0.07)
- ATR normalizado (weight 0.04)
- Volatilidade normalizada (weight 0.03)

Resultado:
- Muito Alta: >= 0.80
- Alta: >= 0.65
- Média: >= 0.45
- Baixa: < 0.45

### Fase 5 — Penalizações
**Arquivos**: `operational.py`, `scanner_types.py`

Criar dataclass `Penalty` com:
- `reason: str` — descrição
- `weight: float` — peso da penalização (0.0 a 1.0)
- `source: str` — módulo de origem

Penalizações possíveis com pesos:
- ATR elevado (>3%): weight 0.20
- Estrutura fraca (<0.4): weight 0.25
- Liquidez insuficiente (<0.5): weight 0.20
- RVOL baixo (<1.0): weight 0.15
- Contra tendência: weight 0.30
- Kalman contrário: weight 0.25
- Próximo de resistência (<2%): weight 0.15
- Próximo de suporte (<2%): weight 0.15
- Mercado lateral: weight 0.20
- Spread elevado (>0.0005): weight 0.10
- Baixo consenso (<0.6): weight 0.20

Função `compute_penalties(signal_data) → List[Penalty]` que retorna
penalizações aplicáveis com seus pesos.

### Fase 6 — Retorno Operacional
**Arquivos**: `operational.py`

Expandir `OperationalCalculator.calculate()` para retornar:
- `preco_entrada`: entry_price
- `preco_tp`: take_profit_1
- `preco_stop`: stop_loss
- `retorno_ativo_pct`: retorno do ativo em %
- `retorno_margem_pct`: retorno sobre margem
- `retorno_patrimonio_pct`: retorno sobre patrimônio
- `lucro_liquido_usdt`: lucro líquido TP1
- `perda_maxima_usdt`: perda máxima stop
- `valor_nominal`: valor nominal (quantidade * entry_price)
- `margem_utilizada_usdt`: margem usada
- `quantidade`: quantidade total
- `alavancagem_efetiva`: alavancagem efetiva

### Fase 7 — Tendência
**Arquivos**: `decision_engine.py`

Adicionar regras explícitas no DecisionEngine:

- LONG contra Trending_Down + Kalman DOWN → REJEITAR
- SHORT contra Trending_Up + Kalman UP → REJEITAR

Exceção permitida APENAS quando houver confirmação real de reversão:
- CHOCH confirmado no timeframe atual + BOS + volume acima da média + consenso >= 0.70

### Fase 8 — Qualidade do Setup
**Arquivos**: `scanner_scoring.py`, `scanner_config.py`

Recalibrar SCORE_WEIGHTS para evitar que setups medianos recebam classificação alta:
- Reduzir peso de flow_score (0.12 → 0.08)
- Aumentar peso de structural_score (0.10 → 0.14)
- Aumentar peso de confidence_score (0.08 → 0.12)
- Adicionar verificação de consistência entre scores

### Fase 9 — Thresholds Bronze/Prata/Ouro/Diamante
**Arquivos**: `scanner_scoring.py`, `scanner_config.py`

Qualidade mínima para cada tier:
- BRONZE: quality >= 0.60, RR >= 2.0, consenso >= 0.55, confiança >= 0.60
- PRATA: quality >= 0.70, RR >= 2.5, consenso >= 0.65, confiança >= 0.70
- OURO: quality >= 0.80, RR >= 3.0, consenso >= 0.75, confiança >= 0.80
- DIAMANTE: quality >= 0.90, RR >= 3.5, consenso >= 0.85, confiança >= 0.90

### Fase 10 — Índice Geral
**Arquivos**: `operational.py`

Refatorar `compute_overall_score()` para usar pesos transparentes:
- Quality: 0.20
- Confidence: 0.15
- Consensus: 0.12
- Structure: 0.10
- Liquidity: 0.10
- Momentum: 0.10
- Trend Alignment: 0.08
- Kalman Alignment: 0.08
- Risk (invertido): 0.07

Garantir que o índice nunca ultrapasse 100 nem seja distorcido.

### Fase 11 — Estatísticas Paper Trading
**Arquivos**: `paper_trading.py`

Adicionar ao `get_stats()`:
- `win_rate`: já existe
- `profit_factor`: já existe
- `expectancy`: já existe
- `drawdown_maximo`: já existe
- `payoff`: avg_win / avg_loss
- `sharpe_ratio`: (avg_return - rf_rate) / std_returns
- `win_rate_by_classification`: dict{classification: wr}
- `win_rate_by_symbol`: dict{symbol: wr}
- `win_rate_by_timeframe`: dict{tf: wr}
- `win_rate_long`: wr for LONG
- `win_rate_short`: wr for SHORT
- `avg_time_to_tp_hours`: tempo médio até TP
- `avg_time_to_stop_hours`: tempo médio até Stop
- `top_loss_reasons`: contagem de motivos de perda
- `top_win_reasons`: contagem de motivos de ganho

### Fase 12 — Autoaprendizado
**Arquivos**: `auto_calibration.py`, `trade_analytics.py`

Implementar:
- `MIN_SAMPLES_FOR_LEARNING = 50` — mínimo de trades fechados para recalibrar
- `MIN_SAMPLES_PER_CLASSIFICATION = 20` — mínimo por classificação
- `LEARNING_SOURCES = ["paper_trading"]` — apenas Paper Trading
- `generate_learning_report()` — relatório com sugestões baseadas em dados reais

### Fase 13 — Telegram
**Arquivos**: `telegram_formatter.py`

Novo layout do cartão:
1. HEADER: símbolo, direção, timeframe
2. CLASSIFICAÇÃO E QUALIDADE: Índice Geral com barra, classificação (diamante/ouro/prata/bronze), qualidade
3. CONVICÇÃO E EXPECTATIVA: convicção, expectativa, penalizações (se houver)
4. PREÇOS: entrada, TP, Stop, RR
5. OPERACIONAL: retorno do ativo, lucro líquido, perda máxima, alavancagem
6. ANÁLISE: tendência, Kalman, ADX, RVOL, ATR, fluxo, estrutura, liquidez
7. AUDITORIA: signal ID, versão, ciclo, timestamp

## Riscos

1. **Falso aumento de rejeições** — Gates mais rigorosos podem rejeitar sinais bons.
   Mitigação: monitorar funnel e comparar com baseline antes/depois.

2. **Classificação mais restritiva** — BRONZE agora exige RR >= 2.0 + consenso + confiança.
   Mitigação: verificar se os thresholds não estão cortando sinais viáveis.

3. **Penalizações podem duplicar gates** — Algumas penalizações repetem verificações
   já feitas pelo DecisionEngine. Mitigação: penalizações são informativas, não
   eliminatórias.

4. **Autoaprendizado prematuro** — Limite de 50 trades pode ser atingido rápido.
   Mitigação: usar 100 trades como mínimo conservador.

## Plano de Rollback

Cada alteração tem seu próprio ponto de rollback via git revert. Em caso de
regressão crítica, reverter completamente e restaurar BASELINE.md anterior.

## Critérios de Aceitação

1. classificação BRONZE exige RR>=2.0, consenso>=0.55, confiança>=0.60
2. expectativa "Muito Alta" exige score >= 0.80
3. penalizações mostram origem e peso
4. retorno operacional inclui todos os 12 campos
5. LONG contra Trending_Down+Kalman DOWN é rejeitado
6. SHORT contra Trending_Up+Kalman UP é rejeitado
7. índice geral máxima 100, mínima 0
8. paper_trading.get_stats() retorna 20+ métricas
9. autoaprendizado só roda após 100 trades fechados
10. telegram mostra classificação, qualidade, convicção, RR, expectativa, penalizações
