# Test Report - QuantOS V17.1

Data: 2026-07-11

## Testes Executados
Comando:
`python -m pytest TESTS/test_decision_engine_v10.py TESTS/test_decision_engine_minimal_fixes.py TESTS/test_scanner.py`

Resultado:
- 13 passed em 1.10s.

## Validacao Real
Script temporario:
`C:\Users\josue\AppData\Local\Temp\opencode\validate_approval_cycle.py`

Resultado:
- `APPROVED_COUNT 1`.
- Aprovado: `67USDT`, timeframe `4h`, direcao `short`, estado `pronto`, hard gates `True`, self-audit `True`.

## Cobertura Funcional
- DecisionEngine hard gates.
- Scanner basico.
- Fluxo de aprovacao controlada `PRONTO`.
- Self-audit de sinal aprovado.

## RFC V25 (2026-07-14) — Hard Gate Financeiro

Comando:
`python -m pytest TESTS/ -q`

Resultado:
- **492 passed, 17 warnings em 9.46s** (0 falhas, 0 regressoes).
- 15 testes novos: 6 em `TESTS/test_rfc_v21_math_auditor.py`
  (`TestAccountCapitalAndLeverageGate`), 9 em
  `TESTS/test_rfc_v25_hard_gate_financeiro.py`.

Verificacao adicional:
- `python -c "import main"` — cadeia de imports OK, sem erro.
- `BotConfig().leverage == LEVERAGE_MAX_USER` (25.0) confirmado interativamente.
- `ACCOUNT_SIZE` confirmado lendo `QUANTOS_ACCOUNT_SIZE=200` do `.env` real.

Cobertura Funcional (V25):
- Saldo de paper trading usa capital real configurado (nao mais saldo fantasma).
- Alavancagem real aplicada no calculo e no Hard Gate.
- Math Auditor bloqueia margem acima do capital e alavancagem acima do maximo.
- Conflito MTF isolado reprova o sinal.
- Regressao: sinal consistente dentro do capital/alavancagem real continua
  aprovado (sem falso-positivo).
