# SYSTEM RECOVERY V20.4

- **Data:** 2026-07-13 07:20
- **Responsável:** RFC V20.4 — Recuperação Operacional do QuantOS

---

## Estado Anterior (Pré-Recuperação)

| Item | Estado |
|------|--------|
| **QuantOS** | NÃO rodando (parado desde 12/07 23:48) |
| **GAUSS DNA V5 (SINAIS TOP)** | Rodando (PID 6180, desde 06:04 via PM2) |
| **PM2** | Gerenciando `gauss-dna-v5` |
| **Task Scheduler** | `\GAUSS-DNA-V5` — Habilitado, executa `pm2 resurrect` no logon |
| **Startup** | `QuantOS.lnk` — Quebrado (VBS não existe) |
| **Telegram** | Ambos projetos usam MESMO token/chat |

### Causa Raiz do Problema

O GAUSS DNA V5 enviava sinais com label "SINAIS TOP" para o **mesmo bot/chat do Telegram** que o QuantOS utiliza, criando a impressão de que o QuantOS ainda tinha o módulo TOP ativo. Na verdade, o QuantOS estava parado há mais de 7 horas.

---

## Correções Executadas

| # | Ação | Comando |
|---|------|---------|
| 1 | Parar GAUSS DNA V5 | `pm2 stop gauss-dna-v5` |
| 2 | Remover do PM2 | `pm2 delete gauss-dna-v5` |
| 3 | Resetar PM2 dump | `pm2 save` (dump limpo) |
| 4 | Desabilitar Task Scheduler | `schtasks /change /tn "GAUSS-DNA-V5" /disable` |
| 5 | Remover atalho quebrado | Remove-Item `QuantOS.lnk` da Startup |
| 6 | Criar PM2 ecosystem do QuantOS | `ecosystem.config.js` |
| 7 | Iniciar QuantOS via PM2 | `pm2 start ecosystem.config.js --only quantos` |
| 8 | Salvar PM2 para auto-restore | `pm2 save` |

---

## Processos Ativos (pós-recuperação)

```
PID 10888  python.exe  QuantOS (main.py)  PM2: quantos
PID 12756  node.exe    PM2 Daemon
PID  8148  node.exe    PM2 Daemon (original)
```

**Apenas 1 processo Python:** QuantOS.

---

## Serviços e Startup

### PM2
- App `quantos` (PID 10888) — **online**, uptime 9min
- App `gauss-dna-v5` — **deletado**
- `pm2 save` executado — dump sem apps antigos

### Task Scheduler
- `\GAUSS-DNA-V5` — **Desabilitado**

### Startup (shell:startup)
- `Ollama.lnk` — mantido
- `QuantOS.lnk` — **removido** (estava quebrado)

### Próximo Logon
PM2 com `pm2 resurrect` (se reabilitado) ou manual:
```cmd
pm2 start C:\Users\josue\QuantOS\ecosystem.config.js --only quantos
```

---

## Status do QuantOS

| Módulo | Status |
|--------|--------|
| **Health Check** | ✅ OK (07:08:09) |
| **Startup** | ✅ Iniciado (07:08:09) |
| **Modo** | PRODUCTION / PAPER_TRADING |
| **Scanner** | ✅ Ativo (300 pares/ciclo) |
| **Decision Engine** | ✅ Operando (0 aprovados, mercado crítico) |
| **Risk Manager** | ✅ Ativo |
| **Telegram** | ✅ Configurado (bot `8834044482:AAF-...`, chat `-1003994169897`) |
| **Diagnostic Engine** | ✅ Ativo |
| **BotEngine** | ✅ PAPER_TRADING mode, autenticação ignorada |

---

## Pipeline — 5 Ciclos (Benchmark)

| Ciclo | Hora | Duração | Pares | Aprovados | Gargalo Principal | Erros 429 |
|-------|------|---------|-------|-----------|-------------------|----------|
| #1 | 07:08:14 | 44.5s | 300 | 0 | Entry Zone (66.7%) | 79 |
| #2 | 07:10:12 | 43.0s | 300 | 0 | Entry Zone (66.7%) | 77 |
| #3 | 07:12:10 | 44.2s | 300 | 0 | Entry Zone (66.7%) | 77 |
| #4 | 07:14:08 | 43.4s | 300 | 0 | Entry Zone (60.0%) | 76 |
| #5 | 07:16:06 | 41.9s | 300 | 0 | Entry Zone (50.0%) | 72 |

**Tempo médio por ciclo:** ~43.4s
**Aprovados médios:** 0 (mercado em condição crítica — health score 0.0)

---

## Telegram

- **Bot Token:** `8834044482:AAF-M5iJP6T6KaTW5_pmf82LACxDT-207z0`
- **Chat ID:** `-1003994169897`
- **Origem atual:** Apenas `SERVICES/telegram/telegram_sender.py` (QuantOS)
- **Arquivo de envio:** `SERVICES/telegram/telegram_sender.py:40` — `bot.send_message(chat_id=..., text=...)`
- **Nenhum sinal "TOP" ou "SINAIS TOP" nos logs do QuantOS** — confirmado

---

## Itens de Atenção

1. **MEXC_API_KEY/MEXC_API_SECRET vazios** — não afeta PAPER_TRADING, mas para LIVE será necessário preencher
2. **429 rate limiting** — ~76 erros/ciclo. Se persistir, reduzir `SCAN_MAX_WORKERS` ou `MAX_SCAN_PAIRS`
3. **Entry Zone como gargalo** — 50-66% das rejeições. Mercado crítico (health 0.0). Sem ação necessária.
4. **GAUSS DNA V5** — caso queira rodar novamente, usar **outro bot Telegram** para não poluir o chat

---

## Rollback (se necessário)

```powershell
# Reativar GAUSS DNA V5
schtasks /change /tn "GAUSS-DNA-V5" /enable
cd C:\Users\josue\gauss-dna-v5
pm2 start ecosystem.config.js

# Parar QuantOS
pm2 stop quantos
pm2 delete quantos
```
