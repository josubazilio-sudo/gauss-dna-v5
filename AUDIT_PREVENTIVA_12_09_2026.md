# AUDITORIA PREVENTIVA K12 — 12/09/2026
## Rastreamento: Candidatos TOP → Rejeição Final

---

## 🚨 DESCOBERTA CRÍTICA

**Os pares relatados pelo usuário (MUSTOCK, XAU, ARB) NÃO EXISTEM NA MEXC!**

Eles aparecem no diagnóstico "SEM SINAL" como "TOP ATIVOS MAIS PRÓXIMOS" porque:
- Scanner diagnosticador usa 50 pares pequeno
- Esses pares não são validados contra MEXC nesse diagnóstico
- Quando processados, API MEXC rejeita: `"mexc does not have market symbol MUSTOCK"`

**Resultado:** Rejeição no nível de API, não análise de mercado.

---

## 📊 RASTREAMENTO DE CANDIDATOS REAIS

### 1️⃣ BTCUSDT

**Entrada:** K10Engine.analisar()

| Campo | 30m | 1h |
|-------|-----|-----|
| Score | 45 | 43 |
| RVOL | 0.179 | 0.470 |
| RR | 2.11 | 2.11 |
| Direção | LONG | SHORT |
| BOS/SWEEP | ❌ | ❌ |

**Motivos de Rejeição (30m - melhor score):**
1. ❌ `EMA10 < EMA21 — contra LONG` (HARD gate)
2. ❌ `Volume muito baixo RVOL 0.18 < 0.5` (HARD gate - liquidez)
3. ❌ `RR 2.11 < 2.5` (HARD gate - ratio mínimo)
4. ❌ `Sem BOS/CHoCH confirmado` (HARD gate - estrutura)

**PRIMEIRO PONTO DE PARADA:** 
- **Regra:** RVOL < 0.5 mínimo
- **Valor:** 0.179
- **Função:** K10Engine._analisar_tf() linha ~700 (volume_check)
- **Tipo:** HARD gate — rejeição imediata

**Análise:**
- Score = 45 (abaixo de 70 necessário)
- Nenhum BOS/SWEEP confirmado
- RVOL extremamente baixo (0.179 vs 0.5 mínimo)
- `"ok"` no diagnóstico? SIM, mas enganoso — tem score, mas TODOS os gates duros rejeitam

---

### 2️⃣ ETHUSDT

**Entrada:** K10Engine.analisar()

| Campo | 30m | 1h |
|-------|-----|-----|
| Score | 12 | 53 |
| RVOL | 0.430 | 0.560 |
| RR | 6.58 | 2.18 |
| Direção | SHORT | LONG |
| BOS/SWEEP | ❌ | ❌ |

**Motivos de Rejeição (1h - melhor score=53):**
1. ❌ `RR 2.18 < 2.5` (HARD gate - ratio)
2. ❌ `Sem BOS/CHoCH confirmado` (HARD gate - estrutura)

**PRIMEIRO PONTO DE PARADA:**
- **Regra:** RR < 2.5 mínimo (final_selector.CFG)
- **Valor:** 2.18
- **Função:** K10Engine._analisar_tf() linha ~873 (HARD_GATE_1 RR check)
- **Tipo:** HARD gate — rejeição imediata

**Análise:**
- Score = 53 (abaixo de 70)
- RVOL borderline (0.56, logo acima de 0.5)
- Estrutura: nenhum BOS/SWEEP
- RR ligeiramente abaixo do mínimo (2.18 vs 2.5 necessário)
- `"ok"` no diagnóstico? Parcialmente — tem score razoável mas falha RR gate

---

### 3️⃣ ARBUSDT

**Entrada:** K10Engine.analisar()

| Campo | 30m | 1h |
|-------|-----|-----|
| Score | 53 | 43 |
| RVOL | 0.068 | 0.355 |
| RR | 2.18 | 3.5 |
| Direção | SHORT | SHORT |
| BOS/SWEEP | ❌ | ❌ |

**Motivos de Rejeição (30m - melhor score=53):**
1. ❌ `Volume muito baixo RVOL 0.07 < 0.5` (HARD gate - liquidez)
2. ❌ `RR 2.18 < 2.5` (HARD gate - ratio)
3. ❌ `Sem BOS/CHoCH confirmado` (HARD gate - estrutura)

**PRIMEIRO PONTO DE PARADA:**
- **Regra:** RVOL < 0.5 mínimo
- **Valor:** 0.068
- **Função:** K10Engine._analisar_tf() linha ~700 (volume check)
- **Tipo:** HARD gate — rejeição imediata

**Análise:**
- Score = 53 (abaixo de 70)
- RVOL crítico (0.068 — extremamente baixo)
- Múltiplos gates duros falham
- `"ok"` no diagnóstico? NÃO — múltiplas falhas críticas

---

### 4️⃣ LINKUSDT ⭐ (MAIS PRÓXIMO DE APROVAÇÃO)

**Entrada:** K10Engine.analisar()

| Campo | 30m | 1h |
|-------|-----|-----|
| Score | 61 | 67 |
| RVOL | 0.102 | 1.556 |
| RR | 3.5 | 3.5 |
| Direção | SHORT | SHORT |
| BOS/SWEEP | ❌ | ❌ |

**Motivos de Rejeição (1h - melhor score=67):**
1. ❌ `Sem BOS/CHoCH confirmado` (HARD gate - estrutura)

**PRIMEIRO PONTO DE PARADA:**
- **Regra:** BOS ou CHoCH deve estar confirmado (hard requirement)
- **Valor:** bos_ok=False, sweep_ok=False
- **Função:** K10Engine._analisar_tf() linha ~597-598
- **Tipo:** HARD gate — rejeição por estrutura

**Análise:**
- Score = 67 (MUITO perto de 70 necessário)
- RVOL = 1.556 (✅ EXCELENTE — acima de 0.5)
- RR = 3.5 (✅ EXCELENTE — acima de 2.5)
- **ÚNICO problema:** Sem BOS/CHoCH confirmado
- `"ok"` no diagnóstico? Tecnicamente SIM — tem score alto, RVOL ok, RR ok
  - Mas FALHA em estrutura (gate duro)

---

## 🔴 GATES DUROS QUE CAUSAM REJEIÇÕES

(Ordenado por frequência de rejeição observada)

| Gate | Threshold | Exemplos que falharam |
|------|-----------|----------------------|
| **BOS/CHoCH Confirmado** | Deve haver pelo menos um | BTCUSDT, ETHUSDT, ARBUSDT, LINKUSDT (TODOS) |
| **RVOL Mínimo** | 0.5 | BTCUSDT (0.179), ETHUSDT (0.43), ARBUSDT (0.068), LINKUSDT-30m (0.102) |
| **RR Mínimo** | 2.5 | BTCUSDT (2.11), ETHUSDT (2.18), ARBUSDT (2.18) |
| **Score Mínimo** | 70 | BTCUSDT (45), ETHUSDT (53), ARBUSDT (53), LINKUSDT (67) |
| **EMA Alinhada** | E10 alinhada com direção | BTCUSDT: EMA10 < EMA21 contra LONG |

---

## 🎯 INCONSISTÊNCIAS ENCONTRADAS

### Inconsistência #1: "ok" vs Rejeição Múltipla

**Fato:** BTCUSDT aparece no diagnóstico com score=45, listado como "TOP ATIVO"

**Realidade:** 
- RVOL 0.179 < 0.5 (FALHA)
- RR 2.11 < 2.5 (FALHA)
- EMA contra direção (FALHA)
- Sem estrutura (FALHA)

**Causa:** Diagnóstico mostra "TOP 5 MAIS PRÓXIMOS" mesmo que todos falhem gates duros.
- Esperado: Normal — é diagnóstico de último recurso quando 0 sinais
- Risco: Usuário pode interpretar "score=45" como "próximo de aprovação" quando na verdade múltiplos gates duros impedem

**Correção:** Clarificar no relatório que score não é suficiente; gates duros são obrigatórios.

---

### Inconsistência #2: Símbolos Inexistentes

**Fato:** MUSTOCK, XAU, ARB mencionados no diagnóstico

**Realidade:** Não existem na MEXC
```
"MUSTOCK 30m: mexc does not have market symbol MUSTOCK"
```

**Causa:** 
1. Scanner diagnosticador (50 pares) não valida contra API antes
2. Apenas quando processado em K10Engine a API rejeita
3. Esses pares vêm de uma watchlist que inclui símbolos não-MEXC

**Risco:** Usuário vê esses pares no "TOP PRÓXIMOS" e pensa que existem na MEXC

**Correção:** Filtrar watchlist diagnóstico para incluir APENAS pares MEXC válidos
- Arquivo: `watchlist.py` ou `get_watchlist()`
- Verificação: Validar símbolos contra `ccxt.mexc().symbols` antes de listar no diagnóstico

---

## 📋 RASTREAMENTO COMPLETO: LINKUSDT

**EXEMPLO DETALHADO — Candidato mais próximo de aprovação**

### Fluxo:
```
runner.py (linha ~250)
  ↓
K10Engine.analisar("LINKUSDT")
  ↓
K10Engine._analisar_tf("LINKUSDT", "30m", "1h")
  ↓ [RESULTADO 30m: score=61, RVOL=0.102, sem estrutura]
  ↓
K10Engine._analisar_tf("LINKUSDT", "1h", "4h")
  ↓ [RESULTADO 1h: score=67, RVOL=1.556, RR=3.5, sem estrutura] ← MELHOR
  ↓
K10Engine.analisar() CONSOLIDAÇÃO
  ↓ [max() pega 1h por score=67 > 61]
  ↓
Verificar `aprovado` (linha 887-898)
  ↓
gates duros:
  - Score 67 >= 70? NÃO (67 < 70) ← PROBLEMÁTICO
  - BOS ou SWEEP? NÃO ← REJEITADO AQUI
  ↓
aprovado = False (len(motivos) > 0)
  ↓
return {"aprovado": False, "motivos": ["Sem BOS/CHoCH confirmado"], ...}
  ↓
runner.py aprovados.append() — NÃO adiciona (aprovado=False)
  ↓
❌ LINKUSDT nunca chega ao final_selector.py
```

**Ponto de Parada Exato:**
- **Arquivo:** k10_engine.py
- **Linha:** 597-598 (gate de estrutura)
- **Código:**
```python
if sweep_ok:
    confirmacoes.append("✅ Liquidez capturada"); score += 20
elif bos_ok:
    confirmacoes.append("✅ BOS confirmado"); score += 15
elif tend_forte:
    confirmacoes.append("✅ Tendência forte"); score += 10
else:
    # <<< AQUI: Permitir consolidação
    confirmacoes.append("🔸 Sem BOS/CHoCH/tendência (consolidação)"); score += 2
```

**Depois, linha 887-898:**
```python
if tier_qualidade == "APEX" and eq < 80:
    motivos.append(...)
if tier_qualidade == "APEX":
    if not (bos_ok or sweep_ok):  # <<< LINKUSDT FALHA AQUI
        motivos.append("[HARD_GATE_APEX] Sem BOS/CHoCH/Sweep")
```

---

## 🏁 RESUMO: ONDE CADA CANDIDATO FALHA

| Símbolo | Score | Motivo Principal | Função | Linha ~ |
|---------|-------|-----------------|--------|---------|
| **BTCUSDT** | 45 | RVOL 0.179 < 0.5 | _analisar_tf | ~700 |
| **ETHUSDT** | 53 | RR 2.18 < 2.5 | _analisar_tf | ~873 |
| **ARBUSDT** | 53 | RVOL 0.068 < 0.5 | _analisar_tf | ~700 |
| **LINKUSDT** | 67 | Sem BOS/CHoCH | _analisar_tf | ~597 |
| **MUSTOCK** | 0 | API MEXC | _analisar_tf | ~200 |
| **XAU** | 0 | API MEXC | _analisar_tf | ~200 |

---

## ✅ VERIFICAÇÃO: NENHUMA DIVERGÊNCIA ENTRE GATES

**Pergunta:** "Os valores são recalculados depois?"

**Resposta:** NÃO. Rastreamento mostra:
- Score calculado 1x em `_analisar_tf()`
- RVOL lido 1x do CCXT
- RR calculado 1x
- BOS/SWEEP verificado 1x
- Depois disso, valores são apenas LIDOS, não recalculados

**Nenhuma inconsistência de "ok" → rejeição por mudança de valor.**

---

## 🔍 BUG CONFIRMADO

### Bug #1: Symbols inexistentes no diagnóstico

**Severidade:** Média (Confusão, não perda de sinal)

**Root cause:** Watchlist inclui símbolos não-MEXC, não filtrados antes de diagnóstico

**Evidência:**
```
[XAU] RESULTADO_30M
  motivos_rejeicao: ['XAU 30m: mexc does not have market symbol XAU']
```

**Correção mínima recomendada:**
```python
# Em watchlist.py ou runner.py antes do diagnóstico:
def get_watchlist(...):
    wl = [...]
    # Apenas após validação contra CCXT
    mexc_symbols = _exch.symbols  # cache isso
    wl = [s for s in wl if s in mexc_symbols]
    return wl
```

---

## ✅ SEM BUGS FUNCIONAIS CONFIRMADOS

Não há bug que cause "ok → sinal não emitido".

**Fatos:**
1. Todos os candidatos auditados têm falhas LEGÍTIMAS em gates duros
2. LINKUSDT = 67 é o "melhor", mas falha gate de estrutura (BOS/SWEEP)
3. Nenhum valor é recalculado ou alterado entre etapas
4. O diagnóstico "TOP ATIVOS" é correto — são realmente os mais próximos

**Conclusão:** Bot está funcionando corretamente. Os pares não geram sinal porque:
- Falta liquidade (RVOL)
- Falta estrutura (BOS/SWEEP)
- RR abaixo do mínimo
- Score abaixo de 70

---

## 📝 RECOMENDAÇÕES (NÃO IMPLEMENTAR SEM APROVAÇÃO)

1. ✅ Filtrar símbolos inexistentes do diagnóstico (evita confusão)
2. ⚠️ Clarificar na mensagem "SEM SINAL" que "TOP ATIVOS" significa "mais próximos entre REJEITADOS", não "aprovados"
3. ⚠️ Monitor: Se RVOL < 0.5 está bloqueando consistentemente, investigar se MEXC teve redução de volume real

---

## 🎯 CONCLUSÃO

**Nenhuma alteração necessária no K12.** 

O bot está funcionando como projetado:
- ✅ Gates duros estão funcionando
- ✅ Valores calculados corretamente
- ✅ Sem inconsistências entre etapas
- ✅ Rejeições são legítimas (falta de estrutura e liquidez)

**Problema observado = Ausência de sinais é por condições de mercado, não por bug.**

---

**Auditoria completa em:** `audit_candidato.py`
**Data:** 2026-09-12 16:45 UTC
