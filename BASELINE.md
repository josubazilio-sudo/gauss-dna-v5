# Baseline — QuantOS V19.1

Data: 2026-07-16
Versão: V19.1
Engine: V19.1

## Baseline Anterior
- V18.6: Trend Hard Gate + diagnostico solo log + RCDE

## O que mudou (V19.1)
- **ELITE SIGNAL CARD**: novo layout limpo e profissional do cartão de sinais
- Header dual: 👑 ELITE (score >= 80) / 🏆 APROVADO (score 60-79)
- Score < 60 não envia mais Telegram
- Seções: Score/Probabilidade/Confiança/Risco → Entrada/TP/SL/RR → Contexto → Confluências → Operação → Motivo → Status
- Removido: ADX, RVOL, ATR, Fluxo, Estrutura, Liquidez, Coerência, Votação, Penalidades, Convicção, Expectativa, MTF Conflict, auditoria completa (Signal ID, Versão, Ciclo, PID, Servidor, Build, UTC, Processamento), Valor nominal, Margem, Quantidade, Sobre patrimônio, Sobre margem, approval_reasons

## Arquivos alterados
- `SERVICES/telegram/telegram_formatter.py` — reescrita completa
- `SERVICES/telegram/telegram_service.py` — filtro score < 60
- `main.py` — engine_version → V19.1
- `CHANGELOG.md`, `docs/RFC_V19_1_ELITE_SIGNAL_CARD.md` — documentação

## Testes
- 686/686 passando, 0 falhas
- 4 testes atualizados para o novo formato

## Health
- 100% (sem alteração de lógica de trading)
