# QUANT OS

## DOCUMENTO 011 — PROJECT STRUCTURE

VERSÃO 1.0

MILESTONE: 01 - FOUNDATION

DEPENDÊNCIAS: 001, 002, 003, 004, 005, 006, 007, 008, 009, 010

---

### OBJETIVO

Definir oficialmente a estrutura física e lógica do QuantOS.

Este documento será a referência única para criação de diretórios, módulos e organização do projeto.

Nenhum arquivo poderá ser criado fora desta estrutura sem justificativa técnica.

---

### ESTRUTURA OFICIAL

```
QuantOS/
├── CORE/
├── KNOWLEDGE/
├── ENGINE/
├── SERVICES/
├── BOTS/
├── CONFIG/
├── BASELINES/
├── MEMORY/
├── REPORTS/
├── TESTS/
├── LAB/
├── TOOLS/
├── DOCS/
└── SCRIPTS/
```

---

### CORE

Responsável pela governança do QuantOS.

Contém:

- Constituição
- Filosofia
- Governor
- Commander
- Guardian
- Reasoning Engine

Nenhum módulo poderá modificar o CORE sem aprovação do System Governor.

---

### KNOWLEDGE

Biblioteca oficial do projeto.

Contém conhecimento validado sobre:

- Mercado
- SMC
- Order Flow
- Liquidez
- Estatística
- Gestão de Risco
- Backtest
- Engenharia
- Performance

Toda decisão técnica deverá consultar esta base.

---

### ENGINE

Motor principal do QuantOS.

Contém:

- Scanner
- Decision Engine
- Score Engine
- Signal Engine
- Market Intelligence
- Optimizer
- Validation Engine

---

### SERVICES

Serviços compartilhados.

- Auditoria
- Backtest
- Versionamento
- Logs
- Documentação
- Performance

Todos devem ser reutilizáveis.

---

### BOTS

Responsáveis apenas pela integração com exchanges.

Nenhuma lógica crítica poderá ficar dentro dos bots.

Eles apenas:

- recebem sinais
- executam ordens
- retornam informações

---

### MEMORY

Armazena todo o conhecimento adquirido.

- Melhorias aprovadas
- Melhorias rejeitadas
- Bugs
- Lições aprendidas
- Melhores parâmetros
- Histórico

---

### LAB

Área destinada a pesquisas.

Nenhuma funcionalidade experimental poderá ir para produção sem:

- Backtest
- Auditoria
- Aprovação
- Baseline

---

### REGRAS GERAIS

Cada módulo deve possuir uma única responsabilidade.

Evitar dependências desnecessárias.

Evitar duplicação de código.

Evitar comunicação direta entre módulos sem interfaces oficiais.

A arquitetura deverá permanecer simples, modular, reutilizável e escalável.

---

### RESULTADO ESPERADO

Todo desenvolvedor ou IA deverá compreender imediatamente onde cada componente pertence e como o QuantOS está organizado.

---

Fim do Documento 011.
