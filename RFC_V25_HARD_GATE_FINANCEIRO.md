# RFC V25 — Hard Gate Financeiro e Unificação do Dimensionamento de Capital

## Objetivo
Corrigir a causa raiz da inconsistência financeira reportada (sinal BULLSUSDT com
valor nominal/margem incompatíveis com a conta configurada, e aprovação mesmo com
conflito MTF), sem duplicar auditorias já existentes.

## Motivação
O QuantOS já possuía 3 camadas de auditoria (RFC V18.4, V21 Math Auditor, V22
Execution Validator), mas nenhuma delas validava os valores calculados contra os
limites reais da conta (`QUANTOS_ACCOUNT_SIZE`, `QUANTOS_LEVERAGE_MAX`). A
investigação encontrou 3 bugs concretos que anulavam o efeito prático do Hard Gate:

1. `BOTS/mexc/bot_engine.py::_update_balance()` usava saldo fixo de 10.000 USDT em
   paper trading, ignorando `QUANTOS_ACCOUNT_SIZE=200` do `.env`.
2. `main.py` sempre atribuía `leverage=1.0` porque `BotConfig` nunca teve o atributo
   `leverage` (fallback de `hasattr` sempre falhava), desconectando
   `QUANTOS_LEVERAGE_MAX=25` de qualquer cálculo real.
3. `ENGINE/auditor/institutional_math_auditor.py` (V21) validava apenas
   auto-consistência aritmética (checks tautológicos), nunca contra os limites da
   conta. Conflito MTF isolado não bloqueava o sinal, só ajustava um fator interno
   de Probabilidade.

## Arquivos Afetados
| Arquivo | Mudança |
|---|---|
| `BOTS/mexc/bot_engine.py` | `_update_balance()`: saldo em paper trading passa a usar `ACCOUNT_SIZE` (`QUANTOS_ACCOUNT_SIZE`) em vez de `10000.0` fixo. Branch `is_live()` não alterado. |
| `BOTS/mexc/bot_config.py` | Novo campo `leverage: float = LEVERAGE_MAX_USER` (mesma env var `QUANTOS_LEVERAGE_MAX` já usada em `scanner_config.py`). |
| `main.py` | `data["leverage"]` simplificado (remove fallback morto); chamada ao `InstitutionalMathAuditor.audit()` passa `account_capital=ACCOUNT_SIZE, max_leverage=LEVERAGE_MAX_USER`; gate combinado "Conflito MTF + Estrutura Fraca" substituído por gate padrão "Conflito MTF entre timeframes" (sempre reprova, independente da estrutura); mapeamento de gate/log (`_fv_gate`, `_bgates`) reconhece o novo motivo como `MTF_CONFLICT`. |
| `ENGINE/auditor/institutional_math_auditor.py` | `audit()` ganha parâmetros opcionais `account_capital` e `max_leverage`, com 2 checks reais e não tautológicos: `MarginWithinCapital` (margem ≤ capital) e `LeverageWithinLimit` (alavancagem ≤ máxima). `hard_fail_reason` passa a detalhar qual(is) check(s) falharam. |

## Impacto Esperado
- Posições em paper trading dimensionadas contra o capital real ($200), não mais
  contra um saldo fantasma de $10.000.
- `QUANTOS_LEVERAGE_MAX` deixa de ser uma trava morta — é aplicado tanto no
  dimensionamento quanto no Hard Gate do Math Auditor.
- "Exposição máxima" é coberta automaticamente como consequência de
  `Margem ≤ Capital` e `Alavancagem ≤ Máxima` (decisão confirmada com o usuário —
  sem nova variável de ambiente).
- Conflito MTF isolado passa a reprovar o sinal sempre, igual ao gate já existente
  para Kalman contrário — fecha o caso relatado de "sinal aprovado mesmo com
  conflito MTF".

## Riscos
- Sinais que hoje são aprovados com margem calculada contra o saldo fantasma podem
  passar a ser bloqueados legitimamente (comportamento esperado e desejado).
- Nenhuma alteração no branch de execução real (`is_live()`) nem no
  `ExchangeExecutionValidator` (V22).

## Plano de Rollback
Reverter os 4 arquivos modificados (nenhuma migração de dados, nenhuma mudança de
schema). O `.env` não precisa de nenhuma variável nova.

## Critérios de Aceitação
- [x] Todas as operações usam o capital configurado (`QUANTOS_ACCOUNT_SIZE`) em
      paper trading.
- [x] Dimensionamento respeita `QUANTOS_LEVERAGE_MAX`.
- [x] Limite de exposição aplicado como consequência de capital × alavancagem
      máxima.
- [x] Conflito MTF impacta efetivamente a decisão final (reprova sempre).
- [x] Inconsistência financeira (margem/alavancagem acima do limite) bloqueia
      automaticamente o envio do sinal, com motivo detalhado no log.
- [x] Nenhuma auditoria redundante criada — extensão do Math Auditor (V21) e do
      bloco `validation_errors` (V18.4/V18.5) já existentes.
- [x] Suite completa de testes sem regressão: 492/492 passando (15 testes novos:
      6 em `test_rfc_v21_math_auditor.py`, 9 em
      `test_rfc_v25_hard_gate_financeiro.py`).

## Status
Implementado e testado localmente (paper trading). Pendente: propagação para o
VPS e observação de ciclos reais para confirmar ausência de regressão em produção.
