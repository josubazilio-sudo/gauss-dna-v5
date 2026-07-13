#!/usr/bin/env python3
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from AUDIT.ab_validation import ABValidation, ABResult
from AUDIT.baseline import save_baseline, compare_against_baseline, list_baselines
from AUDIT.recalibrator import Recalibrator

log = logging.getLogger("run_ab")


def main():
    use_real = "--real" in sys.argv or "--synthetic" not in sys.argv

    print("=" * 68)
    print("  QUANTOS V11.1 — VALIDAÇÃO A/B INSTITUCIONAL")
    print("  V7 (producao) vs V11 (Decision Brain)")
    print(f"  Fonte: {'REAIS (Binance)' if use_real else 'SINTETICOS'}")
    print("=" * 68)

    print("\n[1/5] Executando A/B Validation...")
    ab = ABValidation(use_real_data=use_real)
    result_v7, result_v11, comparison = ab.run()

    print(f"  V7:  {result_v7.total_trades} trades | WR={result_v7.win_rate:.1%} | PF={result_v7.profit_factor:.2f}")
    print(f"  V11: {result_v11.total_trades} trades | WR={result_v11.win_rate:.1%} | PF={result_v11.profit_factor:.2f}")

    print("\n[2/5] Salvando baseline V7...")
    baseline_path = save_baseline(result_v7, version="V7")

    print("\n[3/5] Comparacao direta V7 vs V11:")
    print(f"  {'Metrica':<22s} {'V7':<12s} {'V11':<12s} {'Dif':<10s} {'Melhor':<8s}")
    print(f"  {'-'*22} {'-'*12} {'-'*12} {'-'*10} {'-'*8}")
    for metric, vals in sorted(comparison.items()):
        if isinstance(vals, dict) and "diff" in vals:
            v7 = vals.get("V7", 0)
            v11 = vals.get("V11", 0)
            diff = vals.get("diff", 0)
            better = "V11" if vals.get("V11_better") else "V7"
            v7_str = f"{v7:.4f}" if isinstance(v7, (float, int)) else str(v7)
            v11_str = f"{v11:.4f}" if isinstance(v11, (float, int)) else str(v11)
            diff_str = f"{diff:+.4f}" if isinstance(diff, (float, int)) else str(diff)
            arrow = ">>" if vals.get("V11_better") else "<<"
            print(f"  {metric:<22s} {v7_str:<12s} {v11_str:<12s} {diff_str:<10s} {arrow} {better:<6s}")

    print("\n[4/5] Verificando recalibracao...")
    brain = ab._v11
    recal = Recalibrator(brain, min_trades=100)
    trade_dicts = [t.__dict__ for t in result_v11.trades]
    ajustes = recal.analyze_and_adjust(trade_dicts)
    if ajustes:
        print(f"  Ajustes aplicados: {len(ajustes)}")
        for a in ajustes:
            print(f"    ! {a['dimensao']}:{a['label']} WR={a['win_rate']:.1%} degrad={a['degradacao']:.1%}")
    else:
        print(f"  Nenhum ajuste necessario ({len(result_v11.trades)} trades V11)")

    print("\n[5/5] Resumo da Validacao:")
    pas = result_v11.profit_factor >= result_v7.profit_factor
    ex = result_v11.expectancy >= result_v7.expectancy
    dd = result_v11.max_drawdown <= result_v7.max_drawdown
    wr = result_v11.win_rate >= result_v7.win_rate
    criteria = [
        ("PF V11 >= V7", result_v7.profit_factor, result_v11.profit_factor, pas),
        ("Expectancy V11 >= V7", result_v7.expectancy, result_v11.expectancy, ex),
        ("Drawdown V11 <= V7", result_v7.max_drawdown, result_v11.max_drawdown, dd),
        ("WR V11 >= V7", result_v7.win_rate, result_v11.win_rate, wr),
    ]
    passed = sum(1 for _, _, _, ok in criteria if ok)
    for name, v7v, v11v, ok in criteria:
        status = "PASSOU" if ok else "FALHOU"
        print(f"  [{status}] {name:<30s} V7={v7v:.4f}  V11={v11v:.4f}")
    print(f"\n  {passed}/{len(criteria)} criterios atendidos")
    if passed == len(criteria):
        print("  RESULTADO: V11 APROVADO PARA SUBSTITUIR V7")
    else:
        print("  RESULTADO: V11 MANTIDO EM PAPER TRADING — nova calibracao necessaria")
    print("=" * 68)

    return comparison


if __name__ == "__main__":
    main()