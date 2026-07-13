"""
P2: Analytics & Validation Report
- Lê pipelines existentes do JSON
- Exporta para SQLite + CSV
- Computa estatísticas (rejeição, performance, saúde)
- Gera relatório formatado
"""
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ENGINE.analytics.analytics_engine import AnalyticsEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

audit_dir = "MEMORY/audit"


def print_report(report: dict):
    summary = report.get("summary", {})
    sig = report.get("signals", {})
    perf = report.get("performance", {})
    health = report.get("health", {})

    print("=" * 60)
    print(f"  QUANTOS | Pipeline Analytics Report")
    print(f"  {summary.get('total_cycles', 0)} ciclos | {summary.get('total_assets_analyzed', 0)} ativos")
    print("=" * 60)

    # SINAIS
    print(f"\n=== SINAIS ===")
    print(f"  Total decisions: {sig.get('total_signals', 0)}")
    print(f"  Approved: {sig.get('approved', 0)}")
    print(f"  Rejected: {sig.get('rejected', 0)}")
    print(f"  Approval rate: {sig.get('approval_rate', 0):.1f}%")
    print(f"  Avg Quality: {sig.get('avg_quality', 0):.4f}")
    print(f"  Avg Confidence: {sig.get('avg_confidence', 0):.4f}")

    # REJEIÇÕES
    ranking = report.get("rejection_ranking", [])
    if ranking:
        print(f"\n=== TOP REJEICOES ===")
        print(f"  {'#':<3} {'Motivo':<30} {'Qtd':<6} {'%':<7} {'Ativos'}")
        print(f"  {'-'*55}")
        for i, r in enumerate(ranking[:10], 1):
            print(f"  {i:<3} {r['motivo']:<30} {r['quantidade']:<6} {r['percentual']:<7}% {r['ativos_afetados']}")
        if len(ranking) > 10:
            print(f"  ... e mais {len(ranking) - 10} motivos")

    # PERFORMANCE
    dur = perf.get("duration_ms", {}).get("all_cycles", {})
    cached = perf.get("duration_ms", {}).get("cached_cycles", {})
    print(f"\n=== PERFORMANCE ===")
    print(f"  Total cycles: {perf.get('total_cycles', 0)}")
    print(f"  Duration (all): {dur.get('mean', 0):.0f}ms avg | {dur.get('max', 0):.0f}ms max")
    print(f"  Duration (cached): {cached.get('mean', 0):.0f}ms avg")
    print(f"  First (uncached): {perf.get('duration_ms', {}).get('first_cycle_uncached', 0):.0f}ms")

    # SAÚDE
    hs = health.get("health_scores", {})
    print(f"\n=== SAUDE ===")
    print(f"  Health score: {hs.get('mean', 'N/A')} avg | {hs.get('min', 'N/A')}-{hs.get('max', 'N/A')} range")
    print(f"  Below threshold (<90): {hs.get('below_threshold', 0)} cycles")
    print(f"  Bugs: {health.get('total_bugs', 0)} | Silent drops: {health.get('total_silent_drops', 0)}")

    print("=" * 60)


if __name__ == "__main__":
    ae = AnalyticsEngine(audit_dir)
    ae.load_all()
    report = ae.generate_report()

    print_report(report)

    ae.to_sqlite()
    ae.to_csv()
    print(f"\nRelatorio exportado para SQLite + CSV em '{audit_dir}'")
