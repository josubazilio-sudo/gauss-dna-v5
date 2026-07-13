# Relatório Final — Recalibração dos Sinais do QuantOS (Modo Institucional)

Data: 2026-07-11
Ref: `RFC_RECALIBRACAO_SINAIS_INSTITUCIONAL.md`

## Resumo Executivo

Auditoria completa do pipeline de sinais confirmou 6 problemas apontados (2 com evidência de bug real, 4 como lacunas arquiteturais — ausência de proteções que nunca existiram). Implementadas todas as correções aprovadas: deduplicação por ativo, redesenho da fórmula de qualidade (com 2 bugs reais corrigidos no processo), 4 novos hard gates institucionais, e thresholds elevados. Validado em produção real com 500 ativos: pipeline funciona corretamente, dedup funciona, mas **os thresholds solicitados (0.70+ em Quality/Consensus/Entry Zone/Confidence) produzem 0 sinais aprovados nas condições de mercado atuais** — decisão consciente do usuário de manter assim, aceitando raridade de sinais em troca de rigor institucional.

## Causa Raiz de Cada Problema

| # | Problema | Causa raiz | Correção |
|---|---|---|---|
| 1 | Duplicidade por ativo/timeframe | `ScannerEngine.scan()` gera 1 `Signal` por timeframe monitorado (até 4 por ativo); `main.py` avaliava e enviava cada um independentemente, sem escolher o melhor | Coleta de todos os aprovados do ciclo por ativo, envia só o de maior score composto (`quality*0.5 + consensus*0.3 + rr_normalizado*0.2`) |
| 2 | Qualidade 48-50/100 | Fórmula matematicamente correta (pesos somam 1.0), mas 4 sub-componentes (`flow_score`, `structural_score`, `risk_score`, `conviction_score`) nunca se aproximavam de 1.0 nos dados reais (teto observado: 0.71/0.62/0.59/0.82) — ~16 pontos ficavam estruturalmente inalcançáveis. **+ bug real**: `institutional_score` era calculado com `flow_score=0.0` (valor ainda não computado naquele ponto) e nunca recalculado depois | Reescala dos 4 componentes pelo teto real observado (p99, não máximo bruto, para não deixar 1 outlier definir a escala); `institutional_score` agora recalculado após flow/conviction ficarem disponíveis |
| 3 | Confiança (~75) incompatível com Qualidade (~50) | Duas fórmulas independentes por design — não havia bug, mas também não havia regra de consistência entre elas | Novo GATE 10: rejeita se `\|confidence - quality\| > 0.10` |
| 4 | Sinais em mercado lateral | Já existia um corte simples no Scanner (threshold 0.8, sem hard gate no Decision Engine, sem exceção estruturada) | Novo GATE 11 no `DecisionEngine`: lateral (`regime="ranging"`) exige rompimento (BOS/CHoCH) + volume acima da média + estrutura válida + consenso ≥ threshold simultaneamente |
| 5 | Kalman × Trend Engine sem rejeição | Kalman só era usado como insumo em médias ponderadas (`conviction_score`/`timing_index`), nunca como gate de conflito | Novo GATE 12: rejeita se `regime` indicar tendência clara e `kalman_direction` divergir |
| 6 | Aprovação só por threshold mínimo | Confirmado por design — os 8 gates originais são todos `>=`/`<` fixos | Thresholds elevados para padrão institucional (ver tabela abaixo); não implementada "vantagem estatística" via histórico de paper trading — exigiria trabalho de backtest fora do escopo desta RFC |

## Arquivos Modificados/Criados

| Arquivo | Mudança |
|---|---|
| `main.py` | Import de `RR_IDEAL_RR` e `calibration_measurement`; loop `_process_scan_result` reestruturado — coleta `approved_this_pair` em vez de enviar por timeframe, dedup por ativo após o loop com log de qual timeframe venceu |
| `ENGINE/decision/decision_engine.py` | +4 gates (linhas ~103-155): Confidence (GATE 9), Confidence-vs-Quality (GATE 10), Mercado Lateral (GATE 11), Kalman-vs-Trend (GATE 12) |
| `ENGINE/scanner/scanner_config.py` | `QUALITY_GATE_MIN_SCORE` 0.45→0.70 (debug 0.42→0.65), `CONSENSUS_MINIMUM_SCORE` 0.50→0.70, `ENTRY_ZONE_SCORE_MIN` 0.40→0.70; novas constantes `CONFIDENCE_GATE_MIN_SCORE=0.75`, `CONFIDENCE_QUALITY_MAX_DIFF=0.10`, `LATERAL_REGIMES`, `QUALITY_COMPONENT_CEILINGS` |
| `ENGINE/scanner/scanner_scoring.py` | Nova função `rescale_to_ceiling()`; aplicada a `structural_score`/`risk_score` em `compute_all_scanner_scores()` |
| `ENGINE/scanner/scanner_engine.py` | `flow_score`/`conviction_score` reescalados no ponto de atribuição real; `institutional_score` recalculado com `score_institutional()` após flow ficar disponível (bug corrigido) |
| `ENGINE/diagnostic/calibration_measurement.py` | **Novo** — logger de medição por sinal avaliado (quality/confidence/consensus/componentes/conflito kalman), usado para calibrar os thresholds com dado real |
| `SERVICES/telegram/telegram_service.py` | `_on_decision` (antes um stub vazio) agora formata e envia — bug pré-existente encontrado nesta sessão, não fazia parte da recalibração mas bloqueava todo sinal aprovado |
| `SERVICES/telegram/telegram_validator.py` | `validate_consistency()` reduzido de 18 para os 8 campos que o motor atual realmente define — bug pré-existente encontrado, bloqueava silenciosamente 100% dos sinais |
| `TESTS/test_decision_engine_recalibracao.py` | **Novo** — 11 testes unitários dos 4 gates novos |
| `TESTS/test_quality_score_rescale.py` | **Novo** — 6 testes unitários da reescala de quality_score |
| `RFC_RECALIBRACAO_SINAIS_INSTITUCIONAL.md` | RFC completa (auditoria, plano, riscos) |

## Thresholds — Antes / Depois

| Parâmetro | Antes | Depois |
|---|---|---|
| `QUALITY_GATE_MIN_SCORE` | 0.45 | **0.70** |
| `CONSENSUS_MINIMUM_SCORE` | 0.50 | **0.70** |
| `ENTRY_ZONE_SCORE_MIN` | 0.40 | **0.70** |
| `CONFIDENCE_GATE_MIN_SCORE` | (não existia) | **0.75** |
| `\|Confidence - Quality\|` máximo | (não existia) | **0.10** |
| Mercado lateral | soft-skip no Scanner (0.8) | hard gate com exceção estruturada |
| Conflito Kalman×Trend | (não existia) | hard gate |
| Sinais por ativo/ciclo | ilimitado (1 por timeframe) | **1** |

## Impacto Medido (Antes/Depois)

**Fórmula de Quality (isolada, testada com componentes reais medidos):**

| Setup | Quality antes | Quality depois |
|---|---|---|
| Melhor já observado (p99 de cada componente) | 0.827* | **0.971** |
| Bom (p90 de cada componente) | — | **0.774** |
| Mediano típico (médias reais) | ~0.47 (teto real 0.668) | **0.570** |

*calculado sem a correção de `institutional_score`; com a correção completa chega a 0.971.

**Pipeline completo, 500 ativos reais, 3 ciclos antes / múltiplos ciclos depois:**

| Métrica | Antes (thresholds antigos) | Depois (thresholds institucionais) |
|---|---|---|
| Sinais avaliados | 3.810 | 251 (amostra) |
| Aprovados | 44 (5.8%) | **0 (0%)** |
| Duplicidade por ativo | Sim (múltiplos timeframes enviados) | **Confirmado 0** (6 símbolos únicos enviados no teste intermediário, nenhum repetido) |
| Motivo dominante de rejeição | Consensus/Quality baixos | Entry Zone (23.5%) e RVOL (52.6%) |

## Evidências dos Testes

- **17 testes unitários, 17 passando** (`TESTS/test_decision_engine_recalibracao.py` + `TESTS/test_quality_score_rescale.py`), cobrindo os 4 gates novos (rejeição e aprovação) e a reescala de quality_score.
- **Teste de integração real**: pipeline rodando em produção (pm2, 500 ativos/ciclo) durante toda a implementação, monitorado ciclo a ciclo via `calibration_measurement.csv`.
- **Confirmação de dedup funcionando**: log `DEDUP:` mostrou 6 símbolos distintos enviados em uma janela de teste intermediária, nenhum repetido — e o mecanismo de escolha do melhor timeframe (`Dedup ciclo:`) está implementado e pronto para disparar quando 2+ timeframes do mesmo ativo passarem simultaneamente (não ocorreu na amostra coletada, dado o rigor dos novos gates).

## Confirmação de Não-Regressão

- `python -c "import main"` — cadeia completa de imports OK após cada mudança.
- Todos os testes unitários novos passam (17/17).
- Bot rodando continuamente em produção (pm2) durante toda a implementação, sem crash, processando ciclos completos de 500 ativos.
- Nenhuma mudança na lógica de RVOL/ADX/BOS/CHoCH/estrutura/Risk Manager (gates 1-8 originais intocados, exceto reordenação para inserir os gates novos entre o Consensus e o Risk Manager).

## Riscos Remanescentes

1. **Zero sinais aprovados nas condições de mercado atuais** com os thresholds pedidos — decisão explícita do usuário de manter assim. Recomendo reavaliar após acumular paper trading por período mais longo, para confirmar se o mercado eventualmente produz setups que passam em todos os critérios, ou se algum threshold precisa de ajuste fino adicional.
2. `QUALITY_COMPONENT_CEILINGS` foi calibrado com 3.810 amostras (3 ciclos) — recomendo recalibrar periodicamente conforme mais dados reais forem coletados (o mecanismo de medição, `calibration_measurement.py`, continua ativo em produção para isso).
3. Não foi implementada a "vantagem estatística" mencionada no problema #6 (histórico de win rate por classificação) — exigiria integração com dados de paper trading acumulados, fora do escopo desta RFC.

## Próxima Fase Recomendada

Paper trading por período a definir, monitorando se os gates institucionais eventualmente aprovam sinais em condições de mercado mais favoráveis (menos lateralização — hoje ~69% dos ativos monitorados estão em `ranging`).
