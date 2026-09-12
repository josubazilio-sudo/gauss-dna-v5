# K12 → TradingView Integration

Integração automática que envia os **melhores sinais** (OURO, Score ≥80) do K12 para TradingView via webhook.

## Configuração

### 1. Obter URL do Webhook TradingView

1. Abrir TradingView
2. Ir para **Settings → Webhooks** (ou criar um novo)
3. Copiar a URL do webhook

### 2. Configurar Variável de Ambiente

No VPS, adicionar ao `.env` ou `.bashrc`:

```bash
export TRADINGVIEW_WEBHOOK_URL="https://tradingview.webhook.url/seu-webhook-aqui"
```

Ou adicionar ao arquivo `/root/gauss-dna-v5/.env`:

```
TRADINGVIEW_WEBHOOK_URL=https://tradingview.webhook.url/seu-webhook-aqui
```

### 3. Reiniciar K12

```bash
ssh vps-gauss "bash /root/gauss-dna-v5/start_k12.sh"
```

## Critérios de Envio

Sinais são enviados para TradingView **automaticamente** quando:

✅ **Tier = OURO** (qualidade máxima)
✅ **Score ≥ 80** (alta confiança)
✅ **RR ≥ 2.0** (risk/reward aceitável)
✅ **Estrutura confirmada** (BOS ou SWEEP)

## Dados Enviados

Cada sinal envia os seguintes dados para TradingView:

```json
{
  "time": "2026-09-12T12:45:00+00:00",
  "symbol": "BTCUSDT",
  "timeframe": "30m",
  "direction": "LONG",
  "quality": "PREMIUM",
  "tier": "OURO",
  "score": 85,
  "entry_quality": 78,
  "rr_ratio": 2.5,
  "rvol": 2.1,
  "structure": "SWEEP",
  "entry": 45000,
  "tp1": 46500,
  "tp2": 47500,
  "stop": 44000,
  "source": "K12_SMC_ENGINE"
}
```

## Verificação

### Ver logs no VPS

```bash
ssh vps-gauss "grep 'TradingView' /tmp/k12_session.log | tail -20"
```

Saída esperada:
```
✅ TradingView: BTCUSDT enviado (score=85, rr=2.50, tier=OURO)
✅ TradingView: ETHUSDT enviado (score=82, rr=2.15, tier=OURO)
K12 TradingView: 2 sinal(is) premium enviado(s)
```

### Sem Webhook Configurado

Se `TRADINGVIEW_WEBHOOK_URL` não está configurado:

```
⚠️ TRADINGVIEW_WEBHOOK_URL não configurado
```

Nenhum sinal será enviado até configurar.

## Exemplo de Uso

### Configurar manualmente na VPS

```bash
ssh vps-gauss "
  echo 'export TRADINGVIEW_WEBHOOK_URL=https://seu-webhook-aqui' >> ~/.bashrc
  source ~/.bashrc
  bash /root/gauss-dna-v5/start_k12.sh
"
```

### Verificar se está funcionando

```bash
ssh vps-gauss "ps aux | grep runner.py && echo 'K12 rodando'"
```

### Ver sinais sendo enviados

```bash
ssh vps-gauss "tail -f /tmp/k12_session.log | grep -i tradingview"
```

## Troubleshooting

### "TRADINGVIEW_WEBHOOK_URL não configurado"

**Solução:** Adicionar ao `.env`:
```bash
TRADINGVIEW_WEBHOOK_URL=https://seu-webhook-aqui
```

E reiniciar K12.

### Webhook retorna erro 401/403

**Possíveis causas:**
- URL incorreta
- Token expirado
- Permissões insuficientes

**Solução:** Verificar a URL no TradingView Settings → Webhooks

### Nenhum sinal sendo enviado

**Verificar:**
1. ✅ Webhook está configurado: `echo $TRADINGVIEW_WEBHOOK_URL`
2. ✅ Há sinais sendo gerados: `grep "aprovados" /tmp/k12_session.log`
3. ✅ Tier é OURO: `grep "tier.*OURO" /tmp/k12_session.log`
4. ✅ Score ≥ 80: `grep "score" /tmp/k12_session.log`

## Desativar Temporariamente

Comentar a linha no runner.py:

```python
# tv_enviados = await enviar_multiplos_tradingview(aprovados)
```

Ou remover a variável de ambiente:

```bash
unset TRADINGVIEW_WEBHOOK_URL
```

Reiniciar K12.

## Arquivos

- `tradingview_webhook.py` — Módulo de integração
- `runner.py` — Chamada automática de envio
- `TRADINGVIEW_SETUP.md` — Esta documentação

---

**Status:** ✅ Operacional (após configurar TRADINGVIEW_WEBHOOK_URL)
