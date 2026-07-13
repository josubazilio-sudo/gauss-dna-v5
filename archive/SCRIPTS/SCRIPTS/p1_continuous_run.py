import logging, os, signal, sys, time, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["QUANTOS_DEBUG"] = "false"
os.environ["QUANTOS_ENV"] = "production"
os.environ["QUANTOS_MODE"] = "PAPER_TRADING"

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from CORE.data_providers import create_provider
from ENGINE.market.market_engine import MarketEngine
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.diagnostic.engine import DiagnosticEngine
from CORE.events.event_bus import EventBus
from CORE.events.publishers import Publisher
from CORE.execution.mode_manager import ExecutionModeManager
from BOTS.mexc.bot_config import BotConfig
from BOTS.mexc.bot_engine import BotEngine
from SERVICES.telegram.telegram_service import TelegramService
from ENGINE.mid.mid_dashboard import MIDashboard

TIMEFRAMES = ["30m", "1h", "4h", "1d"]
QUOTE_ASSETS = ["USDT"]

provider = create_provider()
print(f"Provider: {provider.name}", flush=True)
all_symbols = provider.get_symbols()
symbols = [s for s in all_symbols if any(s.endswith(qa) for qa in QUOTE_ASSETS)][:10]
print(f"Symbols: {len(symbols)}", flush=True)

bus = EventBus()
publisher = Publisher(bus)
diag = DiagnosticEngine()
market = MarketEngine()
scanner = ScannerEngine()
mid = MIDashboard()
mode = ExecutionModeManager()
config = BotConfig(dry_run=not mode.is_live())
bot = BotEngine(config=config, event_bus=bus, market_engine=market, scanner_engine=scanner)
telegram = TelegramService(bus)

print(f"Mode: {mode.mode_name}, DryRun: {config.dry_run}, QG min: {config.min_quality}", flush=True)

total_crashes = 0
total_scan_errors = 0
total_signals_raw = 0
total_approved = 0

for cycle in range(3):
    print(f"--- Cycle {cycle+1} ---", flush=True)
    diag.start_cycle(cycle + 1)
    start = time.time()

    for pair in symbols:
        try:
            tf_candles = provider.get_all_timeframes(symbol=pair)
            if not tf_candles:
                continue
            main_candles = tf_candles.get("1h", next(iter(tf_candles.values())))
            market_ctx = market.analyze(pair=pair, candles=main_candles, timeframe_candles=tf_candles)
            report = scanner.scan(pair=pair, candles=tf_candles, market_ctx=market_ctx, spread=0.001)
            total_signals_raw += len(report.signals)
            if report.errors:
                total_scan_errors += len(report.errors)
                for e in report.errors[:3]:
                    print(f"  ERR {pair}: {e}", flush=True)
            for sig in report.signals:
                if sig.classification.name != "REPROVADO":
                    total_approved += 1
                    publisher.signal_generated(sig.to_dict())
                    print(f"  SIGNAL {pair} {sig.timeframe} {sig.classification.name} Q={sig.scores.quality_score:.3f}", flush=True)
        except Exception as e:
            total_crashes += 1
            print(f"  CRASH {pair}: {e}", flush=True)
            traceback.print_exc()

    elapsed = round((time.time() - start) * 1000, 1)
    diag.end_cycle(elapsed)
    print(f"  Cycle {cycle+1}: {elapsed}ms, signals={total_signals_raw}, approved={total_approved}", flush=True)
    if cycle < 2:
        time.sleep(5)

print(f"\nRESULT: 3 cycles completed", flush=True)
print(f"  Pairs scanned: {len(symbols)} per cycle", flush=True)
print(f"  Total signals: {total_signals_raw}", flush=True)
print(f"  Total approved: {total_approved}", flush=True)
print(f"  Scan errors: {total_scan_errors}", flush=True)
print(f"  Crashes (uncaught): {total_crashes}", flush=True)
if total_crashes == 0 and total_scan_errors == 0:
    print("  STATUS: ✅ Zero crashes, zero scan errors", flush=True)
else:
    print("  STATUS: ❌ Issues found", flush=True)
