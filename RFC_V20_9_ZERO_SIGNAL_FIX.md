# RFC V20.9 - Correção de Bug e Ajuste de Thresholds para Zero Sinais

## Objetivo
Restaurar a geração de sinais do QuantOS que está produzindo 0% de aprovação há 20+ ciclos consecutivos.

## Motivação
O QuantOS está escaneando 300 ativos por ciclo mas aprovando 0 (zero) sinais. Três problemas foram identificados:
1. Bug de atributo (`sd.rvol`/`sd.adx` inexistentes) gera 71+ exceções por ciclo e distorce o diagnóstico.
2. `HARD_MIN_RVOL = 0.70` bloqueia ~55% dos candidatos — a maioria dos altcoins opera com RVOL 0.15-0.50.
3. `CONSENSUS_MINIMUM_SCORE = 0.70` bloqueia 36.8% dos restantes.

## Arquivos afetados
- `main.py` (linhas 720, 722)
- `ENGINE/scanner/scanner_config.py` (HARD_MIN_RVOL, HARD_MIN_ADX, CONSENSUS_MINIMUM_SCORE)
- `TESTS/test_rfc_v20_9_zero_signal_fix.py` (novo)

## Impacto esperado
- Correção do bug: elimina 71+ AttributeError/ciclo; diagnóstico do funil volta a funcionar.
- RVOL 0.70 → 0.50: destrava ~30% mais candidatos para os gates seguintes.
- ADX 25 → 22: alinha com o piso histórico do DNA FLEX para mercados fracamente trendados.
- Consensus 0.70 → 0.55: valor médio entre o antigo (0.50) e o recalibrado (0.70); restaura fluxo sem abrir mão de qualidade.

## Riscos
- **Médio**: Redução de thresholds pode aumentar falsos positivos. Mitigação: os gates seguintes (Entry Zone, Quality, Confidence, Weighted Vote, Coherence) continuam ativos como barreiras de qualidade.
- **Baixo**: Bug fix não tem risco — `sig` está disponível no escopo e `sig.rvol`/`sig.adx` existem.

## Plano de implementação
1. Criar este RFC.
2. Corrigir `main.py:720,722`: `sd.rvol` → `sig.rvol`, `sd.adx` → `sig.adx`.
3. Ajustar `scanner_config.py`: `HARD_MIN_RVOL = 0.50`, `HARD_MIN_ADX = 22`, `CONSENSUS_MINIMUM_SCORE = 0.55`.
4. Executar testes unitários.
5. Executar testes de integração.
6. Auditoria.

## Plano de rollback
Reverter as alterações em `main.py` e `scanner_config.py`. Remover o teste.

## Critérios de aceitação
- Nenhum `AttributeError: 'SignalDecision' object has no attribute 'rvol'/'adx'` nos logs.
- Pelo menos 1 sinal aprovado por ciclo (vs. 0 atualmente).
- Diagnóstico do funil mostra categorias coerentes (sem "Outros" com 33%+).
- Testes unitários passam.
- Testes de integração passam.
