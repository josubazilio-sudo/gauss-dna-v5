# Homologation Report - QuantOS V17.1

Data: 2026-07-11

## Resultado
Homologacao parcial aprovada para a mudanca de aprovacao controlada.

## Evidencia Principal
- Validacao com dados reais MEXC retornou 1 sinal aprovado: `67USDT 4h short`.
- Hard gates aprovados: `True`.
- Self-audit aprovado: `True`.
- Estado do DecisionBrain: `PRONTO`.

## Rejeicoes Mantidas
- `OBSERVACAO` continua rejeitado.
- Sinais com RVOL abaixo do minimo continuam rejeitados.
- Sinais com consenso abaixo de `0.60` continuam rejeitados.
- Sinais com exaustao continuam bloqueados antes do DecisionEngine.

## Pendencias
- Rodar 20+ ciclos consecutivos em producao.
- Executar paper trading para medir win rate, profit factor, drawdown e expectancy.
- Comparar metricas contra baseline apos trades fechados.

## RFC V25 (2026-07-14) — Hard Gate Financeiro

### Resultado
Homologacao local aprovada para a correcao de causa raiz do Hard Gate Financeiro.

### Evidencia Principal
- Suite completa: 492/492 testes passando, zero regressao.
- `import main` sem erros.
- Saldo de paper trading (`BotEngine._update_balance`) confirmado usando
  `ACCOUNT_SIZE` (200.0) em vez do saldo fantasma anterior (10000.0).
- `BotConfig().leverage` confirmado igual a `LEVERAGE_MAX_USER` (25.0).
- Math Auditor bloqueia (via teste automatizado) um sinal reproduzindo o
  sintoma reportado (BULLSUSDT): quantidade dimensionada contra saldo de
  10.000 USDT, capital real de 200 USDT — `MarginWithinCapital` falha e
  `hard_fail_reason` explica o motivo.
- Conflito MTF isolado confirmado como bloqueante (gate padrao, sem exigir
  `structural_score < 0.60` combinado).

### Pendencias
- Propagar para o VPS (`deploy_vps.sh`) e observar ciclos reais para confirmar
  (ver RFC V25.1 abaixo — VPS confirmado rodando codigo anterior a V25).

## RFC V25.1 (2026-07-14) — Homologacao Pos-Deploy (Paper Trading Real)

### Resultado
Homologacao PARCIAL. Ver `RFC_V25_1_HOMOLOGACAO_POS_DEPLOY.md` para o relatorio
completo.

### Resumo
- 2h / 44 ciclos locais, zero erros, zero regressao.
- Nenhum sinal aprovado na janela observada (0/5285 candidatos passaram dos
  filtros iniciais) - os Hard Gates novos (`MarginWithinCapital`,
  `LeverageWithinLimit`, `MTF_CONFLICT`) nao tiveram nenhuma oportunidade de
  disparar em um sinal real nesta janela. Validado apenas via testes
  automatizados e inspecao de codigo.
- Achado critico: 2 sinais com conflito MTF nao bloqueado recebidos pelo
  usuario vieram de uma instancia diferente (provavel VPS), rodando codigo
  anterior a RFC V25 - confirmado por numero de ciclo (#290/#435, impossivel
  para o processo local recem-reiniciado) e por texto de conflito MTF
  diferente do usado no codigo local atual. Nao e uma falha do Hard Gate V25.

### Pendencias remanescentes
- Assim que um sinal real for aprovado (local ou VPS), confirmar visualmente no
  log do Math Auditor que os valores batem com o Telegram.
- Monitorar se o novo Hard Gate nao esta bloqueando sinais legitimos em excesso
  (revisar `BLOCKED_SIGNALS.log`, gate `MTF_CONFLICT`, apos alguns ciclos).

## RFC V25.2 (2026-07-14) — Deploy para VPS

### Resultado
Deploy concluido com sucesso. Ver `RFC_V25_2_DEPLOY_VPS.md` para o relatorio
completo.

### Resumo
- Backup reversivel criado antes do deploy
  (`/opt/backups/quantos_pre_v25_20260714_223641.tar.gz`).
- VPS (`vps-gauss`) confirmado rodando exclusivamente o codigo da RFC V25 apos
  o deploy (instancia unica, pid 1563310).
- `.env` do VPS preservado (`QUANTOS_ACCOUNT_SIZE=200`, `QUANTOS_MODE=DEVELOPMENT`);
  `QUANTOS_LEVERAGE_MAX` nao definido explicitamente la, usa o fallback do
  codigo (25), igual ao default local.
- 20 min de monitoramento pos-deploy: zero erros novos, zero aprovacoes novas.
- Pendencia (compartilhada com V25.1): validar Hard Gate em sinal real
  aprovado - ainda nao ocorreu nem local nem no VPS.
- Identificado (nao resolvido nesta etapa): os 2 sinais "Conflito MTF detectado!"
  da V25.1 nao vieram do processo pm2 do `vps-gauss` - origem real identificada
  e corrigida na RFC V25.3 (abaixo).

## RFC V25.3 (2026-07-14) — Auditoria da Origem dos Sinais do Telegram

### Resultado
CONCLUIDA. Ver `RFC_V25_3_AUDITORIA_ORIGEM_SINAIS.md` para o relatorio completo.

### Resumo
- **Causa raiz da duplicidade encontrada**: o VPS tinha 2 processos QuantOS
  rodando ao mesmo tempo - o pm2 (gerenciado por esta RFC) e um servico
  `systemd` (`quantos.service`, enabled, `Restart=always`) esquecido, rodando
  ha 16h com codigo anterior a RFC V25 (nunca reiniciado por nenhum deploy
  anterior, que so reinicia o pm2). Os 2 enviavam para o mesmo Telegram
  (mesmo `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`), explicando os sinais quase
  identicos recebidos com poucos segundos de diferenca.
- **Acao tomada (autorizada pelo usuario)**: `systemctl stop` +
  `systemctl disable` do `quantos.service`. Confirmado: agora so 1 processo
  (pm2) ativo no VPS.
- Auditados todos os ambientes possiveis (Docker, WSL, Task Scheduler, cron,
  GitHub Actions, SSH config) - nenhum outro ambiente encontrado.
- Implementado fingerprint temporario de instancia (Servidor/PID/Build) em
  cada sinal do Telegram e no log de startup, para rastreabilidade completa
  daqui em diante.
- 4 testes novos, suite completa 496/496 passando, zero regressao.
- Nenhuma logica operacional, filtro, calculo ou threshold foi alterado.
