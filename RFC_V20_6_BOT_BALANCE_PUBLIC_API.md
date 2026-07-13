# RFC V20.6 - API Publica de Balance do Bot

## Objetivo
Remover o acesso externo ao atributo privado `_balance` do `BotEngine`.

## Motivacao
`main.py` calcula quantidade operacional usando `self._bot._balance.total`, acoplando o orquestrador ao estado interno do bot. Uma propriedade publica preserva encapsulamento e evita quebra caso a implementacao interna mude.

## Arquivos afetados
- `BOTS/mexc/bot_engine.py`
- `BOTS/mexc/TESTS/test_bot_mexc.py`
- `main.py`

## Impacto esperado
Consumidores externos passam a usar `bot.balance`, mantendo o mesmo valor de saldo sem acessar atributo privado.

## Riscos
Baixo. A mudanca apenas expoe leitura do estado ja existente e troca um acesso direto por propriedade publica.

## Plano de implementacao
1. Adicionar teste exigindo `bot.balance`.
2. Criar propriedade `balance` no `BotEngine`.
3. Substituir `self._bot._balance.total` por `self._bot.balance.total`.

## Plano de rollback
Reverter este RFC, o teste, a propriedade e a troca em `main.py`.

## Criterios de aceitacao
- Teste falha antes da propriedade.
- Teste passa apos a propriedade.
- `main.py` nao acessa mais `_bot._balance`.
