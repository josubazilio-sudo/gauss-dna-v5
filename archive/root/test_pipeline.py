import json
import logging
import os
import time
import sys

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(message)s")

from CORE.data_providers import create_provider
from ENGINE.market.market_engine import MarketEngine
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.diagnostic.engine import DiagnosticEngine, STAGES
from SERVICES.telegram.telegram_diagnostic_formatter import TelegramDiagnosticFormatter
from ENGINE.consensus.consensus_engine import ConsensusEngine

provider = create_provider()
market = MarketEngine()
scanner = ScannerEngine()
diag = DiagnosticEngine()

TIMEFRAMES = ["30m", "1h", "4h", "1d"]
PAIRS = provider.get_symbols()[:3] or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

start = time.time()
diag.start_cycle(1)
diag.record_step("Ativos monitorados", len(PAIRS))

for pair in PAIRS:
    pair_start = time.time()

    tf_candles = provider.get_all_timeframes(symbol=pair, timeframes=TIMEFRAMES)
    if not tf_candles:
        diag.record_market_data(pair, loaded=False, error="Sem dados da API")
        diag.record_final_decision(pair, "REJECTED", primary_reason="Sem dados", final_decision="Rejected at API")
        continue

    api_ms = (time.time() - pair_start) * 1000
    diag.record_market_data(pair, loaded=True, api_ms=api_ms)

    tf_counts = {tf: len(c) for tf, c in tf_candles.items()}
    diag.record_candles(pair, tf_counts)

    main_candles = tf_candles.get("1h", next(iter(tf_candles.values())))
    market_ctx = market.analyze(pair=pair, candles=main_candles, timeframe_candles=tf_candles)
    ind = market_ctx.indicators
    diag.record_indicators(pair, {
        "atr": ind.atr_percent, "adx": ind.adx,
        "rsi": ind.rsi, "rvol": ind.rvol, "volatility": ind.bb_width,
    })

    report = scanner.scan(pair=pair, candles=tf_candles, market_ctx=market_ctx)

    total_bos = total_choch = total_obs = total_fvgs = total_sweeps = 0

    for sig in report.signals:
        pats = sig.patterns if hasattr(sig, "patterns") else []
        for p in pats:
            pt = str(p.type) if hasattr(p, "type") else ""
            if "BOS" in pt: total_bos += 1
            if "CHOCH" in pt: total_choch += 1
            if "ORDER_BLOCK" in pt: total_obs += 1
            if "FVG" in pt: total_fvgs += 1
            if "LIQUIDITY_SWEEP" in pt or "SWEEP" in pt: total_sweeps += 1

    if report.signals:
        first = report.signals[0]
        st = first.structure
        diag.record_structure(pair, {
            "trend": str(st.structure_type) if hasattr(st, "structure_type") else "unknown",
            "strength": st.structure_strength if hasattr(st, "structure_strength") else 0,
            "bos": total_bos, "choch": total_choch,
        })
    else:
        diag.record_structure(pair, {
            "trend": str(market_ctx.trend.value) if hasattr(market_ctx.trend, "value") else str(market_ctx.trend),
            "strength": market_ctx.trend_strength, "bos": 0, "choch": 0,
        })

    diag.record_smart_money(pair, order_blocks=total_obs, fvgs=total_fvgs, sweeps=total_sweeps)

    entry_scores = [s.scores.quality_score * 100 for s in report.signals if hasattr(s, "scores") and s.scores]
    avg_entry = sum(entry_scores) / len(entry_scores) if entry_scores else 0
    diag.record_entry_zone(pair, zone_type="multi_tf" if entry_scores else "none", score=round(avg_entry, 1), approved=avg_entry >= 40)

    if report.signals:
        tf_directions = {sig.timeframe: sig.direction for sig in report.signals}
        tf_scores = {sig.timeframe: sig.scores.quality_score if sig.scores else 0 for sig in report.signals}
        if tf_directions:
            ce = ConsensusEngine()
            cr = ce.compute(tf_directions, tf_scores)
            diag.record_consensus(pair, {
                "consensus_score": cr.consensus_score,
                "final_direction": str(cr.final_direction.value) if cr.final_direction else "none",
                "agreement_pct": cr.agreement_pct,
                "classification": cr.classification,
                "dominant_timeframe": cr.dominant_timeframe,
                "dissenting": cr.dissenting_timeframes,
                "votes": [{"tf": v.timeframe, "dir": str(v.direction.value) if v.direction else "none", "score": v.score, "weight": v.weight} for v in cr.votes],
            })
    else:
        diag.record_consensus(pair, {"consensus_score": 0, "final_direction": "none", "classification": "Sem dados", "votes": []})

    for sig in report.signals:
        scores_dict = sig.scores.to_dict() if sig.scores else {}
        passed = sig.classification.value != "reprovado"
        reasons = sig.rejection_reasons if hasattr(sig, "rejection_reasons") else []
        diag.record_quality_gate(pair, scores_dict, passed, reasons)

    if report.signals:
        best = max(report.signals, key=lambda s: s.scores.quality_score if s.scores else 0)
        passed = best.classification.value != "reprovado"
        primary = ""; expected = None; obtained = None; secondary = []
        if not passed:
            reasons = best.rejection_reasons or []
            if reasons:
                primary = reasons[0]; secondary = reasons[1:]
            expected = 0.5; obtained = best.scores.quality_score if best.scores else 0
        d = "APPROVED" if passed else "REJECTED"
        final = "Approved by Quality Gate" if passed else "Rejected by " + (primary or "Quality Gate")
        diag.record_final_decision(pair, status=d, primary_reason=primary, expected=expected, obtained=obtained, secondary_reasons=secondary, final_decision=final)
    else:
        diag.record_quality_gate(pair, {"quality_score": 0}, False, ["Nenhum sinal gerado"])
        diag.record_final_decision(pair, status="REJECTED", primary_reason="Nenhum sinal", final_decision="Rejected: no signals generated")

diag.detect_silent_drops(PAIRS)
report = diag.end_cycle((time.time() - start) * 1000)

print("\n=== PIPELINE AUDIT ===")
for pair in PAIRS:
    stages = report.pipeline_audit.get(pair, [])
    fd = report.final_decisions.get(pair, {})
    print(f"{pair}: {len(stages)}/{len(STAGES)} stages — {stages}")
    print(f"  Decisao: {fd.get('status', 'N/A')} | {fd.get('final_decision', 'N/A')}")

print("\n=== HEALTH ===")
for k, v in (report.health or {}).items():
    print(f"  {k}: {v}")

print("\n=== TELEGRAM PREVIEW ===")
msg = TelegramDiagnosticFormatter.format(report)
print(msg)

print("\n=== SUMMARY ===")
spath = os.path.join("MEMORY", "audit", "summary.json")
if os.path.exists(spath):
    with open(spath) as f:
        s = json.load(f)
    print(json.dumps(s, indent=2))
else:
    print("summary.json not found")

print("\n=== BUGS ===")
for bug in report.bugs:
    print(f"  {bug['module']}: {bug['probable_cause']}")

print("\n=== PIPELINE CYCLE FILE ===")
cpath = os.path.join("MEMORY", "audit", "pipeline_1.json")
if os.path.exists(cpath):
    with open(cpath) as f:
        c = json.load(f)
    print(f"  final_decisions: {list(c['final_decisions'].keys())}")
    print(f"  health: {c.get('health', {}).get('health_score')}")
    print(f"  bugs: {len(c.get('bugs', []))}")
else:
    print("pipeline_1.json not found")
