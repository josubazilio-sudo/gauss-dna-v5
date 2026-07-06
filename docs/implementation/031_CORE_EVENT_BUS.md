# QUANT OS

## DOCUMENTO 031 — CORE EVENT BUS

VERSÃO 1.0

MILESTONE: 02 - CORE ENGINE

PRIORIDADE: 🔴 MÁXIMA

DEPENDÊNCIAS: 001 até 030 - Todos os documentos anteriores.

---

### OBJETIVO

Definir oficialmente o Barramento de Eventos (Event Bus) do QuantOS.

Todo módulo deverá comunicar eventos através deste sistema.

É proibida a comunicação direta entre módulos quando existir um evento apropriado.

---

### MISSÃO

Desacoplar módulos.

Padronizar comunicação.

Facilitar expansão.

Facilitar auditoria.

Permitir evolução sem dependências ocultas.

---

### ESTRUTURA

```
CORE/events/
├── __init__.py
├── event_bus.py
├── dispatcher.py
├── subscribers.py
├── publishers.py
├── event_types.py
└── event_registry.py
```

---

### RESPONSABILIDADES

**event_bus.py** — Gerenciar o barramento central de eventos.

**dispatcher.py** — Distribuir eventos para os módulos inscritos.

**publishers.py** — Publicar eventos oficiais.

**subscribers.py** — Registrar consumidores de eventos.

**event_types.py** — Definir todos os tipos oficiais de eventos.

**event_registry.py** — Registrar e validar eventos disponíveis.

---

### EVENTOS OFICIAIS

SYSTEM_STARTED

SYSTEM_STOPPED

CONFIG_LOADED

SCANNER_STARTED

SCANNER_FINISHED

SIGNAL_CREATED

SIGNAL_APPROVED

SIGNAL_REJECTED

BACKTEST_STARTED

BACKTEST_FINISHED

AUDIT_STARTED

AUDIT_FINISHED

ERROR_OCCURRED

BASELINE_CREATED

PROJECT_DNA_UPDATED

REPORT_GENERATED

---

### FLUXO

```
Módulo Origem
    ↓
Publica Evento
    ↓
Event Bus
    ↓
Dispatcher
    ↓
Subscribers
    ↓
Execução
    ↓
Registro em Log
```

---

### REGRAS

Todo evento deverá possuir:

Identificador único.

Data.

Hora.

Origem.

Destino (quando aplicável).

Tipo.

Prioridade.

Payload.

Status.

Todo evento deverá ser registrado pelo Logger.

Eventos críticos deverão ser registrados também pelo Guardian.

---

### PROIBIÇÕES

Não criar eventos duplicados.

Não utilizar comunicação direta quando existir evento equivalente.

Não ignorar eventos críticos.

Não alterar tipos oficiais sem atualização do registro.

---

### CHECKLIST

- [ ] Event Bus implementado.
- [ ] Dispatcher implementado.
- [ ] Registro de eventos criado.
- [ ] Tipos oficiais definidos.
- [ ] Integração com Logger validada.
- [ ] Integração com Guardian validada.
- [ ] Eventos documentados.

---

### OBJETIVO FINAL

Criar um sistema único de comunicação entre módulos, garantindo baixo acoplamento, alta escalabilidade, rastreabilidade e facilidade de manutenção em toda a arquitetura do QuantOS.

---

FIM DO DOCUMENTO 031
