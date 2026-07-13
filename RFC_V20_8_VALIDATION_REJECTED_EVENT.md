# RFC V20.8 - Evento Correto para Rejeicao por Validacao Final

## Objetivo
Publicar sinais bloqueados pela validacao final como `decision.rejected`, nao como `trade.closed`.

## Motivacao
Um sinal rejeitado nao representa uma posicao encerrada. Publicar esse caso como `trade.closed` pode poluir consumidores de trades fechados, metricas e notificacoes operacionais.

## Arquivos afetados
- `CORE/events/publishers.py`
- `main.py`
- `TESTS/test_rfc_v20_8_validation_rejected_event.py`

## Impacto esperado
Bloqueios de validacao final passam a emitir um evento semanticamente correto. O fluxo de trade fechado real permanece usando `trade.closed`.

## Riscos
Baixo. O tipo `EventTypes.DECISION_REJECTED` ja existe; a mudanca apenas expoe metodo no `Publisher` e usa esse evento no bloqueio final.

## Plano de implementacao
1. Adicionar teste para `Publisher.decision_rejected`.
2. Adicionar teste para helper de publicacao de bloqueio final.
3. Implementar metodo no `Publisher`.
4. Substituir o `trade_closed` do bloqueio final por `decision_rejected`.

## Plano de rollback
Reverter este RFC, o teste, o metodo do publisher e restaurar o bloco anterior em `main.py`.

## Criterios de aceitacao
- Teste falha antes da correcao.
- Teste passa apos a correcao.
- Bloqueio final nao publica `trade.closed`.
- Trades fechados reais continuam inalterados.
