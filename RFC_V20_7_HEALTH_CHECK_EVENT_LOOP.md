# RFC V20.7 - Ciclo de Vida do Event Loop do Health Check

## Objetivo
Garantir que os event loops criados para `HealthMonitor.check()` sejam fechados apos uso.

## Motivacao
`main.py` cria novos event loops em `start()` e no `_scan_loop()`, mas nao fecha esses loops. Em execucao longa, isso pode acumular recursos e dificultar diagnostico.

## Arquivos afetados
- `main.py`
- `TESTS/test_rfc_v20_7_health_check_event_loop.py`

## Impacto esperado
Cada health check sincrono cria, usa e fecha seu event loop explicitamente.

## Riscos
Baixo. A mudanca encapsula comportamento existente sem alterar a rotina assicrona do `HealthMonitor`.

## Plano de implementacao
1. Adicionar teste provando que o loop criado pelo helper e fechado.
2. Criar helper `_run_health_check_sync`.
3. Substituir os dois blocos de criacao manual de event loop.

## Plano de rollback
Reverter este RFC, o teste e o helper, restaurando os blocos anteriores.

## Criterios de aceitacao
- Teste falha antes do helper.
- Teste passa apos o helper.
- `main.py` nao duplica a criacao manual de event loop para health check.
