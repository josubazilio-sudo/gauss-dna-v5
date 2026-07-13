# QuantOS Correcoes Minimas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir bugs objetivos de coerencia, risco, FVG, validacao e formatacao de preco no fluxo de sinais do QuantOS.

**Architecture:** Manter a arquitetura atual. As correcoes ficam localizadas nos modulos existentes: `DecisionEngine`, `SignalDecision`, scanner de patterns, servico Telegram e fluxo principal em `main.py`. Nenhum peso, threshold institucional ou regra estrategica nova deve ser introduzida.

**Tech Stack:** Python, pytest/unittest existente, EventBus interno, python-telegram-bot.

---

## File Structure

- Modify: `ENGINE/decision/signal_decision.py` — propagar `risk_reward` do `Signal` para `SignalDecision`.
- Modify: `ENGINE/decision/decision_engine.py` — aceitar regimes reais `trending_up/trending_down` e validar spread quando existir.
- Modify: `ENGINE/scanner/scanner_patterns.py` — corrigir direcao dos FVGs.
- Modify: `SERVICES/telegram/telegram_formatter.py` — formatar preco com precisao dinamica.
- Modify: `main.py` — impedir bypass do `DecisionBrain` e aplicar validacao critica antes de publicar sinal/paper trade.
- Test: `TESTS/test_signal_model.py` — cobrir `risk_reward` em `SignalDecision.from_signal()`.
- Test: `TESTS/test_decision_engine_minimal_fixes.py` — cobrir regime, spread, Brain guard e FVG.
- Test: `TESTS/test_telegram_formatter.py` — cobrir altcoin sem `0.00`.

## Task 1: Propagar Risk Reward No SignalDecision

**Files:**
- Modify: `C:\Users\josue\QuantOS\ENGINE\decision\signal_decision.py:163-199`
- Test: `C:\Users\josue\QuantOS\TESTS\test_signal_model.py`

- [ ] **Step 1: Add failing test**

Append this test to `TESTS/test_signal_model.py` in the existing SignalDecision-related test area:

```python
def test_signal_decision_from_signal_copies_risk_reward(self):
    from ENGINE.decision.signal_decision import SignalDecision

    signal = self._make_signal(risk_reward=2.75)
    decision = SignalDecision.from_signal(signal)

    self.assertEqual(decision.risk_reward, 2.75)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest TESTS/test_signal_model.py -q`

Expected: FAIL because `decision.risk_reward` is `0.0`.

- [ ] **Step 3: Implement minimal fix**

In `ENGINE/decision/signal_decision.py`, inside `SignalDecision.from_signal()`, add `risk_reward=signal.risk_reward,` to the `SignalDecision(...)` constructor near the price fields:

```python
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            risk_reward=signal.risk_reward,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest TESTS/test_signal_model.py -q`

Expected: PASS.

## Task 2: Corrigir Gate De Regime E Spread

**Files:**
- Modify: `C:\Users\josue\QuantOS\ENGINE\decision\decision_engine.py:89-127`
- Test: `C:\Users\josue\QuantOS\TESTS\test_decision_engine_minimal_fixes.py`

- [ ] **Step 1: Create focused tests**

Create `TESTS/test_decision_engine_minimal_fixes.py` with these tests:

```python
import unittest

from ENGINE.decision.decision_engine import DecisionEngine
from ENGINE.scanner.scanner_types import (
    Signal, ScannerScore, SignalClassification, SignalDirection,
    Pattern, PatternType, MarketStructure, StructureType, EntryZone, EntryDetails,
)


def _score():
    return ScannerScore(
        institutional_score=0.90,
        structural_score=0.90,
        market_score=0.90,
        momentum_score=0.90,
        liquidity_score=0.90,
        risk_score=0.20,
        confidence_score=0.90,
        quality_score=0.90,
        entry_score=0.90,
        consensus_score=0.90,
        conviction_score=0.90,
        flow_score=0.90,
        timing_index=0.90,
    )


def _signal(regime="trending_up", direction=SignalDirection.LONG, spread=0.0):
    scores = _score()
    structure = MarketStructure(
        structure_type=StructureType.UPTREND,
        swing_highs=[],
        swing_lows=[],
        structure_strength=0.80,
    )
    patterns = [
        Pattern(PatternType.BOS, direction, "1h", 100.0, 0.90, 0.80, "BOS"),
        Pattern(PatternType.ORDER_BLOCK, direction, "1h", 99.0, 0.90, 0.80, "OB", {"upper": 100.0, "lower": 98.0, "index": 10}),
    ]
    entry_details = EntryDetails(EntryZone(100.0, 98.0, 99.0, 0.90, "inside"), 0.90, True, True)
    entry_details.spread = spread
    return Signal(
        ticker="BTCUSDT",
        timeframe="1h",
        direction=direction,
        entry_price=100.0,
        stop_loss=98.0,
        take_profit_1=104.0,
        take_profit_2=108.0,
        risk_reward=2.0,
        scores=scores,
        classification=SignalClassification.OURO,
        patterns=patterns,
        structure=structure,
        setup="test",
        context="test",
        approval_reasons=[],
        rejection_reasons=[],
        confidence=0.90,
        quality=0.90,
        rvol=2.0,
        adx=40.0,
        atr_value=1.0,
        regime=regime,
        entry_details=entry_details,
        structure_strength=0.80,
    )


class TestDecisionEngineMinimalFixes(unittest.TestCase):
    def test_trending_up_allows_long_trend_gate(self):
        sd = DecisionEngine.evaluate_signal(
            _signal(regime="trending_up", direction=SignalDirection.LONG),
            entry_details=_signal().entry_details,
            highs=[101.0] * 20,
            lows=[99.0] * 20,
            closes=[100.0] * 20,
        )
        self.assertTrue(sd.trend_ok)
        self.assertNotEqual(sd.reject_reason, "Trend desfavoravel (trending_up)")

    def test_spread_above_hard_max_is_rejected_when_available(self):
        sig = _signal(spread=0.01)
        sd = DecisionEngine.evaluate_signal(
            sig,
            entry_details=sig.entry_details,
            highs=[101.0] * 20,
            lows=[99.0] * 20,
            closes=[100.0] * 20,
        )
        self.assertFalse(sd.spread_ok)
        self.assertIn("Spread", sd.reject_reason)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest TESTS/test_decision_engine_minimal_fixes.py -q`

Expected: FAIL on spread because current code always sets `spread_ok=True`. Trend may also fail depending on later gates; the assertion must prove it is not rejected by trend.

- [ ] **Step 3: Implement regime and spread fixes**

In `ENGINE/decision/decision_engine.py`, replace the spread gate with:

```python
        # ---- GATE 5: Spread ----
        details = getattr(signal, 'entry_details', None)
        sp = getattr(details, 'spread', None) if details is not None else None
        if sp is not None and sp > HARD_MAX_SPREAD:
            sd.approved = False
            sd.reject_reason = f"Spread {sp:.4f} > {HARD_MAX_SPREAD}"
            sd.spread_ok = False
            sd.market_ok = False
            _log_result(sd.trace_id, sd.symbol, sd.direction, sd)
            return sd
        sd.spread_ok = True
```

In the trend gate, replace the `aligned` calculation with:

```python
        up_regimes = {"uptrend", "trending_up", "bullish"}
        down_regimes = {"downtrend", "trending_down", "bearish"}
        aligned = (regime_lower in up_regimes and dir_lower == "long") or \
                  (regime_lower in down_regimes and dir_lower == "short")
```

Replace `elif regime_lower in ("uptrend", "downtrend"):` with:

```python
        elif regime_lower in up_regimes or regime_lower in down_regimes:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest TESTS/test_decision_engine_minimal_fixes.py -q`

Expected: PASS.

## Task 3: Corrigir Direcao Do FVG

**Files:**
- Modify: `C:\Users\josue\QuantOS\ENGINE\scanner\scanner_patterns.py:162-208`
- Test: `C:\Users\josue\QuantOS\TESTS\test_decision_engine_minimal_fixes.py`

- [ ] **Step 1: Add failing FVG tests**

Append to `TESTS/test_decision_engine_minimal_fixes.py`:

```python
from datetime import datetime
from ENGINE.market.market_types import Candle
from ENGINE.scanner.scanner_patterns import detect_fvg


class TestFvgDirection(unittest.TestCase):
    def test_gap_up_is_long_fvg(self):
        candles = [
            Candle(datetime.utcnow(), 100.0, 101.0, 99.0, 100.0, 1000.0),
            Candle(datetime.utcnow(), 102.0, 103.0, 101.5, 102.5, 1000.0),
            Candle(datetime.utcnow(), 104.0, 105.0, 103.0, 104.0, 1000.0),
        ]
        patterns = detect_fvg(candles, "1h")
        self.assertEqual(patterns[0].direction, SignalDirection.LONG)

    def test_gap_down_is_short_fvg(self):
        candles = [
            Candle(datetime.utcnow(), 100.0, 101.0, 99.0, 100.0, 1000.0),
            Candle(datetime.utcnow(), 98.0, 98.5, 97.0, 97.5, 1000.0),
            Candle(datetime.utcnow(), 96.0, 96.5, 95.0, 95.5, 1000.0),
        ]
        patterns = detect_fvg(candles, "1h")
        self.assertEqual(patterns[0].direction, SignalDirection.SHORT)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest TESTS/test_decision_engine_minimal_fixes.py -q`

Expected: FAIL because current FVG directions are inverted.

- [ ] **Step 3: Implement minimal FVG fix**

In `ENGINE/scanner/scanner_patterns.py`:

For `if prev.low > nxt.high:`, change `direction=SignalDirection.LONG` to:

```python
                    direction=SignalDirection.SHORT,
```

For `if prev.high < nxt.low:`, change `direction=SignalDirection.SHORT` to:

```python
                    direction=SignalDirection.LONG,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest TESTS/test_decision_engine_minimal_fixes.py -q`

Expected: PASS.

## Task 4: Impedir Bypass Do DecisionBrain

**Files:**
- Modify: `C:\Users\josue\QuantOS\main.py:314-325`
- Test: manual review plus existing pipeline tests; this is flow-level and should be kept minimal.

- [ ] **Step 1: Inspect current block**

Confirm `main.py` has this behavior:

```python
            if brain_state == DecisionState.EXECUTAR:
                sd.approved = True
                sd.reject_reason = "APROVADO — Decision Brain EXECUTAR"
```

- [ ] **Step 2: Implement guard without changing strategy thresholds**

Replace the block with:

```python
            hard_gate_approved = sd.approved

            if brain_state == DecisionState.EXECUTAR:
                if hard_gate_approved:
                    sd.approved = True
                    sd.reject_reason = "APROVADO — Decision Brain EXECUTAR"
                else:
                    sd.approved = False
                    sd.reject_reason = f"REJEITADO — Hard gates bloquearam antes do Brain: {sd.reject_reason}"
            elif brain_state == DecisionState.PRONTO:
                sd.approved = False
                sd.reject_reason = f"PRONTO — Aguardar confirmacao: {brain_just[:100]}"
            elif brain_state == DecisionState.OBSERVACAO:
                sd.approved = False
                sd.reject_reason = f"OBSERVACAO — Riscos identificados: {brain_just[:100]}"
            else:
                sd.approved = False
                sd.reject_reason = f"REJEITADO — Contra-tese superior: {brain_just[:100]}"
```

- [ ] **Step 3: Run syntax/import check**

Run: `python -m py_compile main.py`

Expected: no output and exit code 0.

## Task 5: Validacao Critica Antes De Publicar E Abrir Paper Trade

**Files:**
- Modify: `C:\Users\josue\QuantOS\main.py`

- [ ] **Step 1: Add local helper methods to `QuantOSApp`**

Add these methods inside `class QuantOSApp`, before `_process_pair`:

```python
    def _decision_has_valid_prices(self, sd: SignalDecision) -> bool:
        return (
            sd.entry_price > 0 and
            sd.stop_loss > 0 and
            sd.take_profit_1 > 0 and
            sd.risk_reward > 0
        )

    def _decision_has_required_flags(self, sd: SignalDecision) -> bool:
        required = [
            sd.market_ok, sd.trend_ok, sd.structure_ok, sd.entry_zone_ok,
            sd.entry_score_ok, sd.consensus_ok, sd.quality_ok,
            sd.confidence_ok, sd.risk_ok, sd.institutional_ok,
            sd.rvol_ok, sd.adx_ok, sd.flow_ok, sd.timing_ok,
            sd.liquidity_ok, sd.structural_ok, sd.conviction_ok, sd.rr_ok,
        ]
        return all(required)

    def _decision_ready_for_publication(self, sd: SignalDecision) -> bool:
        return sd.approved and self._decision_has_valid_prices(sd) and self._decision_has_required_flags(sd)
```

- [ ] **Step 2: Use helper before publishing `decision.made`**

In `main.py:372`, change:

```python
            if sd.approved and audit_res.passed:
```

to:

```python
            if self._decision_ready_for_publication(sd) and audit_res.passed:
```

- [ ] **Step 3: Use helper before paper trade entry**

In `main.py:480`, change:

```python
                    if sd.approved:
```

to:

```python
                    if self._decision_ready_for_publication(sd):
```

- [ ] **Step 4: Run syntax check**

Run: `python -m py_compile main.py`

Expected: no output and exit code 0.

## Task 6: Formatacao Dinamica De Preco No Telegram

**Files:**
- Modify: `C:\Users\josue\QuantOS\SERVICES\telegram\telegram_formatter.py:45-90`
- Test: `C:\Users\josue\QuantOS\TESTS\test_telegram_formatter.py`

- [ ] **Step 1: Add failing formatter test**

Append to `TESTS/test_telegram_formatter.py`:

```python
    def test_low_price_asset_does_not_render_zero(self):
        signal = self._make_signal(
            entry_price=0.00001234,
            stop_loss=0.00001100,
            take_profit_1=0.00001500,
            take_profit_2=0.00001800,
            risk_reward=2.0,
        )
        formatted = self.formatter.format_signal(signal)
        self.assertIn("0.00001234", formatted)
        self.assertNotIn("Entrada: $0.00", formatted)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest TESTS/test_telegram_formatter.py -q`

Expected: FAIL because current formatter uses `:.2f`.

- [ ] **Step 3: Implement dynamic price formatter**

In `SERVICES/telegram/telegram_formatter.py`, add helper after `_float()`:

```python
def _price(value: float) -> str:
    if value >= 1:
        return f"{value:.2f}"
    if value >= 0.01:
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return f"{value:.8f}".rstrip("0").rstrip(".")
```

Then replace price lines:

```python
        lines.append(f"\U0001f4b0 Entrada: ${_price(entry_price)}")
        lines.append(f"\U0001f6d1 Stop: ${_price(stop_loss)}")
        lines.append(f"\U0001f3af TP1: ${_price(tp1)}")
        lines.append(f"\U0001f3af TP2: ${_price(tp2)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest TESTS/test_telegram_formatter.py -q`

Expected: PASS.

## Task 7: Final Verification

**Files:**
- All modified files from Tasks 1-6.

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest TESTS/test_signal_model.py TESTS/test_decision_engine_minimal_fixes.py TESTS/test_telegram_formatter.py TESTS/test_risk_stop_loss.py -q`

Expected: PASS.

- [ ] **Step 2: Run syntax checks**

Run: `python -m py_compile main.py ENGINE/decision/signal_decision.py ENGINE/decision/decision_engine.py ENGINE/scanner/scanner_patterns.py SERVICES/telegram/telegram_formatter.py`

Expected: no output and exit code 0.

- [ ] **Step 3: Review diff manually**

Run: `git diff -- main.py ENGINE/decision/signal_decision.py ENGINE/decision/decision_engine.py ENGINE/scanner/scanner_patterns.py SERVICES/telegram/telegram_formatter.py TESTS/test_signal_model.py TESTS/test_decision_engine_minimal_fixes.py TESTS/test_telegram_formatter.py`

Expected: only the approved minimal corrections are present; no score weights, thresholds, or unrelated strategy logic changed.

## Self-Review

Spec coverage:

- Regime mapping: Task 2.
- `risk_reward` propagation: Task 1.
- Brain no-bypass: Task 4.
- FVG direction: Task 3.
- Spread validation: Task 2.
- Validation before publish/paper trade: Task 5.
- Telegram dynamic price formatting: Task 6.

No placeholders remain. Type names match existing code: `SignalDecision`, `Signal`, `PatternType`, `SignalDirection`, `EntryDetails`, `EntryZone`, and existing `main.py` flow.
