import logging
logging.basicConfig(level=logging.INFO)

from CORE.data_providers import create_provider
from ENGINE.market.market_engine import MarketEngine
from ENGINE.scanner.scanner_engine import ScannerEngine

provider = create_provider()
market = MarketEngine()
scanner = ScannerEngine()

# Use scan_multi to test the ProcessPoolExecutor path
pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# Build input dicts
pairs_candles = {}
market_contexts = {}

for pair in pairs:
    tf_candles = provider.get_all_timeframes(pair)
    main_candles = tf_candles.get("1h", next(iter(tf_candles.values())))
    market_ctx = market.analyze(pair=pair, candles=main_candles, timeframe_candles=tf_candles)
    pairs_candles[pair] = tf_candles
    market_contexts[pair] = market_ctx

print("Starting scan_multi...")
results = scanner.scan_multi(pairs_candles=pairs_candles, market_contexts=market_contexts)
print(f"Results: {list(results.keys())}")
for pair, report in results.items():
    print(f"{pair}: signals={len(report.signals)}, errors={len(report.errors)}")
    for err in report.errors:
        print(f"  ERROR: {err}")
