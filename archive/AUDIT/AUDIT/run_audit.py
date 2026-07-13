#!/usr/bin/env python3
"""
QuantOS V2.2 -- Validacao Final Institucional
Pipeline completo: download dados reais → backtest → Monte Carlo → 
Walk Forward → Overfitting → Matriz Robustez → Feature Importance →
Dashboard → IA Analytics → Relatório Executivo
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from AUDIT.backtest_audit import BacktestAudit, BACKTEST_ASSETS, BACKTEST_TIMEFRAMES
from AUDIT.auto_calibration import AutoCalibration
from AUDIT.dashboard import PerformanceDashboard
from AUDIT.report_generator import ReportGenerator
from AUDIT.monte_carlo import MonteCarloEngine
from AUDIT.ai_analytics import AIAnalytics
from AUDIT.institutional_metrics import compute_institutional_metrics
from AUDIT.robustness_matrix import RobustnessMatrix
from AUDIT.overfitting_detector import OverfittingDetector
from AUDIT.data_loader import BinanceDataLoader


def main():
    use_real = "--real" in sys.argv or "--synthetic" not in sys.argv
    show_console = "--console" not in sys.argv
    data_source = "REAIS (Binance Futures)" if use_real else "sinteticos"

    print("=" * 68)
    print("  QUANTOS V2.2 -- VALIDAÇÃO FINAL INSTITUCIONAL")
    print(f"  Fonte: {data_source} | Ativos: 5 | Timeframes: 3 | Periodo: 24 meses")
    print("  Criterios: PF>=1.50 | WR>=40% | DD<=10% | Sharpe>=1.20 | Sortino>=1.80")
    print("=" * 68)

    print(f"\n[1/7] Executando Backtest...")
    bt = BacktestAudit(use_real_data=use_real)
    result = bt.run()

    print(f"\n[2/7] Metricas Institucionais...")
    metrics = compute_institutional_metrics(result)
    print(f"  Alpha={metrics.alpha:.4f} Beta={metrics.beta:.4f} Kelly={metrics.kelly_criterion:.2%}")
    print(f"  SQN={metrics.sqn:.2f} Recovery={metrics.recovery_factor:.2f} Ulcer={metrics.ulcer_index:.2%}")

    print(f"\n[3/7] Monte Carlo (5.000 simulacoes)...")
    mc = MonteCarloEngine(num_simulations=5000)
    mc_result = mc.simulate(result.trades)
    print(f"  Prob Lucro={mc_result.probability_positive:.1%} Risco Ruina={mc_result.ruin_risk:.1%}")

    print(f"\n[4/7] Matriz de Robustez...")
    matrix = RobustnessMatrix(result)
    best = matrix.best_combinations(min_trades=5, top_n=5)
    worst = matrix.worst_combinations(min_trades=5, top_n=5)
    print(f"  Melhores combinacoes:")
    for (label, row, col), stats in best[:3]:
        print(f"    {label}: {row} x {col} -> PF={stats['profit_factor']:.2f} WR={stats['win_rate']:.1%}")
    print(f"  Piores combinacoes:")
    for (label, row, col), stats in worst[:3]:
        print(f"    {label}: {row} x {col} -> PF={stats['profit_factor']:.2f} WR={stats['win_rate']:.1%}")

    print(f"\n[5/7] Deteccao de Overfitting...")
    overfit = OverfittingDetector(result, mc_result)
    assessment = overfit.overall_assessment()
    print(f"  Verdict: {assessment['verdict']}")
    for check in assessment['checks']:
        status = "OK" if check['passed'] else "ALERTA"
        print(f"    {status}: {check['check_name']} ({check['detail']})")

    print(f"\n[6/7] Auto-Calibracao + Feature Importance...")
    cal = AutoCalibration()
    records = [dict(t.__dict__) for t in result.trades]
    for r in records:
        r["rvol_value"] = r.get("rvol_value", 0) or 0
        r["risk_reward"] = r.get("rr", 0)
        r["quality"] = r.get("quality", 0)
        r["adx"] = r.get("adx", 0)
    suggestions = cal.analyze(records)

    action_items = [s for s in suggestions if s.get("suggestion")]
    print(f"  Sugestoes com acao: {len(action_items)}")
    for s in action_items[:5]:
        print(f"    ! {s['feature']}: {s['suggestion']}")

    print(f"\n[7/7] Gerando Dashboard + Relatório + IA Analytics...")
    dash = PerformanceDashboard()
    dash_path = dash.generate(result)
    print(f"  Dashboard: {dash_path}")

    ai = AIAnalytics(result)
    matrix_text = matrix.summary()
    overfit_text = overfit.summary()

    report = ReportGenerator()
    report_text = report.generate(
        result=result,
        calibration=suggestions,
        monte_carlo=mc_result,
        ai_analytics=ai,
        institutional_metrics=metrics,
        robustness_matrix_text=matrix_text,
        overfitting_text=overfit_text,
    )

    report_path = Path(__file__).parent / "data" / "relatorio_executivo.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  Relatório: {report_path}")

    print(f"\n{'=' * 68}")
    print(f"  VALIDAÇÃO INSTITUCIONAL CONCLUÍDA")
    print(f"  {result.total_trades} operacoes | PF={result.profit_factor:.2f} | WR={result.win_rate:.1%}")
    print(f"  Sharpe={result.sharpe_ratio:.2f} | Sortino={result.sortino_ratio:.2f}")
    print(f"  DD={result.max_drawdown:.2%} | SQN={metrics.sqn:.2f} | Kelly={metrics.kelly_criterion:.2%}")
    print(f"  Risco Ruina={mc_result.ruin_risk:.1%} | Alpha={metrics.alpha:.4f}")
    print(f"  Overfitting: {assessment['verdict']}")
    print(f"  Walk-Forward Robustness: {result.walk_forward_results.get('robustness_score', 0):.2%}")
    print(f"{'=' * 68}")

    goals = [
        ("Profit Factor >= 1.50", result.profit_factor, result.profit_factor >= 1.50),
        ("Win Rate >= 40%", result.win_rate, result.win_rate >= 0.40),
        ("Sharpe >= 1.20", result.sharpe_ratio, result.sharpe_ratio >= 1.20),
        ("Sortino >= 1.80", result.sortino_ratio, result.sortino_ratio >= 1.80),
        ("Drawdown <= 10%", result.max_drawdown, result.max_drawdown <= 0.10),
        ("Expectancy > 0", result.expectancy, result.expectancy > 0),
        ("SQN >= 2.5", metrics.sqn, metrics.sqn >= 2.5) if hasattr(metrics, 'sqn') else None,
        ("Risco Ruina < 1%", mc_result.ruin_risk, mc_result.ruin_risk < 0.01),
        ("10+ resultados Walk Fwd", result.walk_forward_results.get("robustness_score", 0), result.walk_forward_results.get("robustness_score", 0) > 0.5 if result.walk_forward_results else False),
    ]
    passed = sum(1 for _, _, ok in goals if ok)
    total = len(goals)
    print(f"\n  CRITÉRIOS DE APROVAÇÃO: {passed}/{total}")

    if show_console:
        summary = report_text[:2000]
        print(summary.encode('ascii', 'ignore').decode('ascii'))
        print("  ...(relatório completo em AUDIT/data/relatorio_executivo.txt)")


if __name__ == "__main__":
    main()
