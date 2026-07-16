# RFC V25.3 — Auditoria da Origem dos Sinais do Telegram

Data: 2026-07-14

---

## Achado Principal: Duplicidade Real Encontrada e Corrigida

O VPS (`vps-gauss`, IP 191.252.204.129) tinha **2 processos QuantOS rodando
simultaneamente e enviando para o mesmo Telegram**:

| Processo | Gerenciador | PID | Rodando desde | Código |
|---|---|---|---|---|
| `quantos` | pm2 | 1563310 → 1569000 (após restart do fingerprint) | Hoje, 22:38 (RFC V25.2) | Atualizado (RFC V25) |
| `quantos.service` | **systemd** (`enabled`, `Restart=always`) | 1529168 | Hoje, 06:57 — **16h ininterruptas** | Código antigo (carregado em memória antes de qualquer deploy de hoje) |

Isso explica **100%** do sintoma reportado: os 2 sinais quase idênticos de
ANONUSDT recebidos com 7 segundos de diferença (Ciclo #435 vs #290) eram os
dois processos analisando o mesmo mercado de forma independente. O systemd
nunca foi reiniciado por nenhum `deploy_vps.sh` anterior (o script só reinicia
o pm2), então continuou rodando em memória o código de antes da RFC V25 —
por isso a mensagem "Conflito MTF detectado!" (texto antigo) sem bloqueio.

**Ação tomada (autorizada pelo usuário)**: `systemctl stop quantos.service && systemctl disable quantos.service`.
Confirmado: agora só existe 1 processo (`pm2`, pid 1569000) enviando sinais.

---

## 1. Todos os Servidores

| Ambiente | Status |
|---|---|
| VPS `vps-gauss` (191.252.204.129) | Ativo — única fonte legítima agora |
| VPS "antigo" (2ª entrada no SSH config) | Não existe separadamente — `vps-191252204129` e `vps-gauss` são o **mesmo servidor** (mesmo IP), apenas 2 aliases no `~/.ssh/config` |
| Máquina local (Windows, `DESKTOP-EOI8P73`) | Ativa — 1 processo (pm2) |
| Docker (local) | Instalado mas parado (Docker Desktop `Stopped`) — nenhum container QuantOS |
| WSL (local) | Só a distro `docker-desktop` (auxiliar do Docker Desktop), parada — nenhuma distro com QuantOS |
| GitHub Actions | Repositório QuantOS não tem `.github/workflows` — não existe automação nesse repo (diferente do bot GAUSS+DNA, que é outro projeto) |
| Outros diretórios `*quantos*` no VPS | Nenhum encontrado além de `/opt/QuantOS` |

## 2. Processos

- **Antes da correção**: pm2 (1 processo) + systemd (1 processo) no VPS = 2 processos simultâneos. Local: 1 processo.
- **Depois da correção**: pm2 (1 processo) no VPS + pm2 (1 processo) local = 2 processos totais, ambos legítimos e rastreáveis.
- Cron no VPS: só 1 entrada, `backup.sh` às 3h — não relacionado a envio de sinais.
- Nenhum processo Python órfão fora do pm2/systemd encontrado em nenhum ambiente.

## 3. Token do Telegram

- `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` são **idênticos** entre o `.env` local e o `.env` do VPS — por design, os dois ambientes enviam para o mesmo canal.
- Isso significa que **local + VPS rodando ao mesmo tempo = sinais duplicados legítimos** (2 análises independentes do mesmo mercado, ambas corretas, mas redundantes). Isso é uma decisão de arquitetura pré-existente, não uma falha desta auditoria — sinalizo para o usuário decidir se local deve continuar rodando em paralelo ao VPS ou ser usado só para desenvolvimento/testes.

## 4. Fingerprint de Instância (implementado)

Adicionado ao final do bloco "🔍 Auditoria" de cada sinal do Telegram (e ao log
de startup), temporariamente:

```
Servidor: <hostname>
PID: <pid do processo>
Build: <git commit curto ou "unknown">-<YYYYMMDD-HHMM UTC do boot>
```

Confirmado funcionando:
- Local: `Servidor: DESKTOP-EOI8P73` | `Build: d687290-20260715-0226`
- VPS: `Servidor: vps68826` | `Build: unknown-20260715-0227` (o VPS não mantém
  o diretório `.git` — o `deploy_vps.sh` o exclui do envio de propósito — por
  isso o commit aparece como `unknown`; o timestamp de build ainda permite
  distinguir a instância e o momento exato do boot)

## 5. Hash da Versão no Startup

Já existia parcialmente (commit git + SHA256 por arquivo-chave, adicionado em
RFC anterior). Complementado nesta RFC com `Servidor` e `Fingerprint` (build)
no log de inicialização — ver `main.py::QuantOSApp.start()`.

## 6. Relatório Final — Perguntas Objetivas

| Pergunta | Resposta |
|---|---|
| Quantas instâncias do QuantOS existem? | 2 (local + VPS) |
| Quantas realmente enviam sinais? | 2 (ambas legítimas, mesmo token/chat) — antes desta RFC eram **3** (local + pm2 VPS + systemd VPS) |
| Existe duplicidade? | Havia (systemd + pm2 no VPS) — **corrigida** nesta RFC |
| Existe algum ambiente esquecido? | Sim — o `quantos.service` (systemd), habilitado desde antes, nunca desligado em nenhum deploy anterior. **Corrigido.** |
| Existe algum BOT_TOKEN compartilhado? | Sim, entre local e VPS — por design (mesmo canal do Telegram) |
| Existe algum CHAT_ID compartilhado? | Sim, mesmo motivo acima |
| Existe algum processo antigo ainda ativo? | Não, após parar/desabilitar o `quantos.service` |
| Existe risco de sinais vindos de versões diferentes? | Eliminado para o caso identificado (systemd). Risco residual: local e VPS podem divergir de versão entre um deploy e outro — mitigado pelo fingerprint (`Build`), que agora torna isso visível em cada sinal |

---

## Critério de Aceitação

Para qualquer sinal enviado ao Telegram agora é possível identificar:
servidor de origem (`Servidor`), processo (`PID`), versão/commit (`Build`) e
horário de envio (`UTC`, campo já existente). Critério atendido.

## Testes

4 testes novos (`TESTS/test_rfc_v25_3_fingerprint_rastreabilidade.py`):
renderização do fingerprint quando presente, ausência graciosa quando não
presente (retrocompatibilidade), e inspeção de código confirmando o cálculo
único no startup e a propagação para cada sinal. Suite completa: **496/496
passando**, zero regressão.

## Deploy

- Local: `pm2 restart quantos` (pid 7032) — fingerprint confirmado no log.
- VPS: `./deploy_vps.sh` (pid 1569000) — fingerprint confirmado no log, zero
  tracebacks novos, instância única confirmada novamente após o restart.

## Observações / Próximos Passos Sugeridos (não executados nesta RFC)

1. O fingerprint é temporário por natureza (bloco de auditoria) — remover do
   Telegram (mantendo só no log) quando o usuário considerar a rastreabilidade
   suficientemente validada.
2. Considerar se local deve continuar enviando para o mesmo canal que o VPS
   (hoje os dois enviam, por design, mas isso pode gerar sinais duplicados
   legítimos caso ambos aprovem o mesmo par ao mesmo tempo).
3. Nenhuma lógica operacional, filtro, cálculo ou threshold foi alterado
   nesta RFC, conforme exigido.
