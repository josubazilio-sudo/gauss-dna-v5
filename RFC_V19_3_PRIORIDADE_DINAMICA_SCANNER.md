# RFC V19.3 — Prioridade Dinâmica para Moedas de Alto Movimento

Data: 2026-07-12
(Renomeada de "V19.2" no prompt original para evitar colisão com a
RFC V19.2 — Estabilidade do AuditEngine, já implementada e liberada nesta
mesma sessão.)

## Objetivo

Introduzir um `PRIORITY_SCORE` que define **apenas a ordem** em que os pares
são escaneados a cada ciclo, para que ativos com maior probabilidade de
movimento explosivo sejam analisados primeiro. Não altera Score
Institucional, Confidence, Quality, Hard Gates, Decision Engine ou gestão de
risco.

## Motivação

Hoje `_discover_symbols()` (main.py) retorna `sorted(discovered)` — ordem
puramente alfabética, fixada uma vez no boot e reaproveitada em todos os
ciclos. Pares "quentes" (RVOL alto, rompendo máxima/mínima de 24h) podem ser
escaneados tarde no ciclo, perdendo parte do movimento.

## Arquivos Afetados

- `ENGINE/scanner/priority_score.py` (novo) — cálculo do `PRIORITY_SCORE`.
- `ENGINE/scanner/scanner_config.py` — novas constantes/env vars:
  `SCANNER_VIP_PAIRS` (lista configurável, bônus +20),
  `SCANNER_HOT_RESCAN_ENABLED` (default `false` — ver seção de risco),
  `SCANNER_HOT_RESCAN_TOP_N` (default 20).
- `CORE/data_providers/mexc_provider.py` — novo método
  `get_ticker_24h_snapshot()` reaproveitando a mesma chamada
  `/api/v3/ticker/24hr` já usada em `get_symbols()` (bulk, 1 chamada/ciclo),
  agora também extraindo `priceChangePercent`, `highPrice`, `lowPrice`,
  `lastPrice` (hoje só `quoteVolume` é extraído).
- `ENGINE/signals/signal_tracker.py` — método novo (leitura apenas) para
  checar se um par teve sinal aprovado nas últimas N horas.
- `main.py` — antes da submissão ao `ThreadPoolExecutor` em `_scan_loop`
  (hoje linha ~290), reordenar `self._symbols` por `PRIORITY_SCORE`. Sem
  alterar `_fetch_and_scan`, `_process_scan_result` nem o funil de decisão.
- `TESTS/test_priority_score_scanner.py` (novo).

## Cálculo do PRIORITY_SCORE — Adaptação Necessária (Divergência do Prompt Original)

O prompt original pede pontuação usando RVOL, ATR%, ADX, spread e liquidez —
mas **esses valores só existem depois de buscar candles completos do par**
(`MarketEngine.analyze`, que roda dentro de `_fetch_and_scan`, ou seja,
DEPOIS da ordem já ter sido decidida). Calcular esses indicadores antes da
ordenação exigiria buscar candles de todos os pares duas vezes por ciclo —
violando diretamente a regra "não aumentar chamadas de API" / "não impactar
desempenho" do próprio prompt. Solução proposta (documentando a divergência,
conforme exigido pelo processo — não implementar silenciosamente diferente
do pedido):

| Termo do prompt | Fonte usada nesta RFC | Observação |
|---|---|---|
| RVOL >= 2.0 (+40) | **Cache do ciclo anterior** (último RVOL calculado para o par) | Sem custo extra. No 1º ciclo pós-boot, contribui 0 (sem histórico ainda) |
| Volume 24h > média do universo (+30) | Ticker 24h (bulk, 1 chamada/ciclo) | Direto, sem custo extra |
| Variação de preço 24h > 5% (+25) | Ticker 24h | Direto |
| ATR% elevado (+20) | Cache do ciclo anterior | Mesmo racional do RVOL |
| ADX > 25 (+20) | Cache do ciclo anterior | Mesmo racional |
| Rompendo máxima/mínima 24h (+15) | Ticker 24h (`highPrice`/`lowPrice`/`lastPrice`) | Direto |
| Spread baixo (+15) | **Não implementado nesta RFC** | Pipeline atual não mede spread real (valor fixo 0.0 em todo o código hoje) — contribui 0 até uma RFC futura instrumentar spread real. Documentado como limitação conhecida, não fictício. |
| Liquidez alta (+15) | Aproximado pelo percentil do `quoteVolume` (ticker 24h) | Usa volume como proxy de liquidez, já que profundidade de book não é coletada hoje |
| Momentum crescente (+10) | Cache do ciclo anterior (`momentum_score`) | Mesmo racional do RVOL |
| Sinal aprovado nas últimas horas (+10) | `SignalTracker` (já existe, só leitura) | Direto, sem custo extra |
| VIP list (+20) | `SCANNER_VIP_PAIRS` (env, configurável) | Direto |

No **primeiro ciclo após o boot**, os termos "cache do ciclo anterior"
contribuem 0 (não há histórico); a partir do 2º ciclo, o `PRIORITY_SCORE`
usa dados reais do ciclo imediatamente anterior. Isso é reavaliado a cada
ciclo (não é um valor estático).

## Blacklist Temporária

Pares com RVOL (cache) muito baixo **ou** volume 24h (ticker) insuficiente
vão para o fim da fila. Spread/liquidez-como-critério-de-exclusão ficam de
fora pelo mesmo motivo de instrumentação ausente (ver tabela acima).

## Lista VIP

`SCANNER_VIP_PAIRS` em `.env`, lista separada por vírgula, seguindo o
padrão já usado por `QUANTOS_CUSTOM_PAIRS`. Totalmente configurável, com
default vazio (sem VIPs) se não definida.

## Reescaneamento dos Top 20 — Ponto de Decisão (Trade-off Real)

O prompt pede reescanear os 20 pares de maior prioridade **antes** de
iniciar um novo ciclo completo. Isso é, por definição, **trabalho extra**:
20 buscas de candles + scans adicionais por ciclo, além do ciclo normal de
~300 pares. Isso **aumenta** o número de chamadas de API e o tempo de ciclo
— em tensão direta com "não aumentar chamadas de API" / "não impactar
desempenho" do mesmo prompt. Não há forma de reescanear pares "quentes"
sem buscar dados novos deles.

Proposta: implementar como **feature opcional**, controlada por
`SCANNER_HOT_RESCAN_ENABLED` (default `false`). Preciso de uma decisão sua
sobre isso — ver pergunta ao final desta mensagem.

## Impacto Esperado

- Pares com maior probabilidade de movimento são buscados/escaneados antes
  no `ThreadPoolExecutor`, reduzindo o atraso de captura em cenários onde
  há mais pares que workers disponíveis (hoje: até 300+ pares, 10 workers).
- Zero mudança em Decision Engine, Hard Gates, thresholds, scoring.

## Riscos

- Médio (mais alto que a RFC do Diagnóstico): esta mudança pode, na
  prática, alterar QUAIS sinais são capturados a tempo (mesmo sem mudar a
  lógica de aprovação) — porque um par escaneado mais cedo pode ainda estar
  dentro da entry zone, enquanto o mesmo par escaneado tarde (ordem antiga)
  já teria passado do ponto de entrada. Por isso esta RFC **exige** Paper
  Trading real com comparação de métricas antes/depois (Diretriz
  Permanente), não apenas testes unitários.
- Primeiro ciclo pós-boot roda com priorização parcial (sem cache ainda) —
  comportamento idêntico ao atual (ordem alfabética) até o 2º ciclo.
- Se `SCANNER_HOT_RESCAN_ENABLED=true`: aumento real de custo de API/tempo
  de ciclo — precisa ser medido e aceito explicitamente.

## Plano de Implementação

1. `get_ticker_24h_snapshot()` em `mexc_provider.py` (reaproveita chamada
   já existente, sem custo extra).
2. `priority_score.py`: função pura `compute_priority_score(pair, ticker_snapshot, cached_scores, is_vip, recently_approved) -> float`.
3. Cache do ciclo anterior: reaproveitar `ScannerScore`/indicadores já
   calculados por par no ciclo N para alimentar a priorização do ciclo N+1
   (dicionário simples em memória, sem persistência necessária).
4. Reordenação de `self._symbols` (cópia local, não a lista original) antes
   da submissão ao `ThreadPoolExecutor`.
5. Blacklist temporária: pares abaixo do corte vão para o fim da lista
   reordenada (não são excluídos do scan, só desprezados na fila).
6. `SCANNER_VIP_PAIRS`: leitura de env, bônus fixo.
7. (Condicional à decisão do usuário) Reescaneamento dos top 20 após ciclo
   completo, gated por `SCANNER_HOT_RESCAN_ENABLED`.
8. Testes unitários: cálculo do score por cenário (RVOL alto, VIP, sem
   histórico no 1º ciclo, blacklist, ticker ausente/erro).
9. Teste de integração: rodar `_scan_loop` simulado e confirmar que a
   ORDEM de `self._symbols` muda conforme prioridade, mas o **conteúdo**
   dos resultados de scan (aprovação/rejeição por par) é idêntico ao
   comportamento atual dado o mesmo input de candles.
10. **Paper Trading obrigatório** (Diretriz Permanente): rodar em paralelo
    (ordem antiga vs. nova, ou nova isolada com período de observação
    suficiente) e comparar Win Rate, tempo médio até aprovação, número de
    sinais capturados dentro da entry zone, antes/depois. Só considerar a
    RFC concluída com evidência real de melhoria ou neutralidade (não
    piora).

## Critérios de Aceitação

- `PRIORITY_SCORE` não influencia nenhum campo de scoring/decisão — só a
  ordem de varredura.
- Zero aumento de chamadas de API na configuração default
  (`SCANNER_HOT_RESCAN_ENABLED=false`).
- Suite de testes 100% verde, incluindo os novos testes.
- Paper Trading com dados reais mostrando resultado igual ou melhor
  (Win Rate, PF, sinais capturados a tempo) — não apenas "compila e passa
  teste".
- Documentação (CHANGELOG, relatório final) atualizada, incluindo a tabela
  de divergências desta RFC.

## Plano de Rollback

Mudança isolada: reordenação ocorre em um ponto único de `main.py` antes do
`ThreadPoolExecutor`. Reverter para `sorted(self._symbols)` (comportamento
atual) é uma mudança de 1 linha. `git revert` do(s) commit(s) desta RFC.
