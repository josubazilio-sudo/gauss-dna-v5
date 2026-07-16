# RFC V25.4 — Correção do Bug de Escala no Filtro de Exaustão

Data: 2026-07-14/15

## Contexto

O usuário reportou que o bot não estava encontrando praticamente nenhum sinal
de compra/venda entre centenas de criptomoedas escaneadas, e perguntou se
era o mercado ou algo bloqueando indevidamente. Investigação (sem alterar
nada) mostrou que **71,7% de todas as rejeições** vinham do filtro de
"Exaustão", e que o fator `velas_alongadas_consecutivas` (+15 pontos, o maior
peso do filtro) estava presente em **100% (2151/2151)** dos bloqueios por
exaustão na amostra analisada.

## Causa Raiz

`ENGINE/scanner/flex_scoring.py::compute_exaustao()`, item 4 ("velas
alongadas consecutivas"):

```python
c_range = (highs[i] - lows[i]) / current_price * 100   # em PORCENTUAL (ex. 0.42)
if c_range > atr_percent * 2.5:                          # atr_percent em FRACAO (ex. 0.0057)
```

`c_range` era calculado em escala percentual (0-100), mas comparado contra
`atr_percent` em escala fracionária (0-1) sem nenhuma conversão — um erro de
escala de ~100x. Na prática, o threshold ficava ~100x menor que o
pretendido, fazendo qualquer vela (por menor que fosse) disparar esse fator.

**Confirmado com dados reais** (BTCUSDT 1h, ao vivo): ATR% real = 0,57%;
threshold correto seria ~1,43% (2,5× o ATR); threshold usado pelo bug era
0,0143 — ou seja, **qualquer vela acima de 0,0143% de range disparava**,
incluindo velas de 0,31%–0,43% (completamente normais, muito abaixo do
threshold correto de 1,43%).

## Correção

```python
c_range = (highs[i] - lows[i]) / current_price   # agora em FRACAO, mesma escala de atr_percent
if c_range > atr_percent * 2.5:                    # comparacao correta
```

Único ponto alterado. Nenhum outro filtro, threshold, peso ou regra de
trading foi tocado.

## Resultado Real (antes × depois, mesmo ambiente, mesmo dia)

| Métrica | Antes do fix | Depois do fix |
|---|---|---|
| Exaustão como % de todas as rejeições | 71,7% (2151/3000 amostra) | **19,7%** (77/391 amostra pós-restart) |
| `velas_alongadas_consecutivas` dentro dos bloqueios por Exaustão | 100% (2151/2151) | **76,6%** (59/77) — agora reflete velas genuinamente grandes, não dispara universalmente |
| Consenso multi-TF como % de todas as rejeições | 28,3% | 80,3% (esperado — mais candidatos agora avançam até essa etapa em vez de morrer antes) |

O funil deixou de matar quase tudo já na primeira barreira (Exaustão) e passou
a filtrar de fato nas etapas seguintes (Consenso, RVOL, Entry Zone, etc.),
como projetado.

## Testes

4 testes novos (`TESTS/test_rfc_v25_4_fix_escala_exaustao.py`):
- Velas normais (escala real de mercado) não disparam mais falsamente.
- Velas genuinamente grandes (>2,5× ATR real) continuam disparando —
  o fix não elimina detecções legítimas de exaustão.
- Documentação do comportamento antigo (bugado) para referência futura.
- Sinal em condições normais de mercado não é mais bloqueado só por causa
  do bug.

Suite completa: **500/500 passando**, zero regressão.

## Deploy

- Local: `pm2 restart quantos` — confirmado sem erros, estatísticas
  coletadas em produção real (paper trading) confirmam o efeito esperado.
- VPS: `./deploy_vps.sh` — instância única confirmada, zero tracebacks
  pós-deploy.

## Observação

Este bug provavelmente existia desde a introdução do filtro de exaustão
(portado do projeto `gauss-dna-v5`, conforme comentário original no código)
e nunca foi pego porque não havia teste unitário cobrindo `compute_exaustao`
com valores realistas de `atr_percent` — os únicos testes indiretos usavam
dados sintéticos que não expunham o descompasso de escala. Recomendação
(não implementada nesta RFC, fora de escopo): revisar os demais filtros do
scanner em busca do mesmo padrão de erro (comparação direta entre valores em
% e em fração), já que esse é um erro fácil de repetir.
