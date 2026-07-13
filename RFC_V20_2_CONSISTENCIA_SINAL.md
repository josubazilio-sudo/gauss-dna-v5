# RFC V20.2 — Correção de Consistência do Sinal

Data: 2026-07-12

## Objetivo

Corrigir inconsistências de exibição do sinal (classificação duplicada,
cálculo de retorno sobre margem incorreto, informação redundante),
adicionando uma validação final antes do envio ao Telegram — sem tocar
em Scanner, Decision Engine, Consensus, Confluence, Score, Quality Gate,
filtros ou cálculos de entrada.

## Diagnóstico

### 1. Classificação divergente (confirmado em produção)

`ENGINE/common/operational.py:compute_overall_score()` já detecta e
LOGA esse problema, mas não o resolve:
```python
if scanner_tier != tier:
    log.warning("Classificacao divergente: scanner %s vs overall_score %.1f -> %s", ...)
```
`SERVICES/telegram/telegram_formatter.py` exibe DUAS classificações
diferentes: Bloco 2 ("Classificação e Qualidade") mostra `overall_tier`
(derivado do `overall_score` numérico); Bloco 6 ("Análise") mostra
`classification_label` (calculado independentemente pelo Scanner) — a
mesma divergência já logada como warning aparece literalmente na tela do
usuário.

### 2. Cálculo de "Retorno sobre Margem" incorreto

`OperationalCalculator.calculate()`:
```python
retorno_margem_pct = lucro_liquido_usdt / perda_maxima_usdt * 100
```
Isso calcula a razão lucro/perda (essencialmente o RR em %), não o
retorno sobre a margem/colateral realmente utilizado. A fórmula correta
para "retorno sobre margem" é `lucro_liquido_usdt / margem_utilizada_usdt * 100`
(quanto o lucro representa sobre o capital de fato comprometido na
posição). Os demais campos exibidos (lucro líquido, perda máxima,
quantidade, valor nominal, margem, retorno sobre patrimônio) foram
auditados e estão matematicamente corretos.

### 3. Informação redundante

Duas representações de penalização são exibidas em blocos diferentes,
computadas por sistemas paralelos distintos: Bloco 3 ("Convicção e
Expectativa") usa `signal.penalty_reasons` (lista de objetos `Penalty`);
Bloco 6 ("Análise") usa `signal.penalty_details` (lista de dicts de
`compute_coarse_penalty_details()`, mais detalhada — gate + peso perdido
+ motivo). Mostrar as duas é redundante e potencialmente inconsistente
entre si (podem discordar sobre quais penalizações se aplicam).

### 4. Sem validação final de consistência antes do envio

`SERVICES/telegram/telegram_validator.py` já valida campos obrigatórios
(`validate_signal_data`) e os 8 hard gates do Decision Engine
(`validate_consistency`) — mas nenhuma dessas funções valida a
CONSISTÊNCIA APRESENTACIONAL do sinal (preços em ordem coerente com a
direção, RR exibido batendo com os preços, tier batendo com o score).

## Arquivos Afetados

- `SERVICES/telegram/telegram_formatter.py` — remover exibição duplicada
  da classificação (Bloco 6 passa a reaproveitar a mesma variável do
  Bloco 2, não uma segunda fonte); remover exibição redundante de
  `penalty_reasons` no Bloco 3 (mantém só `penalty_details`, mais rico,
  no Bloco 6).
- `ENGINE/common/operational.py` — corrigir fórmula de `retorno_margem_pct`
  para usar `margem_utilizada_usdt` como denominador.
- `SERVICES/telegram/telegram_validator.py` — nova função
  `validate_presentation_consistency(data) -> Tuple[bool, str]`:
  valida ordem de preços (entry/stop/tp1 coerente com direção), RR
  exibido compatível com os preços reais (tolerância), e tier
  compatível com o overall_score (reaproveitando `_derive_tier()` já
  existente, sem duplicar a lógica).
- `SERVICES/telegram/telegram_service.py` — chama a nova validação em
  `_format_and_queue()`; se falhar, cancela o envio e registra o erro
  no log (mesmo padrão de `validate_signal_data`/`validate_consistency`
  já existentes).

## Impacto Esperado

- Uma única classificação exibida, sempre a mesma em qualquer lugar do
  card.
- "Retorno sobre margem" passa a refletir o retorno real sobre o
  capital comprometido, não mais uma reformulação do RR.
- Card mais enxuto (remove uma lista de penalização duplicada).
- Sinais com dados internamente inconsistentes (preços fora de ordem,
  RR não bate com os preços, tier não bate com o score) são bloqueados
  antes do envio, com log do motivo — nunca mais um card visivelmente
  contraditório chega ao usuário.

## Riscos

- Baixo: mudanças de apresentação + 1 fórmula de exibição + 1 gate novo
  de validação de dados já calculados. Nenhuma mudança em Decision
  Engine, Scanner, gates institucionais, ou cálculos de entrada/
  quantidade/posição reais (usados na execução).
- A nova validação de consistência pode, em teoria, bloquear sinais
  genuinamente aprovados se houver algum outro bug produzindo dados
  incoerentes — isso é o comportamento INTENCIONAL do item 4 da RFC
  (bloquear e logar em vez de exibir dado quebrado).

## Testes

- Testes para a fórmula corrigida de `retorno_margem_pct`.
- Testes para `validate_presentation_consistency()`: preços coerentes
  passam; preços invertidos (ex.: LONG com stop > entry) falham; RR
  incompatível com preços falha; tier incompatível com score falha.
- Testes para o formatter: classificação aparece uma única vez no card
  completo; penalização aparece uma única vez.
- Suite completa sem regressão.

## Critérios de Aceitação

- Nenhuma ocorrência de duas classificações diferentes no mesmo card.
- `retorno_margem_pct` matematicamente correto (validado por teste).
- Nenhuma duplicação de lista de penalização.
- Sinal com inconsistência de preços/RR/tier é bloqueado antes do envio,
  com log do motivo.
- Nenhuma mudança em Scanner/Decision Engine/Consensus/Confluence/Score/
  Quality Gate/filtros/cálculos de entrada (verificável: nenhum arquivo
  em `ENGINE/scanner/`, `ENGINE/decision/` é tocado).
- Suite completa sem regressão.

## Plano de Rollback

Mudanças isoladas em 3 arquivos de apresentação/validação. `git revert`
do(s) commit(s) desta RFC restaura o comportamento anterior.
