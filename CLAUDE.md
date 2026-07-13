# QuantOS V17 STABLE — Processo Oficial de Desenvolvimento

Toda alteração no QuantOS deve seguir obrigatoriamente este fluxo, sem pular etapas:

RFC → Implementação → Testes Unitários → Testes de Integração → Auditoria → Homologação → Paper Trading → Validação das Métricas → Documentação → Atualização da Baseline → Liberação

## Fase 1 — RFC
Antes de tocar em qualquer arquivo, produzir um RFC com: objetivo, motivação, arquivos afetados, impacto esperado, riscos, plano de implementação, plano de rollback, critérios de aceitação.

## Fase 2 — Implementação
Apenas o escopo definido na RFC. Código limpo, tipado, funções pequenas, responsabilidade única, sem duplicação, sem código morto, sem TODOs esquecidos, sem comentários desnecessários. Não alterar nada fora do escopo.

## Fase 3 — Testes Unitários
Cobrir fluxo principal, casos extremos, entradas inválidas, exceções. Nenhum teste pode falhar.

## Fase 4 — Testes de Integração
Validar o pipeline completo: Scanner → Decision → Risk → Validation → Signal Builder → Telegram → Analytics → Audit → Dashboard. Dados devem permanecer consistentes ponta a ponta.

## Fase 5 — Auditoria
Checar: código duplicado, imports desnecessários, conversões duplicadas, paths absolutos, except silencioso, variáveis mortas, warnings, performance, consistência dos scores.

## Fase 6 — Homologação
Checklist: sistema inicia; Scanner, Decision, Risk, Validation, Telegram, Dashboard, banco, logs, retry, health check funcionando; nenhuma exceção inesperada, traceback ou warning crítico.

## Fase 7 — Paper Trading
Monitorar entradas, stops, take profits, RR, consenso, conviction, scores, Telegram, logs. Comparar com a versão anterior e registrar diferenças.

## Fase 8 — Validação das Métricas
Relatório com Win Rate, Profit Factor, Drawdown, Expectancy, Sharpe, Sortino, Recovery Factor, tempo médio, uso de memória, latência, número de sinais e rejeições — comparado com a Baseline anterior, destacando melhorias e regressões.

## Fase 9 — Documentação
Atualizar obrigatoriamente: RFC.md, ARCHITECTURE.md, CHANGELOG.md, BASELINE.md, TEST_REPORT.md, HOMOLOGATION_REPORT.md. Nenhuma mudança sem documentação correspondente.

## Fase 10 — Liberação
Só liberar se TODOS forem verdadeiros: implementação concluída, testes unitários aprovados, testes de integração aprovados, auditoria aprovada, homologação aprovada, paper trading aprovado, sem regressões, documentação e CHANGELOG atualizados, baseline atualizada. Se qualquer item falhar, NÃO liberar.

## Relatório final obrigatório (toda tarefa)
Resumo executivo; objetivo da alteração; arquivos modificados/criados/removidos; problemas encontrados e corrigidos; testes executados, resultado e cobertura; auditoria; homologação; compatibilidade Windows/Linux/VPS; performance antes/depois; riscos remanescentes; estratégia de rollback; próxima fase recomendada.

## Restrições
- Não alterar a estratégia de trading sem RFC específica.
- Não modificar Hard Gates sem aprovação explícita.
- Não alterar pesos ou thresholds fora do escopo.
- Não criar implementações fictícias, não ocultar erros, não omitir problemas encontrados.
- Preservar compatibilidade com Windows, Linux e VPS.
- Manter retrocompatibilidade sempre que possível.
