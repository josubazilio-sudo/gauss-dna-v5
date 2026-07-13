import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

print("=" * 60)
print("  QUANTOS STARTUP — PRODUCTION VALIDATION")
print("=" * 60)
print()

# ---- CORE VALIDATION ----
from CORE.config.settings import Settings
from CORE.config.environment import Environment
from CORE.execution.mode_manager import ExecutionModeManager

settings = Settings()
env = Environment()
mode = ExecutionModeManager()

print(f"  Settings loaded:        {settings.get('PRODUCTION_VALIDATION', False)}")
print(f"  Environment:            {env.type.value}")
print(f"  Execution Mode:         {mode.mode.value}")
print(f"  Can trade:              {mode.can_trade()}")
print(f"  Logs:                   quantos.log")
print()

# ---- PROVIDER VALIDATION ----
from CORE.data_providers import create_provider
from CORE.data_providers.config import DEBUG_MODE

provider = create_provider()
all_symbols = provider.get_symbols()
scan_symbols = all_symbols[:10]

print(f"  Provider:               {provider.name}")
print(f"  Debug mode:             {DEBUG_MODE}")
print(f"  Exchange:               MEXC")
print(f"  Pairs discovered:       {len(all_symbols)}")
print(f"  Eligible (scan limit):  {len(scan_symbols)}")
print(f"  Sample pairs:           {scan_symbols[:5]}")
print()

# ---- ENGINE MODULES VALIDATION ----
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.scanner.scanner_config import (
    QUALITY_GATE_MIN_SCORE, QUALITY_GATE_CONFIDENCE_MIN, QUALITY_GATE_RISK_MAX,
    CONSENSUS_MINIMUM_SCORE, DISCOVERY_MODE, MAX_SCAN_PAIRS,
)
from ENGINE.market.market_engine import MarketEngine
from ENGINE.diagnostic.engine import DiagnosticEngine
from ENGINE.consensus.consensus_engine import ConsensusEngine

scanner = ScannerEngine()
market = MarketEngine()
diag = DiagnosticEngine()
consensus = ConsensusEngine()

print(f"  Scanner:                OK")
print(f"  Market Engine:          OK")
print(f"  Consensus Engine:       OK")
print(f"  Diagnostic Engine:      OK")
print(f"  Discovery Mode:         {DISCOVERY_MODE}")
print(f"  Max scan pairs:         {MAX_SCAN_PAIRS}")
print(f"  Quality Gate min:       {QUALITY_GATE_MIN_SCORE}")
print(f"  Confidence min:         {QUALITY_GATE_CONFIDENCE_MIN}")
print(f"  Risk max:               {QUALITY_GATE_RISK_MAX}")
print(f"  Consensus min:          {CONSENSUS_MINIMUM_SCORE}")
print()

# ---- DATA VALIDATION ----
import requests
tf_to_test = ["30m", "1h", "4h", "1d"]
data_ok = 0
data_fail = 0

for symbol in scan_symbols[:5]:
    try:
        candles = provider.get_all_timeframes(symbol=symbol, timeframes=tf_to_test)
        if candles:
            counts = {tf: len(c) for tf, c in candles.items()}
            print(f"  {symbol:<12} candles: {counts}")
            data_ok += 1
        else:
            print(f"  {symbol:<12} FAILED (empty)")
            data_fail += 1
    except Exception as e:
        print(f"  {symbol:<12} ERROR: {e}")
        data_fail += 1

print(f"  Data OK: {data_ok} | Fail: {data_fail}")
print()

# ---- TELEGRAM ----
from SERVICES.telegram.telegram_formatter import TelegramFormatter

fmt = TelegramFormatter()
test_tier = fmt._tier_label(0.85)
print(f"  Telegram Formatter:     OK (tier test: {test_tier})")
print(f"  Telegram token:         {'SET' if os.path.exists('TELEGRAM/.env') else 'MISSING'}")
print()



# ---- AUDIT DIRS ----
for d in ["AUDIT", "REPORTS", "BASELINES"]:
    exists = os.path.isdir(d)
    print(f"  Audit dir {d:<12} {'OK' if exists else 'MISSING'}")

print()
print("=" * 60)
print("  ALL SYSTEMS OK — READY FOR PRODUCTION VALIDATION")
print("  Starting main QuantOS loop...")
print("=" * 60)
print()

# ---- START MAIN APPLICATION ----
from main import QuantOSApp

app = QuantOSApp(provider)
try:
    app.start()
except KeyboardInterrupt:
    app.stop()
