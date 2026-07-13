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
