# RFC V19.2 — Estabilidade do AuditEngine (Correção de Vazamento de Threads/IO)

Data: 2026-07-12

## Objetivo

Eliminar a causa raiz da queda silenciosa do processo `quantos` (parado das
13:16 às 15:13 de 2026-07-12, sem traceback, sem log de shutdown) causada por
um padrão de logging não controlado em `audit_engine.py`.

## Motivação

O processo `quantos` (pm2) morreu sem deixar rastro de erro no log. Investigação:

- A máquina opera com apenas ~4 GB de RAM totais, compartilhados entre `quantos`,
  `gauss-dna-v5`, VSCode e Claude Code. `pm2 list` mostrou uso de RAM
  consistentemente em 88-90% mesmo com poucos processos ativos.
- `main.py:523` e `main.py:586` disparam, **para cada sinal rejeitado**:
  ```python
  threading.Thread(target=audit.log_blocker, args=(...), daemon=True).start()
  ```
  Em uma janela de poucas horas o log registrou **~34.000 sinais processados**
  (a maioria rejeitados), ou seja, ~34.000 threads OS criadas sem pool, sem
  limite, sem join — cada uma com overhead de stack (padrão ~1 MB/thread no
  Windows).
- Cada thread executa `AuditEngine._safe_write()`, que para arquivos `.json`
  **lê o arquivo inteiro, faz append em memória, e reescreve o arquivo inteiro**
  (`MEMORY/audit/blockers.json`, hoje 123 KB e crescendo sem rotação). É um
  padrão O(n) por chamada, chamado em altíssima frequência.
- `MEMORY/audit/` acumulou 841 arquivos `pipeline_*.json` (88 MB) sem rotação
  ou limpeza — mesma classe de problema (escrita irrestrita em disco por ciclo).
- Conclusão: alta frequência de criação de threads + reescrita completa de
  arquivos crescentes é o candidato mais forte para exaustão de memória e
  queda silenciosa do processo (Windows não gera traceback Python quando o
  processo é finalizado por pressão de memória do SO).

## Arquivos Afetados

- `audit_engine.py` (raiz do projeto) — único arquivo com a lógica de
  `_safe_write`, `log_blocker`, `log_cycle`, `log_trade`.
- `main.py` — pontos de chamada (linhas 523 e 586) que disparam
  `threading.Thread(...).start()` por sinal rejeitado.

Nenhum outro arquivo (scanner, decision engine, telegram, risk) será tocado.
Este RFC é estritamente sobre estabilidade de logging/auditoria, não sobre
estratégia de sinais.

## Impacto Esperado

- Eliminar a criação descontrolada de threads por sinal rejeitado.
- Eliminar o padrão "ler arquivo inteiro + reescrever arquivo inteiro" por
  chamada, substituindo por append linha-a-linha (JSON Lines) com rotação por
  tamanho/data.
- Reduzir uso de memória e I/O de disco por ciclo de scan, sem alterar
  nenhuma regra de negócio (gates, thresholds, scoring, Telegram).
- Resultado esperado: processo `quantos` permanece estável por períodos
  longos (>24h) sob a mesma carga de ~300 pares/ciclo.

## Riscos

- Baixo: mudança isolada em um módulo de auditoria/log, sem relação com o
  pipeline de decisão de sinais. Risco de regressão limitado a: perda de
  algum registro de auditoria durante a transição de formato (mitigado por
  manter compatibilidade de leitura ou migrar o arquivo existente).
- Risco de concorrência: `_safe_write` já usa `threading.Lock()`; a nova
  versão deve manter proteção equivalente (ou usar uma fila single-writer)
  para evitar corrupção de arquivo com escrita concorrente.

## Plano de Implementação

1. Remover `threading.Thread(...).start()` nas duas chamadas de
   `main.py` (523, 586); chamar `audit.log_blocker(...)` diretamente
   (operação já será barata o suficiente após a correção abaixo) — ou,
   alternativamente, usar uma fila (`queue.Queue`) consumida por **uma única**
   thread de background (worker), evitando qualquer criação de thread por
   evento.
2. Reescrever `AuditEngine._safe_write` para arquivos `.json` recorrentes
   (`blockers.json`, `cycle_*.json`, `trades.json`) usando **append-only em
   formato JSON Lines** (uma linha JSON por evento), eliminando o ciclo
   leitura-completa + reescrita-completa.
3. Adicionar rotação simples por tamanho (ex: novo arquivo quando o atual
   passar de N MB) para `blockers.json` e para os `pipeline_*.json` gerados
   em outro ponto do código (fora do escopo deste RFC se não for o mesmo
   módulo — validar antes de tocar).
4. Manter as assinaturas públicas (`log_cycle`, `log_blocker`, `log_trade`)
   inalteradas para não exigir mudanças em outros chamadores.

## Plano de Rollback

- Mudança isolada em `audit_engine.py` + 2 linhas em `main.py`. Rollback via
  `git revert` do commit específico, ou restauração direta dos arquivos
  antigos (mantidos em diff). Nenhuma migração destrutiva de dados: o
  `blockers.json` antigo (formato lista JSON) será preservado/renomeado, não
  sobrescrito, no primeiro write pós-migração.

## Critérios de Aceitação

- Nenhuma thread nova criada por sinal rejeitado (validar via contagem de
  threads ativas do processo antes/depois, ex: `threading.active_count()`
  logado periodicamente).
- `blockers.json` e equivalentes passam a crescer de forma limitada
  (append O(1) por evento, não O(n)).
- Suite de testes completa (`pytest TESTS/ -v`) permanece 100% passando,
  sem nenhuma mudança em gates/thresholds/scoring.
- Processo `quantos` roda em produção local por período estendido (meta:
  observação mínima de 2h contínuas pós-fix) sem queda silenciosa, com uso
  de memória do processo estável (não crescente) entre ciclos.
- Nenhum arquivo fora do escopo listado é modificado.
