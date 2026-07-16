# RFC V25.1 — Homologação Pós-Deploy do Hard Gate Financeiro

Data: 2026-07-14
Janela observada: 20:27 → 22:29 (local), ~2h02min, 44 ciclos completos
Ambiente: Paper Trading local (pm2 `quantos`, pid 7208), dados reais MEXC

---

## Resumo Executivo

**Status da homologação: PARCIAL — aprovado no que foi possível observar, com 1 pendência.**

- Deploy local limpo: processo reiniciado com o código da RFC V25, zero erros/tracebacks em ~2h de execução contínua (44 ciclos).
- **Achado crítico não relacionado a bug de código**: os 2 sinais com "Conflito MTF" recebidos pelo usuário durante a homologação vieram de **uma instância diferente e desatualizada** (provável VPS), não do processo local corrigido — ver seção "Achado Crítico" abaixo.
- **Pendência real**: nenhum sinal foi aprovado localmente na janela observada (mercado + filtros iniciais rejeitaram 100% dos candidatos antes de chegar aos Hard Gates novos). Por isso, os gates `MarginWithinCapital`, `LeverageWithinLimit` e `MTF_CONFLICT` não tiveram nenhuma oportunidade de disparar (ou deixar passar) um sinal real de ponta a ponta nesta janela.
- **Recomendação**: a robustez do Hard Gate está validada por 15 testes automatizados determinísticos (incluindo um caso reproduzindo exatamente o sintoma BULLSUSDT) e por inspeção de código confirmando a integração correta. A validação em sinal real aprovado fica como monitoramento contínuo recomendado (não bloqueante para produção local), dado que aprovações são eventos raros e imprevisíveis no tempo.

---

## Achado Crítico: Instância Desatualizada Enviando Sinais

Durante a homologação, o usuário recebeu 2 mensagens do Telegram com "⛔ Conflito MTF detectado!" sem bloqueio. Investigação confirmou que **não vieram do processo homologado**:

| Evidência | Processo local homologado | Sinais recebidos |
|---|---|---|
| Ciclo | #10–#44 (2h de uptime) | #435 e #290 |
| Texto de conflito MTF | "⛔ Conflito Direcional entre Timeframes detectado!" (`telegram_formatter.py:274`, não alterado nesta RFC) | "⛔ Conflito MTF detectado!" (string que não existe em nenhum arquivo do repositório local) |

Cálculo de ciclos: o processo local levaria muito mais que 2h para chegar aos ciclos #290/#435 no ritmo observado (~2,7 min/ciclo). Isso, somado ao texto divergente (nunca editado por esta RFC), confirma uma segunda instância rodando código anterior à RFC V25 — muito provavelmente o VPS, que ainda não recebeu o deploy. **Não é uma falha do Hard Gate V25** — é a confirmação de que o VPS precisa da propagação (fora do escopo desta homologação, conforme combinado com o usuário).

---

## Estatísticas (janela de ~2h, 44 ciclos)

| Métrica | Valor |
|---|---|
| Ciclos completos | ~44 |
| Sinais/candidatos rejeitados (registrados em `blockers.jsonl`) | 5.285 |
| Rejeitados por Exaustão | 3.640 |
| Rejeitados por Consenso multi-TF insuficiente | 1.645 |
| Rejeitados por RVOL / Entry Zone / BOS-CHoCH / Descalibração | 0 (nenhum candidato chegou a essas etapas nesta janela) |
| Bloqueados por `MarginWithinCapital` (V25) | 0 (nenhuma oportunidade) |
| Bloqueados por `LeverageWithinLimit` (V25) | 0 (nenhuma oportunidade) |
| Bloqueados por `MTF_CONFLICT` (V25) | 0 (nenhuma oportunidade) |
| Sinais aprovados / enviados ao Telegram | 0 |
| Percentual de aprovação | 0% (sobre 5.285 candidatos analisados nesta janela) |
| Tracebacks / erros críticos | 0 |

**Distribuição por categoria**: 100% das rejeições nesta janela específica ocorreram nas duas primeiras etapas do funil (Exaustão e Consenso multi-TF), antes de qualquer sinal alcançar o Decision Engine / Hard Gates finais. Isso é consistente com o comportamento histórico do sistema (aprovações são raras — no log de hoje, chegaram a passar mais de 1h sem nenhuma aprovação mesmo antes desta RFC).

---

## Conflito MTF — Item 6 (dado real vs. limitação conhecida)

- Sinais bloqueados pelo gate `MTF_CONFLICT` nesta janela: **0**.
- Quantos teriam sido vencedores/perdedores caso aceitos, taxa de acerto: **não mensurável hoje**. O QuantOS não possui nenhum mecanismo de *shadow tracking* que acompanhe o preço após a rejeição de um sinal — só o resultado de sinais efetivamente aprovados é registrado (Paper Trading). Reportar essa métrica agora exigiria inventar dados, o que a própria RFC V25.1 proíbe explicitamente ("não criar implementações fictícias").
- **Não há evidência, nesta janela, de que o gate esteja excessivamente restritivo** — porque ele simplesmente não teve nenhuma chance de agir. Nenhum ajuste de limite é justificável com os dados atuais (consistente com o princípio "nenhum limite deverá ser alterado sem base estatística").
- **Oportunidade identificada (fora de escopo, não implementada)**: uma futura RFC poderia adicionar rastreamento de sinais rejeitados (preço em T+N candles) para permitir essa análise de win-rate contrafactual. Registro apenas como sugestão — nenhum código foi alterado.

---

## Auditoria Financeira

Confirmações possíveis nesta janela (via inspeção de código + testes, já que não houve sinal aprovado real):

- [x] Nenhum cálculo usa saldo fantasma: `BotEngine._update_balance()` usa `ACCOUNT_SIZE` (200.0, confirmado lido do `.env` real) em paper trading.
- [x] `BotConfig().leverage` confirmado igual a `LEVERAGE_MAX_USER` (25.0, do `.env` real).
- [x] Math Auditor bloqueia margem acima do capital e alavancagem acima do máximo — confirmado por 6 testes determinísticos, incluindo reprodução exata do sintoma BULLSUSDT (`test_bullsusdt_style_oversized_signal_blocks`, `test_bullsusdt_symptom_now_blocked_with_real_env_limits`).
- [ ] **Pendente**: confirmar em um sinal real aprovado que os valores exibidos no Telegram (nominal, margem, lucro, perda) batem com os recalculados pelo Math Auditor. Não observável nesta janela por falta de aprovação real.

Nenhuma operação ultrapassou capital ou alavancagem nesta janela — porque nenhuma operação foi aprovada.

---

## Performance

| Métrica | Valor |
|---|---|
| Uptime da homologação | ~2h (restart 20:27, pid 7208) |
| Restarts / unstable restarts | 2 / 0 (1 restart inicial do pm2 + 1 restart desta homologação) |
| CPU (snapshot) | 1,6% |
| Memória (snapshot) | 283,3 MB |
| Tempo médio de ciclo | ~2,7 min (44 ciclos em ~2h) |
| Gargalos observados | Nenhum |

---

## Conclusão

- **A RFC V25 está operacionalmente estável?** Sim — 2h contínuas, 44 ciclos, zero erros/tracebacks, uso de CPU/memória estável.
- **Está pronta para produção (local)?** Sim, com a ressalva de que o Hard Gate financeiro/estrutural novo ainda não foi exercitado por um sinal real aprovado nesta janela — validado até aqui por testes automatizados e inspeção de código, não por observação direta em produção.
- **Existe alguma regressão?** Não. Suite completa (492/492) sem regressão; nenhuma mudança de comportamento fora do escopo da RFC V25 foi observada nos logs.
- **Existe alguma inconsistência remanescente?** Uma, fora do escopo desta RFC: o VPS ainda roda código anterior à RFC V25 (confirmado pelo achado crítico acima) — é a causa real dos 2 sinais com conflito MTF não bloqueado que o usuário recebeu.
- **Existe oportunidade de simplificação?** Não identificada nesta fase — a arquitetura permaneceu igual ou mais simples que antes (nenhum módulo novo, apenas extensão dos gates existentes).

## Recomendação

1. Continuar monitorando o processo local (sem ação necessária — já está em produção paper trading).
2. Quando o usuário autorizar, propagar a RFC V25 para o VPS (pendência já identificada, fora do escopo desta homologação).
3. Assim que um sinal real for aprovado localmente, revisar o log do Math Auditor (`MATH_AUDIT|` no log) para confirmar visualmente que os valores batem com o Telegram — item de baixo esforço, recomendado na próxima verificação de rotina.
