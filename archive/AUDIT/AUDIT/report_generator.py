import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .backtest_audit import BacktestResult
from .ai_analytics import AIAnalytics

log = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self):
        self._lines: List[str] = []

    def generate(self, result: BacktestResult,
                 calibration: Optional[List[Dict]] = None,
                 monte_carlo: Optional[Any] = None,
                 ai_analytics: Optional[AIAnalytics] = None,
                 institutional_metrics: Optional[Any] = None,
                 robustness_matrix_text: Optional[str] = None,
                 overfitting_text: Optional[str] = None) -> str:
        self._lines = []
        self._header("RELATÓRIO EXECUTIVO — QUANTOS V2.1")
        self._line(f"Gerado em: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        self._line(f"Período: 24 meses | Ativos: 5 | Timeframes: 3")
        self._line(f"Metas: PF >= 1.50 | WR >= 40% | DD <= 10% | Sharpe >= 1.20 | Sortino >= 1.80")
        self._line("")

        self._section("1. RESUMO GERAL")
        self._metric("Total de operações", result.total_trades)
        self._metric("Win Rate", f"{result.win_rate:.1%}" + self._metag(result.win_rate >= 0.40))
        self._metric("Profit Factor", f"{result.profit_factor:.2f}" + self._metag(result.profit_factor >= 1.50))
        self._metric("Drawdown Máximo", f"{result.max_drawdown:.2%}" + self._metag(result.max_drawdown <= 0.10))
        self._metric("Expectância", f"{result.expectancy:.4f}" + self._metag(result.expectancy > 0))
        self._metric("Sharpe Ratio", f"{result.sharpe_ratio:.2f}" + self._metag(result.sharpe_ratio >= 1.20))
        self._metric("Sortino Ratio", f"{result.sortino_ratio:.2f}" + self._metag(result.sortino_ratio >= 1.80))
        self._metric("Calmar Ratio", f"{result.calmar_ratio:.2f}")
        self._metric("Média de RR", f"{result.avg_rr:.2f}:1")
        self._metric("Duração Média", f"{result.avg_trade_duration_h:.1f}h")
        self._metric("Lucro Bruto", f"${result.gross_profit:.2f}")
        self._metric("Prejuízo Bruto", f"${result.gross_loss:.2f}")
        self._metric("P/L Líquido", f"${result.net_pnl:.2f}")
        self._line("")

        if monte_carlo:
            self._section("1B. MONTE CARLO (5.000 simulações)")
            self._metric("Retorno Médio", f"${monte_carlo.mean_return:.2f}")
            self._metric("Retorno Mediano", f"${monte_carlo.median_return:.2f}")
            self._metric("VaR 95%", f"${monte_carlo.var_95:.2f}")
            self._metric("VaR 99%", f"${monte_carlo.var_99:.2f}")
            self._metric("Prob. Lucro", f"{monte_carlo.probability_positive:.1%}")
            self._metric("Prob. PF > 1.0", f"{monte_carlo.probability_profit_factor_gt_1:.1%}")
            self._metric("Prob. DD < 10%", f"{monte_carlo.probability_max_dd_lt_10:.1%}")
            self._metric("Risco de Ruína", f"{monte_carlo.ruin_risk:.1%}" + self._metag(monte_carlo.ruin_risk < 0.01))
            self._metric("Drawdown Esperado", f"{monte_carlo.expected_drawdown:.1%}")
            self._metric("Lucro Esperado", f"${monte_carlo.expected_profit:.2f}")
            self._metric("Pior Sequência de Perdas", str(monte_carlo.worst_loss_streak))
            self._metric("Melhor Sequência de Ganhos", str(monte_carlo.best_win_streak))
            self._metric("Confidence Score", f"{monte_carlo.confidence_score:.1%}")
            self._line("")

        if result.walk_forward_results:
            self._section("1C. WALK FORWARD VALIDATION")
            wf = result.walk_forward_results
            self._metric("In-Sample Trades", str(wf.get('in_sample', {}).get('trades', 0)))
            self._metric("In-Sample WR", f"{wf.get('in_sample', {}).get('win_rate', 0):.1%}")
            self._metric("In-Sample PF", f"{wf.get('in_sample', {}).get('profit_factor', 0):.2f}")
            self._metric("Out-of-Sample Trades", str(wf.get('out_sample', {}).get('trades', 0)))
            self._metric("Out-of-Sample WR", f"{wf.get('out_sample', {}).get('win_rate', 0):.1%}")
            self._metric("Out-of-Sample PF", f"{wf.get('out_sample', {}).get('profit_factor', 0):.2f}")
            self._metric("Robustness Score", f"{wf.get('robustness_score', 0):.2%}")
            self._metric("Strategy Decay", f"{wf.get('decay', 0):.2%}")
            self._line("")

        self._section("2. ESTATÍSTICAS POR ATIVO")
        self._table_header(["Ativo", "Trades", "Wins", "WR", "Avg RR", "PF", "P&L"])
        for asset, stats in sorted(result.by_asset.items()):
            self._table_row([
                asset, str(stats["trades"]), str(stats["wins"]),
                f"{stats['win_rate']:.1%}", f"{stats.get('avg_rr', 0):.2f}",
                f"{stats.get('profit_factor', 0):.2f}",
                f"${stats.get('net_pnl', 0):+.2f}",
            ])
        self._line("")

        self._section("3. ESTATÍSTICAS POR TIMEFRAME")
        self._table_header(["TF", "Trades", "Wins", "WR", "PF"])
        for tf, stats in sorted(result.by_timeframe.items()):
            self._table_row([
                tf, str(stats["trades"]), str(stats["wins"]),
                f"{stats['win_rate']:.1%}", f"{stats.get('profit_factor', 0):.2f}",
            ])
        self._line("")

        self._section("4. ESTATÍSTICAS POR CLASSE")
        self._table_header(["Classe", "Trades", "Wins", "WR", "PF"])
        hierarchy = ["ouro_supremo", "ouro", "prata", "bronze", "reprovado"]
        for cl in hierarchy:
            if cl in result.by_classification:
                stats = result.by_classification[cl]
                self._table_row([
                    cl, str(stats["trades"]), str(stats["wins"]),
                    f"{stats['win_rate']:.1%}", f"{stats.get('profit_factor', 0):.2f}",
                ])
        self._line("")

        self._section("5. ESTATÍSTICAS POR REGIME")
        self._table_header(["Regime", "Trades", "Wins", "WR", "PF"])
        for rg, stats in sorted(result.by_regime.items()):
            self._table_row([
                rg, str(stats["trades"]), str(stats["wins"]),
                f"{stats['win_rate']:.1%}", f"{stats.get('profit_factor', 0):.2f}",
            ])
        self._line("")

        self._section("6. ESTATÍSTICAS POR DIREÇÃO")
        self._table_header(["Direção", "Trades", "Wins", "WR", "Avg RR"])
        for dr, stats in sorted(result.by_direction.items()):
            self._table_row([
                dr, str(stats["trades"]), str(stats["wins"]),
                f"{stats['win_rate']:.1%}", f"{stats.get('avg_rr', 0):.2f}",
            ])
        self._line("")

        self._section("7. RANKING DE FEATURES")
        self._table_header(["Feature", "Wins/Total", "WR"])
        for f in result.feature_ranking[:20]:
            self._table_row([
                f['feature'],
                f"{f['wins']}/{f['total']}",
                f"{f['win_rate']:.1%}",
            ])
        self._line("")

        self._section("8. EVOLUÇÃO MENSAL")
        self._table_header(["Mês", "P&L ($)"])
        for month, pnl in result.monthly_pnl.items():
            self._table_row([month, f"${pnl:+.2f}"])
        self._line("")

        self._section("9. DIAGNÓSTICO — PERDAS")
        sorted_losses = sorted(result.loss_causes.items(), key=lambda x: x[1], reverse=True)
        self._table_header(["Causa", "Ocorrências"])
        for cause, count in sorted_losses[:10]:
            self._table_row([cause, str(count)])
        self._line("")

        self._section("10. DIAGNÓSTICO — GANHOS")
        sorted_wins = sorted(result.win_causes.items(), key=lambda x: x[1], reverse=True)
        self._table_header(["Causa", "Ocorrências"])
        for cause, count in sorted_wins[:10]:
            self._table_row([cause, str(count)])
        self._line("")

        if calibration:
            self._section("11. AUTO-CALIBRAÇÃO — SUGESTÕES")
            self._table_header(["Feature", "Wins", "Total", "WR", "Sugestão"])
            for s in sorted(calibration, key=lambda x: x.get("priority", 0), reverse=True):
                if s.get("suggestion"):
                    self._table_row([
                        s["feature"],
                        str(s.get("wins", 0)),
                        str(s.get("total", 0)),
                        f"{s.get('win_rate', 0):.1%}",
                        s["suggestion"],
                    ])
            self._line("")

        if institutional_metrics:
            self._section("4B. MÉTRICAS INSTITUCIONAIS")
            self._metric("Alpha", f"{institutional_metrics.alpha:.4f}")
            self._metric("Beta", f"{institutional_metrics.beta:.4f}")
            self._metric("Information Ratio", f"{institutional_metrics.information_ratio:.4f}")
            self._metric("Recovery Factor", f"{institutional_metrics.recovery_factor:.2f}")
            self._metric("Ulcer Index", f"{institutional_metrics.ulcer_index:.4%}")
            self._metric("Kelly Criterion", f"{institutional_metrics.kelly_criterion:.2%}")
            self._metric("SQN (System Quality Number)", f"{institutional_metrics.sqn:.2f}")
            self._metric("Expectancy por Trade", f"{institutional_metrics.expectancy_per_trade:.4%}")
            self._metric("Exposure %", f"{institutional_metrics.exposure_pct:.2%}")
            self._metric("Avg Holding Time", f"{institutional_metrics.avg_holding_time:.1f}h")
            self._metric("Avg Winner", f"{institutional_metrics.avg_winner:.4%}")
            self._metric("Avg Loser", f"{institutional_metrics.avg_loser:.4%}")
            self._metric("Largest Winner", f"{institutional_metrics.largest_winner:.4%}")
            self._metric("Largest Loser", f"{institutional_metrics.largest_loser:.4%}")
            self._metric("Profit Diario (medio)", f"${institutional_metrics.daily_pnl:.2f}")
            self._line("")

        if robustness_matrix_text:
            self._section("5B. MATRIZ DE ROBUSTEZ")
            for line in robustness_matrix_text.split("\n"):
                self._line(line)
            self._line("")

        if overfitting_text:
            self._section("5C. DETECÇÃO DE OVERFITTING")
            for line in overfitting_text.split("\n"):
                self._line(line)
            self._line("")

        if ai_analytics:
            self._section("12. IA ANALYTICS")
            self._line(ai_analytics.full_report())
            self._line("")

        self._section("13. DIAGNÓSTICO GERAL / BUGS")
        bugs = self._detect_bugs(result)
        if bugs:
            for bug in bugs:
                self._bullet(bug)
        else:
            self._line("  Nenhum bug crítico detectado.")
        self._line("")

        self._section("14. RECOMENDAÇÕES PRIORIZADAS — PRÓXIMA VERSÃO")
        recommendations = self._build_recommendations(result, calibration)
        for i, rec in enumerate(recommendations, 1):
            self._line(f"  {i}. {rec}")
        self._line("")

        self._section("MÉTRICAS VS METAS")
        goals = [
            ("Profit Factor >= 1.50", result.profit_factor, result.profit_factor >= 1.50),
            ("Win Rate >= 40%", result.win_rate, result.win_rate >= 0.40),
            ("Drawdown <= 10%", result.max_drawdown, result.max_drawdown <= 0.10),
            ("Sharpe >= 1.20", result.sharpe_ratio, result.sharpe_ratio >= 1.20),
            ("Sortino >= 1.80", result.sortino_ratio, result.sortino_ratio >= 1.80),
            ("Expectância > 0", result.expectancy, result.expectancy > 0),
        ]
        if institutional_metrics:
            goals.append(("SQN >= 2.5", institutional_metrics.sqn, institutional_metrics.sqn >= 2.5))
        if monte_carlo:
            goals.append(("Risco de Ruína < 1%", monte_carlo.ruin_risk, monte_carlo.ruin_risk < 0.01))
            goals.append(("Prob. Lucro MC > 50%", monte_carlo.probability_positive, monte_carlo.probability_positive > 0.5))
            goals.append(("Prob. PF > 1.0", monte_carlo.probability_profit_factor_gt_1, monte_carlo.probability_profit_factor_gt_1 > 0.5))
        goals.append(("1.000+ operações", float(result.total_trades), result.total_trades >= 1000))
        if result.walk_forward_results:
            wf_robust = result.walk_forward_results.get("robustness_score", 0)
            goals.append(("Walk-Forward Robust > 0.85", wf_robust, wf_robust > 0.85))

        passed = sum(1 for _, _, ok in goals if ok)
        total = len(goals)
        self._table_header(["Métrica", "Valor", "Meta", "Status"])
        for name, val, ok in goals:
            status = "OK" if ok else "PENDENTE"
            val_str = f"{val:.2%}" if isinstance(val, float) and val < 1 else f"{val:.2f}"
            self._table_row([name, val_str, "", status])
        self._line("")
        self._metric(f"Metas validadas", f"{passed}/{total}")

        return "\n".join(self._lines)

    def _metag(self, achieved: bool) -> str:
        return " [META OK]" if achieved else " [PENDENTE]"

    def _detect_bugs(self, result: BacktestResult) -> List[str]:
        bugs = []
        if result.by_classification.get("reprovado", {}).get("wins", 0) > 0:
            bugs.append("Sinais REPROVADO geraram win — verificar classificação")
        if result.by_regime.get("ranging", {}).get("win_rate", 0) > result.by_regime.get("trending_up", {}).get("win_rate", 1):
            bugs.append("Ranging WR > Trending WR — possível viés nos filtros de regime")
        if result.profit_factor > 5.0 and result.total_trades < 20:
            bugs.append("PF anormalmente alto para poucos trades — pode ser overfitting")
        if result.max_drawdown > 0.30:
            bugs.append(f"Drawdown elevado ({result.max_drawdown:.1%}) — risco acima do aceitável")
        if result.avg_rr < 1.5:
            bugs.append(f"RR médio ({result.avg_rr:.2f}) abaixo do mínimo recomendado (2.0)")
        return bugs

    def _build_recommendations(self, result: BacktestResult,
                                calibration: Optional[List[Dict]]) -> List[str]:
        recs = []

        if result.profit_factor < 1.5:
            recs.append("Revisar thresholds dos filtros com WR < 20% para aumentar PF")

        if result.win_rate < 0.40:
            recs.append("Aumentar RR mínimo para 2.5:1 para compensar WR baixo")

        if result.max_drawdown > 0.10:
            recs.append("Implementar stop-loss dinâmico baseado em ATR para reduzir drawdown")

        if result.sharpe_ratio < 1.2:
            recs.append("Reduzir variância dos resultados com position sizing adaptativo")

        best_tf = max(result.by_timeframe.items(), key=lambda x: x[1]['win_rate'])[0] if result.by_timeframe else "?"
        worst_tf = min(result.by_timeframe.items(), key=lambda x: x[1]['win_rate'])[0] if result.by_timeframe else "?"
        recs.append(f"Priorizar timeframe {best_tf}; considerar reduzir exposição em {worst_tf}")

        if calibration:
            high_prio = [s for s in calibration if s.get("priority", 0) >= 8 and s.get("suggestion")]
            for s in high_prio[:3]:
                recs.append(f"Alta prioridade: {s['suggestion']}")

        recs.append("Implementar análise de correlação entre ativos para diversificação")
        recs.append("Criar sistema de gestão de risco dinâmico baseado em volatilidade")

        return recs

    def _header(self, text: str) -> None:
        border = "=" * (len(text) + 4)
        self._lines.append(border)
        self._lines.append(f"  {text}")
        self._lines.append(border)

    def _section(self, text: str) -> None:
        self._lines.append(f"─── {text} ───")

    def _metric(self, label: str, value: Any) -> None:
        self._lines.append(f"  {label:<30s} {value}")

    def _table_header(self, cols: List[str]) -> None:
        self._lines.append("  " + " | ".join(f"{c:<20s}" for c in cols))
        self._lines.append("  " + "-" * (22 * len(cols)))

    def _table_row(self, cols: List[str]) -> None:
        self._lines.append("  " + " | ".join(f"{c:<20s}" for c in cols))

    def _line(self, text: str) -> None:
        self._lines.append(text)

    def _bullet(self, text: str) -> None:
        self._lines.append(f"  * {text}")
