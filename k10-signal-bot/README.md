# 🤖 K10 Signal Bot

Bot de sinais de trading para Telegram com arquitetura institucional adaptativa.

## Arquitetura

- **4 Setups automáticos**: Continuação, Reversal, Breakout, Range
- **Market Regime Detection**: Bull/Bear Trend, Range, Alta/Baixa Volatilidade, Transição
- **Entry Engine**: 10+ filtros de confirmação de entrada
- **Quality Gate**: RR ≥ 2, volume, liquidez, estrutura
- **Multi-timeframe**: 30m → 1H → 4H → 1D

## Instalação

```bash
# Clonar repositório
git clone https://github.com/seu-usuario/k10-bot.git
cd k10-bot

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis
cp .env.example .env
# Edite o .env com seu BOT_TOKEN
```

## Configuração

1. Crie um bot no Telegram via [@BotFather](https://t.me/BotFather)
2. Copie o token e cole no `.env`
3. Adicione seu Chat ID em `ALLOWED_CHAT_IDS` (opcional)

## Executar

```bash
python bot.py
```

## Comandos

| Comando | Descrição |
|---------|-----------|
| `/start` | Menu principal |
| `/analisar BTCUSDT` | Análise completa K10 |
| `/scan` | Varre todos os ativos da watchlist |
| `/regime BTCUSDT` | Regime de mercado atual |
| `/setup BTCUSDT` | Setup recomendado |
| `/ajuda` | Lista de comandos |

## Estrutura

```
k10-bot/
├── bot.py          # Bot Telegram (handlers, formatação)
├── k10_engine.py   # Engine de análise (setups, regime, entry)
├── config.py       # Configurações e watchlist
├── .env.example    # Template de variáveis
├── requirements.txt
└── README.md
```

## Rejeição detalhada

Quando um sinal é rejeitado, o bot informa:
- Qual setup foi analisado
- Qual regra rejeitou e com qual valor
- O que falta para validar
- Qual setup alternativo seria mais adequado
