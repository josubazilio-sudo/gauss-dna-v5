# Relatório — RFC V19.3: Prioridade Dinâmica do Scanner

Data: 2026-07-12
Status: **Implementação e testes concluídos. Validação por Paper Trading
real em andamento (Diretriz Permanente) — RFC ainda NÃO liberada para
conclusão final.**

## Resumo Executivo

Implementado `PRIORITY_SCORE` para reordenar a fila de varredura do
scanner por probabilidade de movimento, sem alterar Score Institucional,
Confidence, Quality, Hard Gates, Decision Engine ou gestão de risco.
Divergências do prompt original documentadas explicitamente (spread/
liquidez não instrumentados; reescaneamento dos top 20 implementado como
feature opcional desligada por padrão).

## Arquivos Modificados/Criados

- `ENGINE/scanner/priority_score.py` (novo).
- `ENGINE/scanner/scanner_config.py` — `SCANNER_VIP_PAIRS`,
  `SCANNER_HOT_RESCAN_ENABLED` (default false), `SCANNER_HOT_RESCAN_TOP_N`.
- `CORE/data_providers/base.py` — método `get_ticker_24h_snapshot()` com
  default seguro (`{}`) para providers que não implementam.
- `CORE/data_providers/mexc_provider.py` — implementação real, reaproveita
  a chamada bulk já existente em `get_symbols()`.
- `ENGINE/signals/signal_tracker.py` — `get_recently_approved_pairs()`
  (leitura apenas).
- `main.py` — cache `self._priority_cache` populado com dados já
  calculados (`ind.rvol`, `ind.adx`, `ind.atr_percent`, `momentum_score`);
  reordenação de uma cópia local de `self._symbols` antes do
  `ThreadPoolExecutor`, com fallback seguro para a ordem original em caso
  de falha.
- `TESTS/test_priority_score_scanner.py` (novo, 17 testes).

## Divergências do Prompt Original (Documentadas, Não Ocultadas)

| Termo pedido | Implementação real | Motivo |
|---|---|---|
| RVOL, ATR%, ADX, Momentum | Cache do ciclo anterior | Só existem após buscar candles completos — calcular antes da ordem exigiria buscar candles 2x, violando "não aumentar chamadas de API" |
| Spread baixo | Não implementado (contribui 0) | Pipeline atual não mede spread real (valor fixo 0.0 em todo o código) |
| Liquidez alta | Proxy via percentil de volume 24h | Profundidade de book não é coletada hoje |
| Reescaneamento top 20 | Feature opcional, default OFF | É trabalho extra real (mais API/tempo) — usuário decidiu manter desligado |

## Testes Executados

- `TESTS/test_priority_score_scanner.py`: 17 testes — bônus individuais,
  blacklist, fallback seguro (ticker vazio → ordem original), garantia de
  que nenhum par é perdido/duplicado na reordenação, e teste explícito de
  que `compute_priority_score` não aceita/retorna campos de Decision
  Engine.
- Suite completa: **85/85 passando**, zero regressão.

## Auditoria

- `priority_score.py` não importa nada de `ENGINE.decision` — isolamento
  estrutural confirmado (não é possível influenciar gates por acidente).
- Reordenação opera sobre uma cópia local (`scan_order`), nunca muta
  `self._symbols` — lista mestra preservada.

## Homologação

- Local: 2 ciclos completos pós-restart, sem exceção de reordenação
  (nenhum warning de fallback), Diagnóstico Avançado confirmando 0 erros.
- VPS: deploy confirmado, processo estável (restarts 19→20, o esperado do
  próprio restart de deploy; `unstable restarts: 0`), sem tracebacks.
- Nota: erros HTTP 429 (rate limit MEXC) observados no VPS são
  **pré-existentes** (confirmados desde 2026-07-11 23:09, antes desta
  RFC) — não são uma regressão introduzida por esta mudança.

## Validação de Métricas (Diretriz Permanente) — EM ANDAMENTO

Esta RFC pode, na prática, alterar quais sinais são capturados a tempo
(mesmo sem mudar a lógica de aprovação), então — conforme a Diretriz
Permanente do QuantOS — não pode ser considerada concluída apenas por
compilar e passar nos testes. Ainda são necessários, com dados reais:

- Comparação de Win Rate, Profit Factor, tempo médio até aprovação e
  número de sinais capturados dentro da entry zone, antes vs. depois.
- Período de observação suficiente (a definir — múltiplas horas de
  operação real) para ter amostra estatisticamente significativa.

**Este relatório será atualizado (ou substituído por um relatório de
liberação) quando essa evidência estiver disponível.**

## Compatibilidade

Windows/Linux/VPS — usa apenas stdlib + provider abstrato com fallback.

## Riscos Remanescentes

- Médio, conforme já descrito na RFC: mudança de ordem pode capturar
  sinais diferentes dos que seriam capturados na ordem alfabética antiga,
  em cenários de borda (entry zone que se fecha entre o início e o fim do
  ciclo). Mitigado por: (a) fallback seguro em caso de falha do ticker,
  (b) primeiro ciclo pós-boot roda sem histórico (comportamento
  equivalente ao atual), (c) validação de métricas pendente antes de
  considerar a RFC definitivamente liberada.

## Estratégia de Rollback

Reverter a reordenação é uma mudança de 1 linha em `main.py`
(`scan_order = list(self._symbols)` em vez de chamar
`reorder_pairs_by_priority`). `git revert` do(s) commit(s) desta RFC para
rollback completo.

## Próxima Fase Recomendada

Continuar observação em produção (VPS) e comparar métricas reais
(Win Rate, PF, sinais capturados a tempo) antes/depois da reordenação,
conforme a Diretriz Permanente. Não liberar como "concluída" até essa
evidência existir.
