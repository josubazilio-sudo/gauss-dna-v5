# AGENTES — leia antes de mexer no K12

Duas sessões de Claude Code trabalham neste bot em paralelo, sem comunicação
direta entre si (uma no desktop, outra no celular). Isso já causou conflito
real: `SOFT_FILTERS_MODE` foi ligado e desligado por sessões diferentes sem
que a outra soubesse, o loop do `screen k12` foi trocado pra `sleep 5`
(martelando a exchange) e depois voltado, e o mesmo bug (`ultimo_sinal`)
recebeu dois patches diferentes em paralelo.

**Antes de mudar `.env`, reiniciar o processo, ou editar arquivos aqui:
atualize a seção "Estado atual" abaixo com data/hora e o que mudou.** Se
encontrar algo diferente do que este arquivo diz, é sinal de que a outra
sessão mexeu — não sobrescreva sem entender o porquê primeiro.

## Estado atual (última atualização: 2026-08-23 09:00 UTC, sessão desktop)

- Processo: `screen -r k12`, loop `python3 k11-signal-bot/runner.py; sleep 300`
  — iniciar/reiniciar sempre via `bash /root/gauss-dna-v5/start_k12.sh`
  (mata processo antigo e fecha screens k11/k12 antes de subir uma nova,
  evita duplicidade). Nunca `sleep 5` — martela a exchange e o disco.
- `.env`: `SOFT_FILTERS_MODE=false` (desligado a pedido explícito do usuário
  em 2026-08-22, depois de dados do Shadow Tracking mostrarem WR/PF ruins
  nos candidatos que esse modo deixaria passar — ver commit `9a66392`).
- `.env`: `V14_STRICT=false` — existe no `.env` mas **não é lido por nenhum
  .py em produção** hoje (só scripts de patch mortos). Inofensivo, mas se
  alguém for conectar isso a algo real, documentar aqui o que passa a fazer.
- `MODO_10_10=true`, `ENTRY_QUALITY_MIN=75`, `ENTRY_QUALITY_BLOCK=true` —
  inalterados desde sempre.
- Repositório git (`gauss-dna-v5`) está sincronizado local + GitHub + VPS
  no commit mais recente da branch master. Rodar `git status`/`git log -1`
  pra conferir antes de assumir que algo está desatualizado.
- Shadow Outcome Tracking (`shadow_tracker.py`) roda em paralelo, gravando
  em `shadow_candidates.jsonl` — não apaga nem reseta esse arquivo, é o
  histórico de validação que estamos acumulando.

## Se você é uma sessão de Claude lendo isto

Antes de reiniciar o bot, mudar `.env`, ou editar `k10_engine.py`/
`runner.py`/`trade_tracker.py`/`shadow_tracker.py`: rode `git status` e
`git log -3` no VPS pra ver se há mudança recente que você não fez. Se
achar algo inesperado, prefira perguntar ao usuário "encontrei X mudado,
foi você (ou a outra sessão) que fez isso?" em vez de reverter direto.

## Incidente 2026-08-23 ~09:00 UTC — revertido

A sessão do celular editou k10_engine.py direto no VPS (sem commit, sem
teste) tentando forçar mais sinais: reclassificou sinais de MACD short como
LONG ("MACD exausto"), removeu o timeframe 1h da análise, e adicionou
bloqueio de regime hardcoded. Isso tinha um bug real (NameError: 'ratio'
not defined) que derrubava silenciosamente a avaliação de qualquer símbolo
onde o MACD cruzasse pra baixo — confirmado ao vivo (HOME/USDT crashava).

**Revertido** pela sessão desktop (com autorização do usuário) de volta pro
último commit bom (8d4436c, que já tinha SOFT_FILTERS_MODE implementado
corretamente). O patch benigno de ultimo_sinal (usa now() como último
fallback) foi mantido e commitado (a15f098).

Se você é a sessão do celular: a ideia de reclassificar SHORT como uma
reversão LONG pode ter mérito, mas precisa entrar via SOFT_FILTERS_MODE (ou
uma flag nova) com teste old-vs-new antes de ir pra produção — não editando
o gate direto. Se tiver dúvida, pergunte ao usuário antes de editar
k10_engine.py sem commit.
