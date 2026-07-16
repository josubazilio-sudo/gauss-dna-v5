# RFC V25.5 — Diagnóstico Rápido Inteligente (Fast Diagnostic)

Data: 2026-07-15

## Objetivo

Executar um diagnóstico leve ao final de cada ciclo do scanner, para
descobrir rapidamente qualquer bloqueio, gargalo ou bug antes que o
sistema fique longos períodos sem emitir sinais — sem recalcular
indicadores e sem exceder ~2 segundos.

## Reuso (nada foi duplicado)

Investigação prévia mostrou que a maior parte da infraestrutura necessária
**já existia**, apenas não estava conectada:

- `ENGINE/analytics/rejection_analytics.py::RejectionAnalytics` já roda ao
  final de todo ciclo (`end_cycle()`) e já calcula `total_analyzed`,
  `total_approved`, `approval_rate`, `gate_percentages`, `ranking` — a base
  de quase tudo que a RFC pede. Reutilizado diretamente, sem recálculo.
- `SERVICES/telegram/telegram_service.py::TelegramService.send_diagnostic(msg)`
  já existia pronto para enviar texto livre ao Telegram, mas **nunca era
  chamado por ninguém** — reutilizado para o alerta imediato.
- `TelegramDiagnosticFormatter` / `TELEGRAM_SEND_DIAGNOSTICS` no `.env`: eram
  código morto (nunca importado em `main.py`) — não removidos (fora de
  escopo), apenas não usados por esta RFC.
- `report.health["api"]` está hardcoded em `100` (nunca reflete a API real)
  — não pôde ser usado; usado em seu lugar `silent_drops` (real, calculado
  a partir de candles que de fato não carregaram) como proxy de
  inconsistência de API/dados.

## Implementação

### Novo módulo: `ENGINE/diagnostic/fast_diagnostic.py`
- `DiagnosticBaseline`: média móvel em memória dos últimos 20 ciclos
  (por gate e taxa de aprovação). Reinicia com o processo (pm2/systemd) —
  decisão deliberada para manter o módulo leve e sem I/O extra.
- `build_fast_diagnostic(...)`: função pura, recebe o resumo já calculado
  pelo `RejectionAnalytics` + 3 agregados triviais (ADX médio, regime
  dominante, % de candles perdidos) já disponíveis em memória — nenhum
  indicador é recalculado.
- `format_fast_diagnostic_log(...)`: formata o relatório para o log.

### Integração em `main.py`
- Chamado ao final de cada ciclo, logo após `RejectionAnalytics.end_cycle()`.
- Protegido por `try/except` (fail-safe) — um erro no diagnóstico nunca
  derruba o ciclo principal, seguindo o mesmo padrão já usado no resto do
  arquivo.
- Log sempre (`FASTDIAG| ...`); Telegram **apenas quando há alerta
  imediato** (decisão de design: evita spam a cada ~3 minutos — o relatório
  rotineiro fica só no log).

### Regras de decisão (documentadas e ajustáveis em `fast_diagnostic.py`)
| Item | Regra |
|---|---|
| Mercado Forte | ADX médio ≥ 25 e regime dominante uptrend/downtrend |
| Mercado Fraco | ADX médio < 18 |
| Mercado Lateral | Caso contrário |
| Gargalo (⚠) | Gate responsável por ≥ 35% das reprovações do ciclo |
| Possível bug | Gate com % atual ≥ 25 pontos acima da média histórica (mín. 3 ciclos de base) |
| Confiança do bug | `min(99%, 50% + delta)` |
| Alerta: zero sinais | ≥ 5 ciclos consecutivos sem nenhuma aprovação |
| Alerta: gate crítico | Um gate reprova ≥ 90% de **todos** os ativos analisados (não só dos reprovados) |
| Alerta: API/candles | ≥ 15% dos ativos não carregaram candles no ciclo |
| Alerta: queda de aprovação | Taxa atual < 50% da média histórica recente |
| Alerta: bug com alta confiança | Confiança do bug ≥ 90% |
| "Score vs decisão divergente" | Não implementado como alerta separado — já é impedido estruturalmente pelos Hard Gates existentes (Classificação, Coerência, RFC V25); reimplementar seria duplicar um gate já ativo |

## Testes

18 testes novos (`TESTS/test_rfc_v25_5_fast_diagnostic.py`): baseline móvel,
classificação de mercado, gargalos, detecção de bug (com e sem histórico
suficiente), todas as 4 condições de alerta imediato implementadas, e
inspeção de código confirmando a integração fail-safe em `main.py`.

Suite completa: **518/518 passando**, zero regressão.

## Deploy e Validação em Produção Real

Local e VPS, ambos confirmados com dados reais do primeiro ciclo pós-deploy:

```
Scanner saudavel: NAO
Mercado: Lateral
Ativos analisados: 592-594
Ativos aprovados: 0
TOP MOTIVOS: Consenso 50%, Scanner 37%, Exaustao 14%
GARGALOS: Consenso e Scanner acima de 35%
```

Nenhum alerta imediato disparou (esperado: só 1 ciclo decorrido, streak de
zero sinais ainda abaixo do limite de 5 ciclos consecutivos).

## Observação (não corrigida nesta RFC, fora de escopo)

Detectado um bug pré-existente (não introduzido por esta RFC):
`build_advanced_report()` (RFC V6.7/V7, módulo antigo) lança `KeyError:
'resumo_executivo'` quando nenhum candidato chega ao Decision Engine no
ciclo (cenário comum desde que Exaustão/Consenso passaram a filtrar mais
cedo, RFC V25.4) — já é capturado pelo `try/except` existente em `main.py`
e vira apenas um `WARNING` no log, nunca derruba o ciclo. Reportando para
eventual correção futura, se desejado.

## Critério de Aceitação

Cumprido: a cada ciclo agora é possível saber, sem esperar 30 minutos,
se o scanner está saudável, qual o motivo dominante de bloqueio, se há
gargalo ou suspeita de bug (com % de confiança), e alertas imediatos
chegam ao Telegram quando algo foge do padrão — tudo sem recalcular
indicadores e sem alterar nenhum parâmetro operacional.
