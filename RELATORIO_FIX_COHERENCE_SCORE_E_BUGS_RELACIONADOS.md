# Relatório Final — Correção do Bug do Coherence Score e Bugs Relacionados

Data: 2026-07-12

## Resumo Executivo

Investigando por que o QuantOS não estava dando sinal, mesmo com o
Decision Engine aprovando setups de qualidade real (ex.: CHZUSDT SHORT,
quality ~0.71-0.75, todos os hard gates aprovados), encontrei uma cadeia
de 3 bugs pré-existentes (não introduzidos nesta sessão, mas
diagnosticados e corrigidos nela) que impediam qualquer sinal de
completar o ciclo até o Telegram:

1. **Coherence Score / Votação Ponderada** (`ENGINE/common/operational.py`)
   liam campos que nunca existiam no dicionário do sinal, zerando 37% do
   peso de decisão para qualquer sinal em tendência.
2. **Telegram formatter** (`SERVICES/telegram/telegram_formatter.py`)
   quebrava ao formatar a mensagem por causa de um comportamento de
   auto-wrapping do `_AttrDict`.
3. **TradeRegistry** (`ENGINE/common/trade_registry.py`) chamava uma
   função com a assinatura errada ao tentar registrar o trade.

Os bugs 2 e 3 só ficaram visíveis DEPOIS de corrigir o bug 1, porque
antes nenhum sinal chegava tão longe no pipeline.

## Arquivos Modificados

- `ENGINE/decision/signal_decision.py` — campos `flow_score`/`momentum_score`
  adicionados (aditivo).
- `ENGINE/common/operational.py` — `compute_institutional_coherence_score`
  e `compute_weighted_vote` corrigidos (leitura de `bos`/`choch` reais,
  comparação de tendência por substring).
- `SERVICES/telegram/telegram_formatter.py` — novo helper `_unwrap()`,
  aplicado em 6 pontos.
- `ENGINE/common/trade_registry.py` — chamada de
  `OperationalCalculator.calculate()` corrigida, mapeamento de campos de
  saída atualizado.
- `main.py` — `trading_data` agora repassa `quantity`/`balance`/`leverage`
  para o `TradeRegistry.open_trade()`.
- `TESTS/test_fix_coherence_score_campos_ausentes.py` (9 testes),
  `TESTS/test_fix_telegram_attrdict_e_trade_registry.py` (9 testes),
  4 testes preexistentes atualizados para o contrato real de campos.

## Incidente Durante a Implementação

`ENGINE/common/operational.py` foi acidentalmente sobrescrito com
conteúdo colado no editor (uma mensagem de Telegram de outro bot, não
relacionada ao código) enquanto o arquivo estava aberto no IDE durante a
implementação. Detectado imediatamente pelo `ast.parse` falhando.
Recuperado com sucesso a partir da cópia válida do último deploy no VPS
(anterior ao incidente), e as duas correções foram reaplicadas sobre essa
base recuperada. Nenhum trabalho foi perdido.

## Testes Executados

- 9 testes reproduzindo o cenário real do bug (CHZUSDT-like: SHORT em
  regime `trending_down`, bem alinhado) antes/depois do fix do
  Coherence Score.
- 9 testes para os bugs de Telegram/TradeRegistry, incluindo reprodução
  do comportamento de auto-wrap do `_AttrDict` e verificação de que
  `open_trade()` sem dado pré-calculado não lança mais exceção.
- Suite completa: **167/167 passando**, zero regressão.

## Auditoria

- Nenhuma mudança de threshold (60%/70% da Validação Final continuam os
  mesmos) — só os inputs dos cálculos foram corrigidos.
- Nenhuma mudança em Decision Engine, Scanner, gates institucionais.
- Bugs corrigidos são estritamente de leitura/mapeamento de campos, não
  de lógica de negócio.

## Homologação

- VPS: após o fix do Coherence Score, `AVICIUSDT SHORT` confirmado
  passando pela Validação Final pela primeira vez na sessão
  (`DEDUP: AVICIUSDT_30M_SHORT... -> novo_sinal`, `status=APPROVED`),
  revelando os bugs 2 e 3 nos logs subsequentes.
- Fix de Telegram/TradeRegistry deployado em seguida; monitoramento
  contínuo para confirmar que o próximo sinal aprovado completa o ciclo
  inteiro (Telegram enviado, trade registrado) sem exceção.

## Riscos Remanescentes

- Médio: com os 3 bugs corrigidos, mais sinais devem passar pela
  Validação Final do que passavam antes (efeito pretendido — corrigir
  falso-negativo sistemático). Recomenda-se observação contínua em
  produção para confirmar que a qualidade dos sinais aprovados se
  mantém alta (não há evidência de que os thresholds em si precisem de
  ajuste — só os inputs estavam errados).
- Baixo: possíveis outros pontos no codebase que dependem do schema
  antigo do `OperationalCalculator` (`leverage`, `account_size`, etc.)
  não mapeados nesta correção, caso existam fora de
  `trade_registry.py`. Recomenda-se busca futura por
  `ops.get("leverage"` / `ops.get("account_size"` em outros módulos.

## Estratégia de Rollback

Cada correção é isolada e pequena (poucas linhas por arquivo). `git
revert` do(s) commit(s) desta correção restaura o comportamento anterior
(sinais voltam a travar na Validação Final, mas sem risco de dado
incorreto).

## Próxima Fase Recomendada

- Confirmar via monitoramento contínuo que um sinal real completa o
  ciclo inteiro (Decision Engine → Validação Final → Telegram → Trade
  Registry) sem nenhuma exceção.
- Acompanhar a taxa de aprovação real nos próximos ciclos para validar
  que o fix não está deixando passar sinais genuinamente fracos (só
  sinais que já eram bons e estavam sendo mal-julgados por bug).
