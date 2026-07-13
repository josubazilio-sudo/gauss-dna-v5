# Relatório Final — RFC V18.4: Consolidação da Camada de Apresentação

Data: 2026-07-11/12
Ref: RFC V18.4 (mensagem do usuário)
Status: **Implementado e validado em produção real (local + pronto para VPS)**

## Resumo Executivo

Confirmada a causa raiz única por trás de quase todas as inconsistências reportadas: o QuantOS tinha **3 sistemas de score/classificação/dimensionamento independentes**, calculados com fórmulas diferentes sobre dados sobrepostos, sem nunca se validarem entre si. A Baseline institucional (Decision Engine, Hard Gates, Quality Gate, Consensus, Risk Engine institucional) **não foi alterada** — todas as correções ficaram na camada de agregação/apresentação, exatamente como restringido.

## Antes × Depois

| Sintoma reportado | Antes | Depois |
|---|---|---|
| Retorno +41%/+111%/+167% em TPs pequenos | `retorno_pct = leverage(fictício) × variação%`, exibido sem qualificação | 4 métricas separadas e rotuladas: retorno da operação (sem alavancagem), lucro líquido USDT, retorno sobre margem, retorno sobre patrimônio — todas calculadas com a quantidade real |
| Dashboard mostra ativo diferente do enviado ao Telegram | 2 seleções de "melhor sinal" independentes (`quality×0.5+consensus×0.3+RR×0.2` só entre aprovados vs `max quality` entre todos) | 1 única seleção (`CycleSignalResult.best_signal`), calculada uma vez, usada por envio e diagnóstico |
| Posição exibida no Telegram não bate com execução real | `OperationalCalculator` inventava 30% do capital × alavancagem (tabela fictícia, nunca usada na execução real) | Quantidade vem de `BOTS/mexc/trading/risk_manager.py::calculate_position_size()` — a mesma função e o mesmo saldo (`self._bot._balance.total`) que a execução real usaria |
| "Score 96 / Classificação Bronze" | 2 sistemas de tier independentes: `classify_signal()` (Baseline) vs `compute_overall_score()`'s própria tabela DIAMOND/PLATINUM/GOLD/SILVER/BRONZE | `overall_tier` agora deriva sempre de `classification_label` (Baseline) — nunca mais diverge, comprovado por teste (`test_overall_score_tier_matches_classification_label_bronze_even_with_high_numeric_score`) |

## Arquivos Modificados (todos dentro dos 3 autorizados)

| Arquivo | Mudança |
|---|---|
| `main.py` | + `CycleSignalResult` (dataclass) e `_cycle_rank()` (função module-level, único critério oficial). Removida a duplicação de "melhor sinal" — o bloco de diagnóstico (linha ~715, antes `max(all_decisions, key=lambda sd: sd.quality)`) agora usa `cycle_result.best_signal`. Adicionado cálculo de `quantity`/`balance` reais via `self._bot.risk_manager.calculate_position_size()` e `self._bot._balance.total`, passados no `data` dict para o formatter. |
| `ENGINE/common/operational.py` | `OperationalCalculator.calculate()`: assinatura trocada de `(quality_score, entry, stop, tp1)` para `(entry, stop, tp1, quantity, balance)` — não estima mais posição/alavancagem, só deriva métricas dos valores reais recebidos. `compute_overall_score()`: removida a tabela `OVERALL_TIERS` independente; `overall_tier` agora deriva de `classification_label` (Baseline). Removidos `calculate_leverage()`, `LEVERAGE_TABLE`, `ACCOUNT_SIZE`, `LEVERAGE_MAX_USER` (não usados em nenhum outro lugar). |
| `SERVICES/telegram/telegram_formatter.py` | Bloco "Operacional" reescrito: mostra posição real (quantidade + valor), e os 4 indicadores separados (retorno da operação, lucro líquido, retorno sobre margem, retorno sobre patrimônio), cada um com rótulo explícito. Removidas as linhas de "Capital p/ Trade" e "Alavancagem" (conceitos fictícios). |

Nenhum outro arquivo foi tocado. Nenhuma linha de `ENGINE/decision/`, `ENGINE/consensus/`, `ENGINE/scanner/` (exceto o que já estava na RFC anterior), `BOTS/mexc/trading/risk_manager.py` ou `ENGINE/risk/risk_manager.py` foi alterada.

## Evidências dos Testes

- **26 testes unitários, 26 passando** (9 novos nesta RFC + 17 das RFCs anteriores desta sessão, sem regressão).
- Teste específico reproduzindo o bug relatado (`test_overall_score_tier_matches_classification_label_bronze_even_with_high_numeric_score`): confirma que um índice numérico de 96+ com `classification_label="bronze"` agora mostra `overall_tier="BRONZE"`, nunca mais "DIAMOND".
- **Validação em produção real** (pm2 local, ciclo real com MEXC): sinal `BTSUSDT 30m short` aprovado (`SIG-20260712-1863`) — confirmado por log que o **mesmo trace_id** aparece tanto no envio (`DEDUP: BTSUSDT_30M_SHORT...`) quanto no registro de diagnóstico (`DIAG-SD[BTSUSDT] SIG-20260712-1863 | status=APPROVED`), eliminando a divergência. Envio ao Telegram confirmado com `200 OK`.

## Confirmação de Não-Regressão

- `python -c "import main"` — cadeia completa de imports OK.
- Bot rodando continuamente em produção (pm2) durante toda a implementação, sem crash, ciclos completos com 300 ativos.
- Nenhuma mudança em Decision Engine, Consensus, Smart Money, Kalman, Scanner, Quality Gate, Hard Gates, Thresholds, Score institucional, Risk Engine institucional ou pipeline de execução.

## Riscos Remanescentes

1. `self._bot._balance.total` em modo `DEVELOPMENT`/paper trading é um valor fixo (10.000 USDT), não a evolução real do capital rastreada por `CORE.trading.paper_trading.PaperTradingEngine` (que tem seu próprio saldo, hoje ~9.879 USDT) — são dois trackers de saldo diferentes para paper trading. Isso é uma questão pré-existente, fora do escopo desta RFC (não é um dos 3 arquivos autorizados) — reportando para uma futura RFC se desejar unificar.
2. Etapas 3, 6 e 7 da auditoria original (padronização de métricas de ciclo, paper trading) não tinham achados críticos e não foram alteradas.

## Próxima Fase Recomendada

Propagar para o VPS via `deploy_vps.sh` e continuar monitorando por alguns ciclos reais para confirmar consistência sustentada.
