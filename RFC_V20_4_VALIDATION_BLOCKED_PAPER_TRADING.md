# RFC V20.4 - Bloqueio de Paper Trading apos Validacao Final

## Objetivo
Impedir que sinais bloqueados pela validacao final sejam registrados como entradas de paper trading ou trades abertos no registry.

## Motivacao
O fluxo atual bloqueia o envio ao Telegram quando `final_validation_errors` existe, mas o processamento posterior ainda pode abrir trades simulados para decisoes aprovadas. Isso cria divergencia operacional: sinal rejeitado na camada final aparece como trade aberto nas metricas.

## Arquivos afetados
- `main.py`
- `TESTS/test_rfc_v20_4_validation_blocked_paper_trading.py`

## Impacto esperado
Sinais com `_validation_blocked=True` nao entram no paper trading, analytics de entrada ou trade registry. Sinais aprovados e sem bloqueio continuam seguindo o fluxo atual.

## Riscos
Baixo. A alteracao restringe somente o caminho posterior a uma rejeicao ja determinada pela validacao final.

## Plano de implementacao
1. Adicionar teste de regressao para o contrato de abertura de paper trade.
2. Centralizar a decisao em uma funcao pequena.
3. Usar essa funcao antes de registrar entradas simuladas.

## Plano de rollback
Reverter este RFC, o teste V20.4 e a condicao adicionada no fluxo de paper trading.

## Criterios de aceitacao
- Teste falha antes da correcao.
- Teste passa apos a correcao.
- Sinal bloqueado por validacao final nao abre paper trade.
- Sinal aprovado sem bloqueio segue elegivel para paper trading.
