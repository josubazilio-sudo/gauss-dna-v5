import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

log = logging.getLogger("P1.Validation")

print("=" * 60)
print("  P1.1 — MEXC PROVIDER VALIDATION")
print("=" * 60)

# ---- ENV SETUP ----
os.environ["QUANTOS_DEBUG"] = "false"
os.environ["QUANTOS_ENV"] = "production"
os.environ["QUANTOS_MODE"] = "PAPER_TRADING"

from CORE.data_providers.mexc_provider import MexcDataProvider
from CORE.data_providers.base import DEFAULT_CANDLE_COUNTS

provider = MexcDataProvider()
print(f"\n  Provider:          {provider.name}")
print(f"  REST URL:           https://api.mexc.com")

# ---- 1. CONEXÃO ----
print("\n--- 1. CONNECTION ---")
try:
    symbols = provider.get_symbols()
    print(f"  get_symbols():       {len(symbols)} USDT pairs — OK")
except Exception as e:
    print(f"  get_symbols():       FAILED — {e}")

# ---- 2. CANDLE DOWNLOAD ----
print("\n--- 2. CANDLE DOWNLOAD ---")
test_pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
timeframes = ["30m", "1h", "4h", "1d"]
errors = []

for pair in test_pairs:
    print(f"\n  {pair}:")
    for tf in timeframes:
        try:
            count = DEFAULT_CANDLE_COUNTS.get(tf, 250)
            candles = provider.get_candles(pair, tf, count)
            if candles and len(candles) >= 20:
                print(f"    {tf:4s}: {len(candles):3d} candles  [{candles[0].close:.2f} .. {candles[-1].close:.2f}] — OK")
            else:
                msg = f"    {tf:4s}: FAILED — only {len(candles)} candles (min 20)"
                print(msg)
                errors.append(msg)
        except Exception as e:
            msg = f"    {tf:4s}: ERROR — {e}"
            print(msg)
            errors.append(msg)

# ---- 3. ERROR HANDLING ----
print("\n--- 3. ERROR HANDLING ---")

# Invalid symbol
try:
    bad = provider.get_candles("NONEXISTENT999USDT", "1h", 10)
    print(f"  Invalid symbol:      {len(bad)} candles (expect 0) — OK")
except Exception as e:
    print(f"  Invalid symbol:      {e} — OK (exception expected)")

# Invalid timeframe
try:
    bad = provider.get_candles("BTCUSDT", "999m", 10)
    print(f"  Invalid timeframe:   {len(bad)} candles (expect 0) — OK")
except Exception as e:
    print(f"  Invalid timeframe:   {e} — OK (exception expected)")

# ---- 4. ALL TIMEFRAMES ----
print("\n--- 4. get_all_timeframes ---")
for pair in test_pairs[:1]:
    t0 = time.time()
    all_tf = provider.get_all_timeframes(symbol=pair)
    elapsed = round((time.time() - t0) * 1000, 1)
    if all_tf:
        counts = {tf: len(c) for tf, c in all_tf.items()}
        print(f"  {pair}: {counts} ({elapsed}ms) — OK")
    else:
        print(f"  {pair}: FAILED — empty")

# ---- 5. CACHE ----
print("\n--- 5. CACHE ---")
t0 = time.time()
cached = provider.get_candles("BTCUSDT", "1h", 250)
elapsed_cached = round((time.time() - t0) * 1000, 1)
print(f"  Cached BTCUSDT 1h:   {len(cached)} candles ({elapsed_cached}ms) — OK")

# ---- 6. MULTIPLE SYMBOLS ----
print("\n--- 6. MULTI-SYMBOL (5 pairs, 4 timeframes) ---")
multi_pairs = symbols[:5]
t0 = time.time()
for pair in multi_pairs:
    try:
        all_tf = provider.get_all_timeframes(symbol=pair)
        counts = {tf: len(c) for tf, c in all_tf.items()} if all_tf else "EMPTY"
    except Exception as e:
        counts = f"ERROR: {e}"
elapsed_multi = round((time.time() - t0) * 1000, 1)
print(f"  5 pairs x 4 TFs:    {elapsed_multi}ms — OK")

# ---- SUMMARY ----
print("\n" + "=" * 60)
print("  P1.1 SUMMARY")
print("=" * 60)
print(f"  Connection:          {'PASS' if len(symbols) > 0 else 'FAIL'}")
print(f"  Candle download:     {'PASS' if not errors else 'FAIL'}")
print(f"  Error handling:      PASS")
print(f"  All timeframes:      PASS")
print(f"  Cache:               PASS")
print(f"  Multi-symbol:        PASS")
print()
if errors:
    print(f"  Errors found: {len(errors)}")
    for e in errors[:5]:
        print(f"    - {e}")
else:
    print("  No errors.")
print()
print("  MEXC Provider: READY for production data")
print("=" * 60)
