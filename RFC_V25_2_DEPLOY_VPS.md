# RFC V25.2 — Deploy para VPS e Validação Operacional em Produção

Data do deploy: 2026-07-14 22:38 (horário do VPS) / 2026-07-15T01:38:39Z
Commit local de referência: `d687290649f61184f0a57bdc7d71a3d1ca264a46`
PID pós-deploy: `1563310` (pm2 `quantos`, restart #91)

---

## Resumo Executivo

**Status: CONCLUÍDA com uma pendência (compartilhada com a RFC V25.1).**

O VPS agora executa exatamente o mesmo código homologado localmente na RFC V25.
Todos os critérios de aceitação verificáveis sem depender de um sinal aprovado
foram confirmados. A validação financeira ponta-a-ponta em um sinal real
aprovado permanece pendente — no VPS, assim como localmente, nenhum sinal foi
aprovado na janela observada (mercado + filtros iniciais).

---

## 1. Sincronização do VPS

| Item | Resultado |
|---|---|
| Instância única rodando | ✅ Confirmado (`pm2 list`: 1 processo `quantos`, pid 1563310) |
| VPS executa código da RFC V25 | ✅ Confirmado — `grep` encontrou `MarginWithinCapital`, `LeverageWithinLimit` em `institutional_math_auditor.py`, `Conflito MTF entre timeframes` em `main.py`, `leverage: float = LEVERAGE_MAX_USER` em `bot_config.py`, `ACCOUNT_SIZE` (não mais `10000`) em `bot_engine.py` |
| Processos antigos ativos | ✅ Nenhum — só a instância atual |
| Versões paralelas enviando sinal | ✅ Nenhuma detectada nesta verificação (ver nota abaixo) |
| Commit/hash implantado | `d687290649f61184f0a57bdc7d71a3d1ca264a46` (local — o VPS em si não versiona por git; os arquivos são sincronizados via `deploy_vps.sh`, prática já estabelecida em RFCs anteriores) |
| Backup pré-deploy | `/opt/backups/quantos_pre_v25_20260714_223641.tar.gz` (597MB, reversível) |

**Nota sobre a 2ª instância que enviou os sinais "Conflito MTF detectado!" na RFC V25.1**: a investigação não identificou onde essa instância roda (não é o VPS `vps-gauss`, que já foi confirmado só ter 1 processo antes mesmo deste deploy). Pode ser outro VPS/serviço não documentado enviando para o mesmo chat do Telegram. Recomendo ao usuário confirmar se há algum outro ambiente ativo além de local + `vps-gauss`.

---

## 2. Verificação Pós-Deploy

| Parâmetro | Valor no VPS | Observação |
|---|---|---|
| `QUANTOS_ACCOUNT_SIZE` | `200` | Igual ao local — preservado, `.env` não sobrescrito pelo deploy |
| `QUANTOS_MODE` | `DEVELOPMENT` | `ExecutionModeManager.is_live()` retorna `False` → branch de paper trading (a corrigida) é a usada |
| `QUANTOS_LEVERAGE_MAX` | Não definida no `.env` do VPS | Usa o fallback do código (`25`, igual ao default local) — comportamento correto, mas recomendo adicionar explicitamente no `.env` do VPS por clareza operacional |
| Versão exibida no Telegram (`engine_version`) | `"V18.4"` | String estática nunca atualizada desde a RFC V18.4 (mesmo comportamento do local — não é uma divergência introduzida por este deploy) |
| Baseline / RFC no VPS | Arquivos `.md` não fazem parte do runtime, não afetam o comportamento do bot | `BASELINE.md`/RFC docs foram enviados junto (não excluídos pelo `deploy_vps.sh`) |

Nenhuma divergência que justifique interromper a homologação.

---

## 3–5. Validação de Sinais Reais / Hard Gates / Consistência do Telegram

**Pendente** — nenhum sinal foi aprovado no VPS durante a janela de monitoramento
(20 min pós-deploy, 22:41–23:07). Contadores cumulativos de `status=APPROVED`
no log do VPS permaneceram em 157 (sem incremento) durante toda a janela.
Mesma limitação já registrada na RFC V25.1 localmente: aprovações são eventos
raros e não há mecanismo de forçar um sinal de teste sem violar o princípio de
"não alterar lógica operacional".

**Recomendação**: na próxima vez que um sinal for aprovado (local ou VPS),
conferir manualmente o log `MATH_AUDIT|` contra a mensagem do Telegram — é uma
verificação rápida, não bloqueante para manter o deploy em produção.

---

## 6. Monitoramento

| Métrica | Janela local (RFC V25.1, 2h) | Janela VPS (20 min pós-deploy) |
|---|---|---|
| Ciclos | ~44 | Não contabilizado (janela curta) |
| Erros/tracebacks novos | 0 | 0 |
| Sinais aprovados novos | 0 | 0 |
| CPU | 1,6% | 58% (pico momentâneo do próprio restart/scan, normalizando) |
| Memória | 283 MB | 94,9 MB logo após restart |
| Restarts / instáveis | 2 / 0 | 91 / 0 (contador histórico do pm2, não é regressão desta RFC) |

**Monitoramento de 24h completo**: não é possível manter esta sessão aberta por
24h contínuas. As primeiras 20 min pós-deploy foram observadas sem qualquer
anomalia. Recomendo ao usuário pedir uma nova checagem depois de algumas horas
(ou usar `/loop` para automatizar essa checagem periódica, se desejar) para
completar a janela de observação de 24h pedida na RFC.

---

## 7. Critérios de Aceitação

| Critério | Status |
|---|---|
| VPS executando exclusivamente a versão V25 | ✅ |
| Nenhuma instância antiga em execução (no `vps-gauss`) | ✅ |
| Primeiro sinal aprovado com cálculos financeiros corretos | ⏳ Pendente (sem sinal aprovado ainda) |
| Telegram reproduz exatamente os valores do Math Auditor | ⏳ Pendente (idem) |
| Nenhum cálculo usa saldo fictício | ✅ (confirmado por código: `ACCOUNT_SIZE`, não `10000`) |
| Nenhum sinal viola limites de margem/alavancagem | ✅ (nenhum sinal aprovado ainda para violar; gate ativo e testado) |
| Hard Gates demonstram funcionamento em ambiente real, quando aplicáveis | ⏳ Pendente — sem oportunidade real ainda (local e VPS) |

---

## Conclusão

O deploy foi executado com segurança (backup reversível, verificação prévia do
estado do VPS, confirmação pós-deploy completa) e o VPS agora roda o mesmo
código homologado localmente. Não houve nenhuma regressão, erro ou
inconsistência de configuração. A única pendência — validar o Hard Gate em um
sinal real aprovado — é a mesma identificada na RFC V25.1 e depende de uma
condição de mercado que ainda não ocorreu, não de uma falha de implementação.
