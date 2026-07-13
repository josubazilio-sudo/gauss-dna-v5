import logging, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QUANTOS_DEBUG"] = "false"
os.environ["QUANTOS_ENV"] = "production"
os.environ["QUANTOS_MODE"] = "PAPER_TRADING"
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from CORE.data_providers.mexc_provider import MexcDataProvider
from ENGINE.market.market_engine import MarketEngine
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.scanner.scanner_types import SignalClassification

provider = MexcDataProvider()
market = MarketEngine()
scanner = ScannerEngine()

pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "MATICUSDT"]
print(f"{'Pair':<12} {'Signals':>3} {'Approved':>3} {'Classes':<35} {'Errors':>2} {'Time':>8}")
print("-" * 80)

for pair in pairs:
    t0 = time.time()
    tf_candles = provider.get_all_timeframes(symbol=pair)
    main_candles = tf_candles.get("1h", next(iter(tf_candles.values())))
    market_ctx = market.analyze(pair=pair, candles=main_candles, timeframe_candles=tf_candles)
    report = scanner.scan(pair=pair, candles=tf_candles, market_ctx=market_ctx, spread=0.001)
    t = round((time.time()-t0)*1000, 1)
    classes = [s.classification.name for s in report.signals]
    approved = sum(1 for s in report.signals if s.classification != SignalClassification.REPROVADO)
    print(f"{pair:<12} {len(report.signals):>3} {approved:>3} {str(classes[:3]):<35} {len(report.errors):>2} {t:>8.1f}ms")
    for s in report.signals:
        print(f"  {s.timeframe:4s}: Q={s.scores.quality_score:.3f} C={s.scores.confidence_score:.3f} R={s.scores.risk_score:.3f} I={s.scores.institutional_score:.3f} dir={s.direction.value} zone={s.entry_zone}")
