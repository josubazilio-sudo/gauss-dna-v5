# RFC V21 — Institutional Math Auditor

## Objetivo
Implementar uma auditoria matemática automática que valide **100% dos sinais** antes do envio ao Telegram, garantindo que nenhum sinal com inconsistência matemática chegue aos assinantes.

## Motivacao
Sinais com erros de position sizing, alavancagem, margem ou RR minam a confianca institucional do QuantOS. A auditoria manual e impraticavel em producao. Um auditor automatizado executa em <1ms e bloqueia qualquer divergencia >0.10%.

## Arquivos criados
- `ENGINE/auditor/__init__.py` — modulo do pacote
- `ENGINE/auditor/institutional_math_auditor.py` — classe InstitutionalMathAuditor
- `TESTS/test_rfc_v21_math_auditor.py` — 41 testes com cobertura >95%

## Arquivos modificados
- `main.py` — integracao do auditor apos calculo de quantity/balance/leverage (linha 1008-1029)

## Fluxo da auditoria

1. SignalDecision gera o sinal com entry, stop, tp, scores
2. Bot.risk_manager.calculate_position_size() calcula quantity
3. **AUDITOR**: recebe entry, stop, tp, quantity, balance, leverage, RR esperado
4. Recalcula TUDO do zero, sem reutilizar nenhum valor pre-calculado:
   - Stop distance, TP distance, RR
   - Nominal, Margem, MaxLoss, ExpectedProfit
   - ReturnOnAsset, ReturnOnMargin, ReturnOnEquity
   - RiskPercentage, CapitalUsed
   - 5 verificacoes de coerencia (Qty*Entry=Nominal, Nominal/Lev=Margin, etc.)
5. Se qualquer divergencia > 0.10%: `_validation_blocked = True`, `hard_fail_reason = "MATH_VALIDATION_FAILED"`
6. Sinal bloqueado antes do Telegram sender

## Formulas

| Metrica | Formula |
|---|---|
| StopDistance | `abs(entry - stop)` |
| TPDistance | `abs(entry - tp1)` |
| RR | `TPDistance / StopDistance` |
| Nominal | `quantity * entry` |
| Margem | `Nominal / leverage` |
| MaxLoss | `quantity * StopDistance` |
| ExpectedProfit | `quantity * TPDistance` |
| ReturnOnAsset | `(TPDistance / entry) * 100` |
| ReturnOnMargin | `(ExpectedProfit / Margem) * 100` |
| ReturnOnEquity | `(ExpectedProfit / balance) * 100` |
| RiskPercentage | `(MaxLoss / balance) * 100` |
| CapitalUsed | `Nominal / leverage` |

## Limite de divergencia
MAX_DIVERGENCE_PCT = 0.10%

## Cobertura dos testes
- 41 testes
- Classes: AuditCheck, AuditResult, PctDiff, ValidSignal (CATONUSDT real), InvalidSignal, EdgeCases, MaxDivergence, CheckCoverage, AuditResultLog
- Casos: RR correto, RR errado, precos zero/negativos, precos muito pequenos/grandes, alta alavancagem, divergencia no limite

## Performance
Tempo medio por auditoria: <0.5ms (operacoes aritmeticas simples, sem IO)

## Impacto esperado
- 0 sinais com erro matematico enviados aos assinantes
- Bloqueio automatico de inconsistencias de position sizing
- Rastreabilidade via BLOCKED_SIGNALS.log
- Diagnostico claro do motivo de bloqueio

## Criterios de aceitacao
- [x] Nenhum calculo reutilizado — todos recalculados independentemente
- [x] Divergencia maxima permitida: 0.10%
- [x] Auditor executado antes do Telegram
- [x] Qualquer inconsistencia bloqueia o sinal (`_validation_blocked = True`)
- [x] Todos os 374 testes aprovados (333 originais + 41 novos)
