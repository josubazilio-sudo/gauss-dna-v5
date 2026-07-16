# RFC V24 — QUANTOS ANALYTICS & REJECTION INTELLIGENCE

## Objetivo
Implementar o módulo de Inteligência Operacional `RejectionAnalytics` para rastrear, registrar e analisar todas as decisões do QuantOS (aprovadas e rejeitadas).

## Motivação
A necessidade de entender POR QUE cada sinal é aprovado ou reprovado, utilizando evidências estatísticas em vez de tentativas e erro para calibração de thresholds.

## Arquivos Afetados
- `ENGINE/analytics/rejection_analytics.py` (Novo)
- `ENGINE/scanner/scanner_config.py` (Modificado)
- `main.py` (Modificado para hooks de telemetria)
- `TESTS/test_rfc_v24_rejection_analytics.py` (Novo)

## Impacto Esperado
- 100% de rastreabilidade das decisões.
- Capacidade de simular impactos de mudanças de threshold.
- Recomendações automáticas baseadas em dados.
- Foco em melhorias operacionais com evidências.

## Plano de Implementação
1. Criar o módulo `RejectionAnalytics` com capacidade de registro, resumo, análise e exportação.
2. Integrar hooks em todos os pontos de decisão (Scanner, DecisionEngine, Final Validation).
3. Configurar via `scanner_config.py`.
4. Validar com testes unitários (>95% de cobertura).

## Rollback
Desativar via `.env` (`QUANTOS_ENABLE_REJECTION_ANALYTICS=false`).

## Critérios de Aceitação
- 100% das decisões rastreadas.
- Todo sinal possui motivo de aprovação ou reprovação.
- Simulações de thresholds funcionando.
- Exportação automática em `analytics/`.
- Compatibilidade com todas as RFCs anteriores.
