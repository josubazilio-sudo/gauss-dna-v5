# Relatório Final — RFC V19.2: Estabilidade do AuditEngine

Data: 2026-07-12

## Resumo Executivo

O processo `quantos` caiu silenciosamente (sem traceback, sem log de
shutdown) às 13:16 de 2026-07-12 e ficou ~2 horas parado, interrompendo
totalmente o fluxo de sinais. Investigação identificou como causa mais
provável um vazamento de recursos em `audit_engine.py`: uma thread do SO era
criada a cada sinal rejeitado (~34.000 threads em poucas horas), cada uma
reescrevendo o arquivo `blockers.json` inteiro. Corrigido via RFC V19.2:
fila + worker único, append-only (JSON Lines), rotação por tamanho.
Nenhuma regra de negócio (gates, thresholds, scoring, Telegram) foi alterada.

## Objetivo da Alteração

Eliminar a causa raiz da queda silenciosa do processo, sem tocar em nenhuma
lógica de decisão de sinais.

## Arquivos Modificados

- `audit_engine.py` — reescrito: fila interna + worker único, append O(1) em
  JSON Lines, rotação por tamanho com nomes únicos (microssegundos + sufixo).
- `main.py` — 2 linhas alteradas (523, 586): chamada direta a
  `audit.log_blocker(...)` em vez de `threading.Thread(...).start()`. Import
  morto de `threading` removido.
- `TESTS/test_audit_engine_estabilidade.py` — novo arquivo, 7 testes.
- `CHANGELOG.md` — entrada [19.2.0] adicionada.
- `RFC_V19_2_ESTABILIDADE_AUDIT_ENGINE.md` — RFC formal (já existente,
  aprovada antes da implementação).

Nenhum outro arquivo foi tocado. Nenhuma mudança em gates, thresholds,
scoring, formatação de Telegram ou lógica de risco.

## Problemas Encontrados e Corrigidos

1. **Thread por evento sem limite**: `main.py` disparava
   `threading.Thread(target=audit.log_blocker, ...).start()` para cada sinal
   rejeitado. Em um scan de ~300 pares × múltiplos timeframes, isso gera
   dezenas de milhares de threads por hora, sem pool, sem join, sem cap.
   **Corrigido**: chamada direta e síncrona; a operação em si passou a ser
   barata (append O(1)), então não há necessidade de thread nem de fila
   externa visível ao chamador (a fila interna do `AuditEngine` já desacopla
   a escrita em disco do fluxo principal, com apenas 1 thread total).
2. **Reescrita completa de arquivo por chamada**: `_safe_write` lia
   `blockers.json` inteiro, fazia append em memória, e reescrevia o arquivo
   inteiro — O(n) por chamada, com `n` crescendo a cada chamada.
   **Corrigido**: append-only em JSON Lines, O(1) por chamada.
3. **Sem rotação/limite de tamanho**: arquivos de auditoria cresciam
   indefinidamente. **Corrigido**: rotação automática por tamanho
   configurável (default 5 MB).
4. **Bug descoberto durante os testes**: a primeira versão da rotação usava
   timestamp com granularidade de segundo (`%Y%m%d_%H%M%S`), causando
   `WinError 183` (arquivo de destino já existe) quando duas rotações
   ocorriam no mesmo segundo — o que faria a rotação falhar silenciosamente
   e o arquivo voltar a crescer sem limite, reproduzindo o problema original.
   **Corrigido antes da homologação**: timestamp com microssegundos + sufixo
   incremental de desempate.
5. **Import morto**: `threading` em `main.py` ficou sem uso após a remoção
   das duas chamadas — removido.

## Testes Executados

- `TESTS/test_audit_engine_estabilidade.py` (novo, 7 testes):
  - sem criação de thread por chamada;
  - append em formato JSON Lines;
  - append é O(1) (nunca reescreve o arquivo inteiro);
  - rotação ocorre ao exceder o tamanho configurado;
  - falha de escrita é silenciosa e não propaga exceção (fail-safe mantido);
  - `log_cycle`/`log_trade` também usam append-only;
  - `main.py` não volta a usar `threading.Thread` por evento.
- Suite completa: `python -m pytest TESTS/ -v` → **49 passed** (42 preexistentes
  + 7 novos), 0 falhas, 0 regressões.
- Cobertura: unitária, focada no módulo alterado. Não há teste de integração
  ponta-a-ponta específico para logging de auditoria (fora do pipeline
  Scanner → Decision → Risk → Telegram, que não foi tocado).

## Auditoria

- Nenhum código duplicado introduzido.
- Nenhum import desnecessário (import morto de `threading` removido).
- Nenhum path absoluto novo.
- Nenhum `except` silencioso novo além do já existente por design
  ("Fail-Safe: Se o AuditEngine falhar, o Scanner continua"), preservado
  intencionalmente e coberto por teste.
- Nenhuma variável morta.
- Verificado (grep) que nenhum outro módulo lia `blockers.json`/`trades.json`
  no formato array antigo antes de migrar para `.jsonl`.

## Homologação

- Sintaxe (`ast.parse`) e import (`importlib.import_module`) OK para
  `audit_engine.py` e `main.py`.
- Processo `quantos` reiniciado localmente via pm2
  (`QUANTOS_MODE=DEVELOPMENT`).
- Observado por ~16 minutos / 9 ciclos de scan completos (300 pares cada):
  - `restarts`: 1 (o reinício intencional), `unstable restarts`: 0.
  - Contagem de threads do processo filho Python: estável (6-7 threads,
    sem crescimento).
  - Memória (`WorkingSet64`): estabilizou em ~172 MB após warm-up inicial
    (não cresceu entre duas leituras consecutivas).
  - `MEMORY/audit/blockers.jsonl` crescendo normalmente via append;
    `MEMORY/audit/blockers.json` (formato antigo) parado desde o restart,
    confirmando que o código novo está ativo em produção.
  - Nenhum `Traceback`/`CRITICAL` nos logs pós-restart.

## Compatibilidade Windows/Linux/VPS

- Mudança usa apenas `os`, `queue`, `threading`, `json`, `datetime` da
  stdlib — compatível com Windows, Linux e a VPS Ubuntu.
- Bug de rotação (`WinError 183`) era específico de Windows; a correção
  (timestamp com microssegundos + sufixo) é multiplataforma e não depende
  de comportamento específico de SO.

## Performance Antes/Depois

- Antes: 1 thread OS + reescrita completa de arquivo por sinal rejeitado
  (custo crescente conforme o arquivo cresce).
- Depois: 0 threads novas por evento; 1 thread worker fixa; escrita O(1)
  por evento (append de uma linha).
- Efeito colateral observado (não é o objetivo do RFC, mas notável): ciclos
  de scan pós-restart completaram em ~43s (vs. ~382s antes da queda),
  provavelmente por cache/estado da API MEXC mais quente, não atribuível
  diretamente a esta mudança — não incluído como métrica de sucesso do RFC.

## Riscos Remanescentes

- Baixo. A migração de formato (`.json` array → `.jsonl`) foi verificada
  como segura (nenhum outro código lia esses arquivos), mas se alguma
  ferramenta externa de análise manual dependia do formato antigo, precisará
  ser ajustada para ler JSON Lines.
- Observação de homologação foi de ~16 minutos, não as 2h recomendadas na
  RFC original. Recomenda-se monitoramento contínuo nas próximas horas via
  `pm2 describe quantos` (campo `unstable restarts` e `uptime`).
- O bug de disco/memória em `MEMORY/audit/` (841 arquivos `pipeline_*.json`,
  88 MB, gerados por outro módulo de diagnóstico) **não foi tratado neste
  RFC** — está fora do escopo (`audit_engine.py` + 2 linhas de `main.py`).
  Se a máquina continuar com RAM crítica (~90% de uso constante observado),
  recomenda-se um RFC futuro para tratar esse módulo também.

## Estratégia de Rollback

- Mudança isolada e pequena: `git revert` do commit desta RFC restaura o
  `audit_engine.py` anterior e as 2 linhas de `main.py` com
  `threading.Thread`. Nenhuma migração destrutiva — o `blockers.json`
  antigo não foi apagado nem sobrescrito pelo novo código (que passou a
  escrever em `blockers.jsonl`).

## Próxima Fase Recomendada

- Continuar monitorando o processo `quantos` (local e após deploy no VPS)
  por um período mais longo para confirmar ausência de crashes recorrentes.
- Avaliar, em RFC futura, se o módulo de diagnóstico que gera os 841
  arquivos `pipeline_*.json` em `MEMORY/audit/` também precisa de rotação,
  dado o quadro geral de RAM/disco limitados da máquina local.
