# QUANT OS

## DOCUMENTO 013 — REPOSITORY STRUCTURE

VERSÃO 1.0

MILESTONE: 01 - FOUNDATION

PRIORIDADE: 🔴 CRÍTICA

DEPENDÊNCIAS: 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012

---

### OBJETIVO

Definir oficialmente a estrutura física do repositório QuantOS.

Todo arquivo criado deverá respeitar esta organização.

É proibido criar arquivos fora desta estrutura sem justificativa técnica.

---

### REPOSITÓRIO OFICIAL

```
QuantOS/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── .gitignore
├── requirements.txt
│
├── DOCS/
│   ├── architecture/
│   ├── governance/
│   ├── standards/
│   ├── knowledge/
│   ├── reports/
│   └── roadmap/
│
├── CORE/
│   ├── governor/
│   ├── guardian/
│   ├── reasoning/
│   ├── commander/
│   └── philosophy/
│
├── ENGINE/
│   ├── scanner/
│   ├── scoring/
│   ├── signals/
│   ├── optimizer/
│   ├── market/
│   └── validation/
│
├── SERVICES/
│   ├── backtest/
│   ├── audit/
│   ├── performance/
│   ├── reports/
│   ├── versioning/
│   └── documentation/
│
├── BOTS/
│   ├── mexc/
│   ├── binance/
│   ├── bybit/
│   └── future/
│
├── KNOWLEDGE/
│   ├── market/
│   ├── smc/
│   ├── orderflow/
│   ├── kalman/
│   ├── statistics/
│   ├── engineering/
│   ├── psychology/
│   └── risk/
│
├── BASELINES/
│
├── MEMORY/
│
├── REPORTS/
│
├── TESTS/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   ├── performance/
│   └── backtest/
│
├── CONFIG/
│
├── SCRIPTS/
│
├── TOOLS/
│
└── LAB/
    ├── research/
    ├── experiments/
    └── prototypes/
```

---

### REGRAS

Toda pasta deverá possuir apenas uma responsabilidade.

Nenhum código de produção poderá ficar na pasta LAB.

Nenhum teste poderá ficar fora da pasta TESTS.

Bots nunca conterão regras de negócio.

Toda inteligência permanecerá no QuantOS.

Toda documentação ficará em DOCS.

A nomenclatura oficial de diretórios é UPPERCASE (ex: CORE, ENGINE, KNOWLEDGE, CONFIG).

---

### OBJETIVO FINAL

Garantir uma estrutura de repositório organizada, padronizada, escalável e preparada para crescimento durante muitos anos.

---

Fim do Documento 013.
