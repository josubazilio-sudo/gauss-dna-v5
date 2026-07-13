"""
audit_signal_propagation.py — Auditoria da propagação do objeto Signal

Rastreia o Signal do builder até o Telegram, registrando cada campo
em cada etapa para identificar onde os dados são perdidos.
"""

import logging
import os
import re
import sys
import json
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING, format="%(message)s")

# =========================================================================
# ETAPA 1: Signal Builder — o que é construído
# =========================================================================
print("=" * 70)
print("  ETAPA 1 — SIGNAL BUILDER: campos no dataclass")
print("=" * 70)

from ENGINE.scanner.scanner_types import Signal, ScannerScore

from dataclasses import fields as dc_fields
sig_fields = [f.name for f in dc_fields(Signal)]
score_fields = [f.name for f in dc_fields(ScannerScore)]

print(f"\n  Signal fields ({len(sig_fields)}):")
for f in sorted(sig_fields):
    print(f"    {f}")

print(f"\n  ScannerScore fields ({len(score_fields)}):")
for f in sorted(score_fields):
    print(f"    {f}")

# =========================================================================
# ETAPA 2: to_dict — o que é serializado
# =========================================================================
print("\n" + "=" * 70)
print("  ETAPA 2 — TO_DICT: campos que saem na serializacao")
print("=" * 70)

from ENGINE.scanner.scanner_types import (
    SignalDirection, SignalClassification, PatternType, StructureType,
    MarketStructure, Pattern,
)
from datetime import datetime

# Build a minimal signal to inspect to_dict()
dummy_score = ScannerScore(
    institutional_score=0.85,
    structural_score=0.75,
    market_score=0.65,
    momentum_score=0.60,
    liquidity_score=0.55,
    risk_score=0.30,
    confidence_score=0.70,
    quality_score=0.80,
)
dummy_structure = MarketStructure(
    structure_type=StructureType.UPTREND,
    swing_highs=[],
    swing_lows=[],
    structure_strength=0.6,
    mm50=51000.0,
    mm200=49000.0,
    vwap=50500.0,
)
dummy_pattern = Pattern(
    type=PatternType.BOS,
    direction=SignalDirection.LONG,
    price=50000.0,
    timeframe="1h",
    confidence=0.8,
    strength=0.7,
    description="BOS confirmado",
    metadata={},
)
sig = Signal(
    ticker="BTCUSDT",
    timeframe="1h",
    direction=SignalDirection.LONG,
    entry_price=50000.0,
    stop_loss=49000.0,
    take_profit_1=52000.0,
    take_profit_2=54000.0,
    risk_reward=2.0,
    scores=dummy_score,
    classification=SignalClassification.OURO,
    patterns=[dummy_pattern],
    structure=dummy_structure,
    setup="Test setup",
    context="Test context",
    approval_reasons=[],
    rejection_reasons=[],
    confidence=0.80,
    quality=0.80,
    regime="trending",
    entry_score=75.0,
)

d = sig.to_dict()
print(f"\n  to_dict keys ({len(d)}):")
for k in sorted(d.keys()):
    v = d[k]
    if isinstance(v, (list, dict)):
        print(f"    {k}: ({type(v).__name__}, len={len(v)})")
    else:
        print(f"    {k}: {v!r}")

# =========================================================================
# ETAPA 3: Campos esperados pelo Formatter vs campos disponíveis
# =========================================================================
print("\n" + "=" * 70)
print("  ETAPA 3 — TELEGRAM FORMATTER: campos que TENTA acessar")
print("=" * 70)

from SERVICES.telegram.signal_compat import wrap_signal

wrapped = wrap_signal(d)

formatter_accesses = {
    "signal.ticker": ["ticker"],
    "signal.timeframe": ["timeframe"],
    "signal.direction.value": ["direction"],
    "signal.quality": ["quality"],
    "signal.entry_zone": ["entry_zone"],
    "signal.market_regime": ["market_regime"],
    "signal.regime (alternative)": ["regime"],
    "signal.dist_ob": ["dist_ob"],
    "signal.dist_fvg": ["dist_fvg"],
    "signal.validity_time": ["validity_time"],
    "signal.entry_price": ["entry_price"],
    "signal.stop_loss": ["stop_loss"],
    "signal.take_profit_1": ["take_profit_1", "take_profit", "tp"],
    "signal.approval_reasons": ["approval_reasons"],
    "signal.signal_id": ["signal_id"],
    "scores.entry_score": ["entry_score"],
    "scores.consensus_score": ["consensus_score"],
    "scores.institutional_score": ["institutional_score"],
    "scores.structural_score": ["structural_score"],
    "scores.liquidity_score": ["liquidity_score"],
    "scores.market_score": ["market_score"],
    "scores.confidence_score": ["confidence_score"],
    "scores.quality_score": ["quality_score"],
}

# Separate checks: direct fields vs scores (nested)
scores_dict = d.get("scores", {})

print(f"\n  {'Acesso no Formatter':<35} {'Chave procurada':<25} {'Em to_dict?':<12}")
print(f"  {'-'*35} {'-'*25} {'-'*12}")

for access, expected in formatter_accesses.items():
    if access.startswith("scores."):
        in_dict = any(k in scores_dict for k in expected)
    else:
        in_dict = any(k in d for k in expected)
    print(f"  {access:<35} {str(expected[0]):<25} {'OK' if in_dict else 'AUSENTE':<12}")

# =========================================================================
# ETAPA 4: Check entry_score location
# =========================================================================
print("\n" + "=" * 70)
print("  ETAPA 4 — CAMPO entry_score: onde ele existe?")
print("=" * 70)

print(f"\n  Signal tem entry_score:    {'entry_score' in sig_fields}")
print(f"  ScannerScore tem entry_score: {'entry_score' in score_fields}")
print(f"  signal.entry_score = {sig.entry_score!r}")
print(f"  signal.scores tem entry_score: {hasattr(dummy_score, 'entry_score')}")
print(f"  to_dict tem 'entry_score': {'entry_score' in d}")
print(f"  to_dict['scores'] tem entry_score: {'entry_score' in d.get('scores', {})}")
print(f"  to_dict['scores'] keys: {sorted(d.get('scores', {}).keys())}")
print(f"  to_dict tem 'entry_score' direto: {'entry_score' in d}")

# Where does entry_score END UP in to_dict?
print(f"\n  Entry score final location:")
for k, v in d.items():
    if isinstance(v, dict) and "entry_score" in v:
        print(f"    Nested in to_dict[{k!r}]['entry_score'] = {v['entry_score']}")
    elif k == "entry_score":
        print(f"    Direct to_dict['entry_score'] = {v}")

# =========================================================================
# ETAPA 5: UTF-8 check on approval_reasons
# =========================================================================
print("\n" + "=" * 70)
print("  ETAPA 5 — UTF-8: cadeia de formatacao")
print("=" * 70)

# Check scanner_signal.py encoding
with open("ENGINE/scanner/scanner_signal.py", "rb") as f:
    raw = f.read()

# Check encoding of specific strings
import re
# Find all strings containing non-ASCII in the file
non_ascii_lines = []
for i, line in enumerate(raw.decode("utf-8", errors="replace").split("\n"), 1):
    for c in line:
        if ord(c) > 127:
            non_ascii_lines.append((i, line.strip()))
            break

print(f"\n  scanner_signal.py: {len(non_ascii_lines)} linhas com caracteres nao-ASCII:")
for ln, text in non_ascii_lines[:15]:
    print(f"    L{ln}: {text[:100]}")

# Verify if Python strings survive through the pipeline
print(f"\n  Python default encoding: {sys.getdefaultencoding()}")
print(f"  Filesystem encoding: {sys.getfilesystemencoding()}")

# Test actual propagation
sig.approval_reasons = ["Tendência alinhada", "Confiança: 0.80"]
d2 = sig.to_dict()
w2 = wrap_signal(d2)
reasons = getattr(w2, "approval_reasons", [])
print(f"\n  approval_reasons after wrap_signal: {reasons}")
if reasons:
    print(f"  reason[0] repr: {reasons[0]!r}")
    print(f"  reason[0] bytes: {reasons[0].encode('utf-8')!r}")
else:
    print("  (empty)")

print("\n" + "=" * 70)
print("  AUDITORIA CONCLUIDA")
print("=" * 70)
