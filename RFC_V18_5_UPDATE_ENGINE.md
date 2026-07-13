# RFC V18.5 — Update Engine para o Telegram

Data: 2026-07-12

## Objetivo
Eliminar spam de atualizações no Telegram, enviando mensagens apenas quando ocorrerem mudanças relevantes (configuradas por thresholds específicos), mantendo o histórico de cada Signal ID e sem alterar a lógica de negociação.

## Diagnóstico
Atualmente, o sistema envia uma atualização a cada ciclo do scanner, gerando excesso de mensagens e repetindo informações irrelevantes ou de baixa variação, o que dilui o impacto dos sinais.

## Arquivos Afetados
- `SERVICES/telegram/telegram_service.py`: Integração com o `UpdateEngine`.
- `SERVICES/telegram/telegram_formatter.py`: Suporte a novos labels de atualização (📈, 📉, etc.).
- `SERVICES/telegram/signal_tracker.py` (NOVO): Estado persistente dos sinais ativos.
- `SERVICES/telegram/update_engine.py` (NOVO): Lógica de comparação e classificação.

## Critérios de Aceitação
- Atualizações enviadas APENAS se as 16 regras de relevância forem atendidas.
- Histórico mantido por Signal ID (sem criar novos IDs para a mesma operação).
- Labels claros de classificação: 📈 SETUP FORTALECIDO, 📉 SETUP ENFRAQUECIDO, 🎯 TP ATUALIZADO, 🛡 STOP AJUSTADO, 🔄 REVERSÃO, ❌ SINAL CANCELADO, ✅ OPERAÇÃO ENCERRADA.
- Nenhuma mudança na lógica operacional do Scanner/Decision Engine/Risk.

## Plano de Rollback
Reversão dos commits em `SERVICES/telegram/`.
