# RFC V19.1 — ELITE SIGNAL CARD

## Objetivo
Redesenhar completamente o cartão de sinais do QuantOS para ser limpo, profissional,
rápido de ler (menos de 5 segundos) e destacar apenas informações essenciais.

## Motivação
O card atual possui excesso de informações técnicas (ADX, RVOL, ATR, Fluxo,
Estrutura, Liquidez, Coerência, Votação, Penalidades, etc.) que não agregam
valor imediato ao operador. A auditoria (Signal ID, Versão, Ciclo, PID,
Servidor, Build, UTC, Processamento) polui ainda mais o card.

## Alterações

### Novo layout
```
👑 ELITE SIGNAL (overall_score >= 80) ou 🏆 APROVADO (overall_score 60-79)

SYMBOL
🔴 SHORT | TIMEFRAME

━━━━━━━━━━━━━━━━━━

🎯 Score
72.4/100 🏆

🎲 Probabilidade
72%

🧠 Confiança
86%

⚠️ Risco
24/100

━━━━━━━━━━━━━━━━━━

💰 Entrada
1.5900

🎯 Take Profit
1.5600

🛑 Stop Loss
1.6000

⚖️ RR
2.30

━━━━━━━━━━━━━━━━━━

🧠 Contexto

Regime
Trending Down

Setup
Trend Continuation

━━━━━━━━━━━━━━━━━━

✅ BOS
✅ Order Block
✅ Fair Value Gap
✅ Kalman DOWN

━━━━━━━━━━━━━━━━━━

💵 Operação

Capital
200 USDT

Alavancagem
25x

Lucro Estimado
13.92 USDT

Perda Máxima
5.76 USDT

━━━━━━━━━━━━━━━━━━

🧠 Motivo
Continuação da tendência de baixa após confirmação de BOS e Order Block,
com Kalman alinhado e liquidez elevada.

━━━━━━━━━━━━━━━━━━

🟢 STATUS

ENTRADA LIBERADA
```

### Removido do card
- Signal ID, PID, Servidor, Build, UTC, Processamento, Versão, Ciclo
- ADX, RVOL, ATR, Fluxo, Estrutura, Liquidez
- Coerência (coherence_score, coherence_audit)
- Votação (weighted_vote)
- Penalidades (penalty_details, penalty_reasons)
- Erros de validação (final_validation_errors)
- Convicção (conviction_level)
- Expectativa (expectancy_level)
- MTF Conflict
- Quality Score individual
- Consensus Score individual
- Valor nominal, Margem, Quantidade, Sobre patrimônio, Sobre margem
- Motivos de aprovação (approval_reasons) — substituído pelo main_reason

### Adicionado/Modificado
- Header: `👑 ELITE SIGNAL` (score >= 80) ou `🏆 APROVADO` (score 60-79)
- Score section: Score, Probabilidade, Confiança, Risco — cada um em linha própria
- Prices section: Entrada, Take Profit, Stop Loss, RR
- Context section: Regime + Setup
- Confluences: ✅ BOS, ✅ CHoCH, ✅ Order Block, ✅ Fair Value Gap, ✅ Kalman
- Operation section: Capital, Alavancagem, Lucro Estimado, Perda Máxima
- 🧠 Motivo: main_reason em formato narrativo
- 🟢 STATUS + ENTRADA LIBERADA no final

### Filtro adicional
Sinais com overall_score < 60 (BRONZE/REPROVADO) não são mais enviados ao Telegram.

## Arquivos afetados
- `SERVICES/telegram/telegram_formatter.py` — reescrita completa do `format_signal()`
- `SERVICES/telegram/telegram_service.py` — adicionado filtro score < 60

## Impacto esperado
- Cards mais limpos e profissionais
- Leitura em menos de 5 segundos
- Redução de ~70% do tamanho do card
- Eliminação de ruído visual
- Padronização institucional

## Riscos
- Nenhum. Apenas formatação visual, sem alteração de lógica de trading.

## Rollback
Reverter `SERVICES/telegram/telegram_formatter.py` e `SERVICES/telegram/telegram_service.py`
para o commit anterior.

## Critérios de aceitação
1. Card é legível em menos de 5 segundos
2. Informações essenciais visíveis imediatamente
3. Score >= 80 mostra 👑 ELITE SIGNAL, score 60-79 mostra 🏆 APROVADO
4. Score < 60 não envia Telegram
5. Audit/technical info removida do card
6. 🧠 Motivo explica o trade em formato narrativo
