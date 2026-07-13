# RFC V20.5 - Paper Trading com Sinal Unico do Ciclo

## Objetivo
Garantir que o paper trading registre somente o mesmo melhor sinal aprovado escolhido para publicacao no ciclo.

## Motivacao
O fluxo de Telegram deduplica sinais por ativo e envia apenas `cycle_result.best_signal`, mas o paper trading ainda percorre `all_decisions`. Isso pode registrar multiplos timeframes do mesmo ativo no mesmo ciclo, criando divergencia entre Telegram, metricas e registry.

## Arquivos afetados
- `main.py`
- `TESTS/test_rfc_v20_4_validation_blocked_paper_trading.py`

## Impacto esperado
Para cada par/ciclo, no maximo um sinal aprovado entra no paper trading: o mesmo `best_signal` usado na publicacao. Rejeicoes e bloqueios finais continuam impedindo registro.

## Riscos
Baixo. A mudanca reduz duplicidade e preserva a fonte unica de selecao ja estabelecida pela RFC V18.4.

## Plano de implementacao
1. Adicionar teste de regressao provando que apenas o melhor sinal aprovado e candidato ao paper trading.
2. Criar helper pequeno para selecionar candidatos de paper trading a partir de `CycleSignalResult`.
3. Trocar o loop sobre `all_decisions` pelo candidato unico.

## Plano de rollback
Reverter este RFC, o teste adicionado e a chamada ao helper de selecao unica.

## Criterios de aceitacao
- Teste falha antes da correcao.
- Teste passa apos a correcao.
- Paper trading nao registra multiplos timeframes do mesmo par/ciclo.
- Sinais bloqueados por validacao final continuam sem registro.
