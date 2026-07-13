# RFC — Recalibração dos Sinais do QuantOS (Modo Institucional)

Data: 2026-07-11
Status: **AGUARDANDO APROVAÇÃO — nenhum código foi alterado por esta RFC**

## Objetivo

Eliminar duplicidade de sinais, recalibrar a relação entre Qualidade/Confiança/Consensus, bloquear sinais em mercado lateral sem rompimento confirmado, e exigir alinhamento entre os motores de tendência antes de aprovar um sinal — elevando o padrão de aprovação de "atingiu o mínimo" para "tem vantagem estatística consistente".

## Motivação

Six problemas foram apontados e verificados no código nesta auditoria:

| # | Problema apontado | Verificado? | Evidência |
|---|---|---|---|
| 1 | Mesmo ativo/timeframe gera múltiplos sinais no mesmo ciclo | **Confirmado no código** | `ScannerEngine.scan()` (`ENGINE/scanner/scanner_engine.py`) itera `for tf in self._timeframes` e chama `build_signal()` uma vez por timeframe (linha 240), anexando cada um a `all_signals` (linha 286). `main.py._process_scan_result()` avalia e **envia imediatamente** cada `sig` do loop `for sig in report.signals` que passar no `DecisionEngine` — não existe nenhum passo que escolha "o melhor" antes de enviar. Se 2+ timeframes do mesmo par passarem os 8 gates com precos diferentes, o `SignalTracker.pode_reenviar()` gera `dedup_id` diferentes (chave inclui entry/stop) e **ambos são enviados ao Telegram como sinais separados**. |
| 2 | Qualidade aprovada entre 48–50 | **Parcialmente investigado** | A fórmula (`ENGINE/scanner/scanner_scoring.py:compute_quality_score`) É recalculada corretamente após `flow_score`/`timing_index`/`conviction_score` serem preenchidos (não é bug de zeragem, como cheguei a suspeitar e descartei ao ler o código completo). O gate atual (`QUALITY_GATE_MIN_SCORE = 0.45`, produção) permite qualquer coisa acima de 45/100 — a média observada (~48-50) é consistente com um piso deliberadamente baixo, não com um bug de cálculo. **Não encontrei evidência de erro na fórmula em si**; o problema real é o threshold estar calibrado muito abaixo do padrão institucional que você quer (70+). |
| 3 | Confiança (~75) incompatível com Qualidade (~50) | **Confirmado como lacuna arquitetural** | `confidence_score` (`score_confidence()`) e `quality_score` são formulas **independentes** — a primeira mede coerência de padrões/estrutura, a segunda é uma média ponderada de 11 fatores (onde `confidence_score` entra com peso de apenas 8%). Não existe, em nenhum lugar do pipeline, uma checagem cruzada tipo "se Confiança - Qualidade > X, rejeitar ou recalcular". Isso não é um bug de cálculo, é a **ausência de uma regra de consistência** que você quer adicionar. |
| 4 | Sinais em mercado lateral | **Parcialmente ja existe** | `ScannerEngine.scan()` já verifica `if confluence.lateral_market_score > 0.8: skip` (linha 118) — mas (a) o threshold 0.8 é frouxo, (b) essa checagem existe só no Scanner, não é reforçada como hard gate no `DecisionEngine`, e (c) não há exceção estruturada por "rompimento confirmado + volume + consenso alto" como você pediu — hoje é um corte binário simples. |
| 5 | Kalman e Trend Engine com estados diferentes, sem rejeição | **Confirmado — checagem inexistente** | `grep` por "kalman" em `ENGINE/decision/decision_engine.py` e `ENGINE/consensus/consensus_engine.py`: **zero ocorrências**. Kalman (`kalman_direction`, `kalman_trend_state` etc.) só é usado como *insumo* dentro de `conviction_score`/`timing_index` (uma média ponderada), nunca como *gate* de rejeição por conflito com o Trend Engine (`ENGINE/market/market_trend.py`) ou com o `MarketRegime`. |
| 6 | Aprovação só por threshold mínimo, sem "vantagem estatística" | **Confirmado por design** | Os 8 gates do `DecisionEngine` (`ENGINE/decision/decision_engine.py`) são todos comparações `>=`/`<` contra constantes fixas (RVOL, ADX, estrutura, entry zone, quality, consensus, RR). Não há nenhuma medida de vantagem estatística (ex: win rate histórico do setup, distribuição de resultados por classificação) usada como gate — isso exigiria dados de paper trading acumulados, que hoje existem (`CORE.trading.paper_trading`) mas não alimentam o `DecisionEngine`. |

## Escopo da Mudança

### O QUE MUDA

1. **Deduplicação por ciclo (symbol + timeframe)** — `main.py._process_scan_result()`
   - Antes de enviar, agrupar `all_decisions` aprovados por `symbol` (não por timeframe individual).
   - Se houver mais de um timeframe aprovado para o mesmo símbolo no ciclo, calcular um score final (proposta: `quality * 0.5 + consensus * 0.3 + rr_normalizado * 0.2`) e manter apenas o de maior score.
   - Registrar em log qual timeframe venceu e quais foram descartados (`log.info("Dedup ciclo: %s venceu com %s sobre %s", ...)`).
   - Arquivo afetado: `main.py`.

2. **Novos hard gates institucionais** — `ENGINE/decision/decision_engine.py` + `ENGINE/scanner/scanner_config.py`
   - `QUALITY_GATE_MIN_SCORE`: 0.45 → **0.70**
   - Novo `CONFIDENCE_GATE_MIN_SCORE = 0.75` (hoje não existe gate de confidence no DecisionEngine)
   - `CONSENSUS_MINIMUM_SCORE`: 0.50 → **0.70**
   - `ENTRY_ZONE_SCORE_MIN`: 0.40 → **0.70**
   - `RR_MIN_RR`: já é 2.0 — mantido.
   - Novo gate: `abs(confidence_score - quality_score) <= 0.10` (equivalente aos 10 pontos pedidos, na escala 0-1) — se violado, rejeitar com motivo `"Descalibração: Confiança/Qualidade fora de faixa"`.
   - Novo gate: rejeitar se `MarketRegime` for lateral/ranging **e** não houver rompimento confirmado (BOS/CHoCH) + volume acima da média + consenso multi-TF ≥ 0.70 simultaneamente.
   - Novo gate: rejeitar se `kalman_direction` divergir da direção do `Trend Engine`/`MarketRegime` (ex: kalman="down" e trend="uptrend").

3. **Reforço do lateral market gate** — `ENGINE/confluence/confluence_engine.py` + `ENGINE/decision/decision_engine.py`
   - Mover a decisão de "lateral" do Scanner (soft skip, threshold 0.8) para um hard gate explícito no `DecisionEngine`, com a exceção estruturada (rompimento + volume + consenso) em vez do corte binário atual.

### O QUE NÃO MUDA
   - Fórmulas de `quality_score`, `confidence_score`, `consensus_score` — não há evidência de bug nelas; o pedido de "recalibrar a fórmula" seria redesenhar pesos sem dados de backtest para validar — **recomendo não fazer isso às cegas**. Ver seção Riscos.
   - Estrutura de detecção de padrões (BOS/CHoCH/OB/FVG), Kalman, cálculo de ATR/ADX/RSI/RVOL — nenhum bug encontrado nesses módulos nesta auditoria.

## Impacto Esperado

- **Volume de sinais deve cair drasticamente.** Com os thresholds atuais (quality 0.45, consensus 0.50), a média observada já fica perto do piso (48-50/100 na escala do dashboard). Subir quality para 0.70 e consensus para 0.70 pode reduzir os sinais aprovados a **zero ou quase zero** até que as condições de mercado realmente produzam setups fortes — isso é o comportamento pedido ("priorizar qualidade sobre quantidade"), mas precisa ser validado nos 500 ativos antes de ir para produção, exatamente como você pediu nos "Testes Obrigatórios".
- Eliminação de duplicidade: 1 sinal por símbolo por ciclo, no máximo.
- Eliminação de sinais em lateralização sem rompimento.

## Riscos

1. **Risco alto de zerar sinais completamente.** Não tenho dados de backtest mostrando que setups reais atingem quality>=0.70 E confidence>=0.75 E consensus>=0.70 simultaneamente. Se a distribuição real de scores nunca combina essas três condições, o resultado prático é nenhum sinal, indefinidamente — preciso rodar o teste de 500 ativos (que você já pediu) **antes** de considerar isso liberado, não depois.
2. **Novo gate confidence-vs-quality pode rejeitar setups legítimos.** As duas métricas medem coisas diferentes por design; forçar `|conf - qual| <= 0.10` pode ser tecnicamente correto para "coerência" mas nunca ter sido validado como um preditor real de qualidade de trade.
3. **Gate de conflito Kalman x Trend Engine pode ser bloqueante demais** se os dois motores frequentemente divergem em mercados normais (não teria como saber sem medir a taxa de divergência atual primeiro).
4. Reduzir volume de sinais para perto de zero é **reversível** (basta reverter os thresholds), mas o tempo de paper trading necessário para validar a nova calibração (ganhar confiança de que setups aprovados são realmente melhores) não é curto.

## Plano de Implementação (após aprovação)

1. Fase de medição (antes de qualquer gate novo): instrumentar e rodar 1 ciclo real com 500 ativos, registrando a distribuição real de `quality_score`, `confidence_score`, `consensus_score`, `lateral_market_score` e taxa de divergência Kalman x Trend Engine — para saber se os thresholds propostos (0.70/0.75/0.70) são atingíveis pela distribuição real, ou se precisam de ajuste antes de travar em produção.
2. Implementar dedup por (symbol) no ciclo em `main.py`.
3. Implementar os novos gates em `decision_engine.py` com os thresholds medidos na fase 1 (ajustados se necessário, com justificativa registrada).
4. Testes unitários para cada gate novo (isolado) + teste de integração do pipeline completo.
5. Rodar novamente os 500 ativos, comparar taxa de aprovação e qualidade média antes/depois.
6. Paper trading por período a definir com você antes de liberar em modo LIVE.

## Rollback

- Reverter `QUALITY_GATE_MIN_SCORE`, `CONFIDENCE_GATE_MIN_SCORE`, `CONSENSUS_MINIMUM_SCORE`, `ENTRY_ZONE_SCORE_MIN` para os valores atuais (0.45/-/0.50/0.40).
- Remover os 3 gates novos (confidence-vs-quality, lateral-market-hard-gate, kalman-vs-trend) do `decision_engine.py`.
- Reverter a dedução por symbol em `main.py` para o comportamento atual (por timeframe).

## Critérios de Aceitação

- [ ] Teste com 500 ativos reais: duplicidade = 0 (nenhum símbolo com mais de 1 sinal enviado no mesmo ciclo).
- [ ] Nenhum sinal aprovado com `|confidence_score - quality_score| > 0.10`.
- [ ] Nenhum sinal aprovado em mercado lateral sem rompimento + volume + consenso confirmados.
- [ ] Nenhum sinal aprovado com Kalman e Trend Engine em conflito de direção.
- [ ] Qualidade média dos sinais aprovados > 0.75 (equivalente a 75/100).
- [ ] Pelo menos 1 sinal aprovado nos 500 ativos testados (senão os thresholds precisam de recalibração antes de prosseguir — ver Riscos #1).
- [ ] Nenhum teste unitário/integração existente quebrado.

---

**Aguardando sua decisão**: aprovar esta RFC como está, ajustar algum threshold/gate antes de aprovar, ou pedir a "fase de medição" (item 1 do plano) primeiro, isoladamente, antes de decidir os valores finais dos gates?
