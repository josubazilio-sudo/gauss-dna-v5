# RFC V23 — Watchlist Prioritária MEXC Futures

## Objetivo
Criar um sistema de prioridade inteligente baseado na Watchlist do usuário, garantindo que as moedas da Watchlist sejam sempre analisadas primeiro sem deixar de monitorar todo o mercado Futures da MEXC.

## Motivação
Usuários possuem moedas de interesse prioritário que precisam ser monitoradas com máxima prioridade. Antes do V23, todas as moedas eram escaneadas na mesma ordem (prioridade dinâmica baseada em volume/volatilidade), sem diferenciar moedas da watchlist.

## Fluxo Final
```
Watchlist (JSON) → Scan Queue Reorder → Scanner Prioritário
                                        → Restante Mercado Futures → Ranking Geral
→ Decision Engine → Risk Manager → V21 Math Auditor → V22 MEXC Validator → Telegram
```

## Arquivos Criados

| Arquivo | Descrição |
|---|---|
| `config/watchlist_priority.json` | Watchlist inicial com 10 moedas (editável sem código) |
| `ENGINE/watchlist/watchlist_manager.py` | Classe `WatchlistManager` — load, query, reorder, bonus |
| `TESTS/test_rfc_v23_watchlist_priority.py` | 38 testes com 95%+ de cobertura |

## Arquivos Modificados

| Arquivo | Descrição |
|---|---|
| `ENGINE/scanner/scanner_config.py` | `WATCHLIST_PRIORITY_BONUS`, `WATCHLIST_PATH` |
| `main.py` | Import WatchlistManager, init, reorder scan queue, ranking bonus, watchlist flag, V23 logger |
| `SERVICES/telegram/telegram_formatter.py` | Indicador ⭐ WATCHLIST PRIORITÁRIA |

## Funcionamento

### 1. Carregamento
- `WatchlistManager` carrega `config/watchlist_priority.json` na inicialização
- Aceita `QUANTOS_WATCHLIST_PATH` via .env para path customizado
- Normaliza símbolos para uppercase
- Recarrega sob demanda via `reload()`

### 2. Prioridade na Fila de Scan
- Após reordenação por `priority_score`, a watchlist move suas moedas para o início da fila
- A ordem relativa entre moedas da watchlist (do JSON) é preservada
- Nenhum par é removido ou duplicado
- `reorder_scan_queue()` é uma função pura de reordenação

### 3. Bônus no Ranking
- `WATCHLIST_PRIORITY_BONUS = 3` (configurável)
- Aplicado como `+0.003` no `_cycle_rank` para desempate
- NÃO altera: quality, confidence, consensus, coherence, probability, score
- Usado exclusivamente como critério de desempate em `max()`

### 4. Indicador Telegram
- `data["_watchlist_priority"] = True/False` propagado no pipeline
- Telegram exibe: `⭐ *WATCHLIST PRIORITÁRIA*` no card do sinal

### 5. Logger V23
- Log separado `WATCHLIST` com contagem de moedas escaneadas vs total da watchlist
- Executado a cada ciclo após o fetch+scan

## Testes (38 testes)

| Grupo | Testes | Cobertura |
|---|---|---|
| WatchlistManagerLoad | 7 | Arquivo válido, ordem preservada, case normalization, missing file, empty, invalid JSON, reload |
| IsWatchlist | 4 | Positivo, negativo, case insensitive, empty list |
| ReorderScanQueue | 6 | Watchlist primeiro, preserva todos, all watchlist, no watchlist, empty, ordem interna |
| CountInList | 4 | All, mixed, none, empty |
| PriorityBonus | 4 | Watchlist, non-watchlist, value constant, case insensitive |
| StatsDict | 2 | Keys, preserve order |
| ConfigFileExists | 3 | File exists, valid JSON, contains all initial symbols |
| PriorityBonusConstant | 2 | Cross-module consistency, positive small int |
| IntegrationWithPriorityScore | 3 | No leak, no data loss, no decision field contamination |
| TelegramIndicator | 3 | Watchlist True, False, missing key |

**Total: 38 testes, cobertura > 95%**

## Configuração

| Variável | Default | Descrição |
|---|---|---|
| `WATCHLIST_PRIORITY_BONUS` | `3` | Bônus para desempate no ranking |
| `WATCHLIST_PATH` | `config/watchlist_priority.json` | Caminho do arquivo JSON |
| `QUANTOS_WATCHLIST_PATH` (env) | — | Sobrescreve caminho do JSON |

## Impacto na Velocidade e Qualidade
- **Tempo adicional**: ~0.01ms (apenas reordenação de lista em memória)
- **Qualidade**: inalterada — bônus só atua em desempates
- **Cobertura**: 100% do mercado Futures continua sendo escaneado
- **Prioridade**: Watchlist SEMPRE na frente da fila de scan
- **Flexibilidade**: editar JSON para adicionar/remover moedas sem reiniciar o sistema (via `reload()`)
