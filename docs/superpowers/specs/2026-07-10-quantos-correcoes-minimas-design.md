# QuantOS Correcoes Minimas De Seguranca - Design

Data: 2026-07-10

## Objetivo

Corrigir bugs objetivos no fluxo de sinal do QuantOS sem alterar estrategia, pesos, thresholds, quantidade alvo de sinais ou arquitetura geral.

O foco e preservar seguranca operacional, coerencia de decisao e integridade dos precos enviados ao Telegram.

## Escopo Aprovado

1. Corrigir compatibilidade entre regimes `trending_up` / `trending_down` e os gates que esperam `uptrend` / `downtrend`.
2. Garantir que `SignalDecision.from_signal()` propague `risk_reward` do sinal quando existente.
3. Impedir que `DecisionBrain` aprove um sinal rejeitado por hard gates do `DecisionEngine`.
4. Corrigir direcao dos FVGs detectados em `scanner_patterns.py`.
5. Implementar validacao real de spread no `DecisionEngine` usando `HARD_MAX_SPREAD` quando o dado existir.
6. Executar validacao critica antes de publicar `decision.made` e antes de abrir paper trade.
7. Ajustar formatacao de precos no Telegram para ativos de baixo preco, evitando exibir `0.00`.

## Fora Do Escopo

- Alterar pesos de score.
- Alterar thresholds institucionais.
- Criar novos filtros quantitativos.
- Otimizar para aumentar quantidade de sinais.
- Refatorar DecisionEngine, DecisionBrain ou Validator em uma nova arquitetura.
- Alterar execucao live ou integracoes de ordem.

## Design Tecnico

### Regime E Tendencia

O gate de tendencia deve aceitar os nomes reais emitidos pelo `MarketRegime`: `trending_up`, `trending_down`, `ranging`, `volatile`, `reversal`, `calm`.

Mapeamento pretendido:

- `trending_up` e `uptrend` equivalem a alta.
- `trending_down` e `downtrend` equivalem a baixa.
- demais regimes continuam usando a logica lateral/reversao ja existente.

### Risk Reward

`SignalDecision.from_signal()` deve copiar `signal.risk_reward` para `SignalDecision.risk_reward`. Isso evita que sinais ja calculados pelo `RiskManager` sejam tratados como RR zero.

### DecisionBrain

O `DecisionBrain` nao deve transformar uma decisao rejeitada pelo `DecisionEngine` em aprovada. Ele pode bloquear, colocar em observacao ou manter aprovacao ja concedida, mas nao deve fazer bypass dos hard gates.

### FVG

O detector de FVG deve alinhar direcao com a interpretacao do gap:

- Gap para baixo deve ser bearish/SHORT.
- Gap para cima deve ser bullish/LONG.

### Spread

O `DecisionEngine` deve usar spread quando disponivel em `signal.entry_details` ou campo equivalente. Se nao houver dado real, nao deve inventar spread alto; deve manter comportamento seguro e registrar ausencia do dado.

### Validacao Antes De Publicar

Antes de publicar `decision.made` e antes de registrar paper trade, o fluxo deve aplicar as mesmas validacoes criticas hoje existentes no Telegram: entrada, stop, TP, RR e flags obrigatorias de decisao aprovada.

### Telegram

Preco deve ser formatado com precisao dinamica:

- Precos >= 1: duas casas decimais.
- Precos entre 0.01 e 1: quatro a seis casas.
- Precos abaixo de 0.01: ate oito ou mais casas, sem virar `0.00`.

## Riscos

- Corrigir FVG pode alterar direcao de sinais historicos baseados nesse padrao.
- Bloquear bypass do `DecisionBrain` pode reduzir sinais aprovados.
- Validacao antecipada pode bloquear paper trades que antes eram registrados, mas isso e desejado se a decisao for incoerente.

## Criterios De Sucesso

- Nenhum sinal aprovado deve sair com entrada, stop, TP ou RR invalidos.
- `DecisionBrain` nao deve aprovar sinal reprovado por hard gate.
- Regimes `trending_up` e `trending_down` devem ser avaliados corretamente pelo gate de tendencia.
- FVG deve ter direcao consistente com gap bullish/bearish.
- Telegram deve exibir precos de altcoins sem arredondar para zero.
- Nenhum threshold, peso ou regra estrategica nao relacionada aos bugs deve ser alterado.
