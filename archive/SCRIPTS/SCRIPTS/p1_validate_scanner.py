import logging
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["QUANTOS_DEBUG"] = "false"
os.environ["QUANTOS_ENV"] = "production"
os.environ["QUANTOS_MODE"] = "PAPER_TRADING"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("P1.2")

from CORE.data_providers.mexc_provider import MexcDataProvider
from ENGINE.market.market_engine import MarketEngine
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.scanner.scanner_config import (
    QUALITY_GATE_MIN_SCORE, QUALITY_GATE_CONFIDENCE_MIN, QUALITY_GATE_RISK_MAX,
    CONSENSUS_MINIMUM_SCORE,
)
from ENGINE.scanner.scanner_types import SignalClassification, ScanReport

errors = []

def report_error(stage, location, detail, impact):
    errors.append({
        "stage": stage,
        "location": location,
        "detail": detail,
        "impact": impact,
    })
    log.error(f"[{stage}] {location}: {detail} | Impact: {impact}")

print("=" * 60)
print("  P1.2 — SCANNER VALIDATION (MEXC DATA)")
print("=" * 60)

provider = MexcDataProvider()
market = MarketEngine()
scanner = ScannerEngine()

print(f"\n  Provider: {provider.name}")
print(f"  Thresholds: QG={QUALITY_GATE_MIN_SCORE}, Conf={QUALITY_GATE_CONFIDENCE_MIN}, Risk={QUALITY_GATE_RISK_MAX}")
print(f"  Consensus min: {CONSENSUS_MINIMUM_SCORE}")

# ---- DISCOVERY ----
print("\n--- 1. DISCOVERY ---")
try:
    symbols = provider.get_symbols()
    print(f"  Symbols: {len(symbols)} USDT pairs — OK")
except Exception as e:
    report_error("DISCOVERY", "provider.get_symbols()", str(e), "Nenhum par descoberto")

# ---- SCAN INDIVIDUAL PAIRS ----
print("\n--- 2. SCAN (10 pairs) ---")
test_pairs = symbols[:10]
scan_results = {}

for pair in test_pairs:
    pair_start = time.time()
    try:
        tf_candles = provider.get_all_timeframes(symbol=pair)
        if not tf_candles:
            report_error("SCAN", f"{pair}", "get_all_timeframes returned empty", "Sinal perdido")
            continue

        main_candles = tf_candles.get("1h", next(iter(tf_candles.values())))
        market_ctx = market.analyze(
            pair=pair, candles=main_candles, timeframe_candles=tf_candles,
        )
        if not market_ctx:
            report_error("SCAN", f"{pair}", "market.analyze returned None", "Sinal perdido")
            continue

        report = scanner.scan(
            pair=pair, candles=tf_candles, market_ctx=market_ctx, spread=0.001,
        )

        elapsed = round((time.time() - pair_start) * 1000, 1)
        scan_results[pair] = report

        if report.errors:
            for err in report.errors[:3]:
                report_error("SCAN", f"{pair}", err, "Sinal parcialmente perdido neste timeframe")

        status = "HAS SIGNALS" if report.signals else "NO SIGNALS"
        classifications = [s.classification.name for s in report.signals] if report.signals else []
        print(f"  {pair:<12}: {len(report.signals):2d} signals, {len(report.errors)} errors, {elapsed:7.1f}ms [{', '.join(classifications[:3])}]")

    except Exception as e:
        tb = traceback.format_exc().split('\n')[-3]
        report_error("SCAN", f"{pair}", f"{e} at {tb}", "Par inteiro perdido")
        print(f"  {pair:<12}: CRASHED — {e}")

# ---- SCAN SUMMARY ----
total_signals = sum(len(r.signals) for r in scan_results.values())
approved = sum(1 for r in scan_results.values() for s in r.signals if s.classification != SignalClassification.REPROVADO)
print(f"\n  Total signals: {total_signals}")
print(f"  Approved:      {approved}")
print(f"  Pairs scanned: {len(scan_results)}/{len(test_pairs)}")

# ---- CONSENSUS ----
print("\n--- 3. CONSENSUS (multi-TF) ---")
from ENGINE.consensus.consensus_engine import ConsensusEngine
consensus = ConsensusEngine()

for pair in test_pairs[:3]:
    report = scan_results.get(pair)
    if not report or len(report.signals) < 2:
        continue
    directions = {s.timeframe: s.direction for s in report.signals}
    tf_scores = {s.timeframe: s.scores.quality_score for s in report.signals}
    try:
        c = consensus.compute(directions, tf_scores)
        print(f"  {pair:<12}: score={c.consensus_score:.2f}, dir={c.final_direction.value}, dissenting={c.dissenting_timeframes}")
    except Exception as e:
        report_error("CONSENSUS", f"{pair}", str(e), "Consenso nao calculado")

# ---- QUALITY GATE ----
print("\n--- 4. QUALITY GATE (sample) ---")
from ENGINE.scanner.quality_gate import apply_quality_gate, format_gate_report
from ENGINE.scanner.scanner_scoring import compute_all_scanner_scores, classify_signal

for pair in test_pairs[:3]:
    report = scan_results.get(pair)
    if not report:
        continue
    for signal in report.signals[:2]:
        print(f"  {pair} {signal.timeframe}: quality={signal.scores.quality_score:.2f}, confidence={signal.scores.confidence_score:.2f}, risk={signal.scores.risk_score:.2f}, class={signal.classification.name}")

# ---- PUBLISHER (EventBus test) ----
print("\n--- 5. PUBLISHER (EventBus) ---")
from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from CORE.events.publishers import Publisher
bus = EventBus()
publisher = Publisher(bus)
received = []
def handler(event):
    received.append(event.type)
bus.subscribe(EventTypes.SIGNAL_GENERATED, handler)
for pair, report in list(scan_results.items())[:3]:
    for signal in report.signals:
        publisher.signal_generated(signal, {"test": True})
print(f"  Events published: {len(received)} signal.generated events — OK" if received else "  No events published")

# ---- ERROR SUMMARY ----
print("\n" + "=" * 60)
print("  P1.2 ERROR SUMMARY")
print("=" * 60)
if errors:
    for e in errors:
        print(f"  [{e['stage']}] {e['location']}: {e['detail']}")
        print(f"    Impact: {e['impact']}")
else:
    print("  Zero errors across all stages.")
print(f"\n  Total errors: {len(errors)}")
print("=" * 60)
