# Architecture - QuantOS V17.1 Approval Flow

## Pipeline de Aprovacao
O fluxo permanece: Scanner -> Consensus -> DecisionEngine -> DecisionBrain -> SelfAudit -> Publication/PaperTrading.

## Mudanca V17.1
- `DecisionEngine` continua sendo responsavel pelos hard gates eliminatorios.
- `DecisionBrain=EXECUTAR` aprova somente se hard gates ja passaram.
- `DecisionBrain=PRONTO` agora aprova de forma controlada somente se hard gates ja passaram.
- `DecisionBrain=OBSERVACAO` e `REJEITADO` continuam bloqueados.

## Controles Mantidos
- Dados de mercado validos.
- RVOL, ADX, spread, BOS/CHOCH, trend, estrutura, smart money, entry zone.
- Quality, confidence, risk, institutional, structural, flow, liquidity, timing, conviction.
- Consensus minimo `0.60`.
- RR minimo `2.0`.
- Self-audit obrigatorio para publicacao.
- Validacao de entry, stop loss, take profit e risk reward.
