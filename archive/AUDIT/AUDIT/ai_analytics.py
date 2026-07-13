import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .backtest_audit import BacktestResult, TradeRecord

log = logging.getLogger(__name__)


class AIAnalytics:
    def __init__(self, result: BacktestResult):
        self._result = result
        self._trades = result.trades

    def best_filter(self) -> str:
        features = [(f['feature'], f['win_rate'], f['total']) for f in self._result.feature_ranking]
        features = [f for f in features if f[2] >= 5]
        if not features:
            return "Dados insuficientes para análise."
        best = max(features, key=lambda x: x[1])
        return f"{best[0]}: WR={best[1]:.1%} em {best[2]} trades — melhor filtro individual."

    def worst_filter(self) -> str:
        features = [(f['feature'], f['win_rate'], f['total']) for f in self._result.feature_ranking]
        features = [f for f in features if f[2] >= 5]
        if not features:
            return "Dados insuficientes para análise."
        worst = min(features, key=lambda x: x[1])
        return f"{worst[0]}: WR={worst[1]:.1%} em {worst[2]} trades — pior filtro individual."

    def best_asset(self) -> str:
        assets = self._result.by_asset
        valid = {k: v for k, v in assets.items() if v['trades'] >= 5}
        if not valid:
            return "Dados insuficientes."
        best = max(valid.items(), key=lambda x: x[1]['profit_factor'])
        return (f"{best[0]}: PF={best[1]['profit_factor']:.2f}, "
                f"WR={best[1]['win_rate']:.1%}, {best[1]['trades']} trades.")

    def worst_asset(self) -> str:
        assets = self._result.by_asset
        valid = {k: v for k, v in assets.items() if v['trades'] >= 5}
        if not valid:
            return "Dados insuficientes."
        worst = min(valid.items(), key=lambda x: x[1]['profit_factor'])
        return (f"{worst[0]}: PF={worst[1]['profit_factor']:.2f}, "
                f"WR={worst[1]['win_rate']:.1%}, {worst[1]['trades']} trades.")

    def best_timeframe(self) -> str:
        tfs = self._result.by_timeframe
        valid = {k: v for k, v in tfs.items() if v['trades'] >= 5}
        if not valid:
            return "Dados insuficientes."
        best = max(valid.items(), key=lambda x: x[1]['profit_factor'])
        return (f"{best[0]}: PF={best[1]['profit_factor']:.2f}, "
                f"WR={best[1]['win_rate']:.1%}, {best[1]['trades']} trades.")

    def worst_timeframe(self) -> str:
        tfs = self._result.by_timeframe
        valid = {k: v for k, v in tfs.items() if v['trades'] >= 5}
        if not valid:
            return "Dados insuficientes."
        worst = min(valid.items(), key=lambda x: x[1]['profit_factor'])
        return (f"{worst[0]}: PF={worst[1]['profit_factor']:.2f}, "
                f"WR={worst[1]['win_rate']:.1%}, {worst[1]['trades']} trades.")

    def best_setup(self) -> str:
        setups = self._result.by_setup
        valid = {k: v for k, v in setups.items() if v['trades'] >= 3}
        if not valid:
            return "Dados insuficientes."
        best = max(valid.items(), key=lambda x: x[1]['win_rate'])
        return f"{best[0]}: WR={best[1]['win_rate']:.1%}, {best[1]['trades']} trades."

    def loss_antecedents(self) -> str:
        causes = self._result.loss_causes
        sorted_causes = sorted(causes.items(), key=lambda x: x[1], reverse=True)
        if not sorted_causes:
            return "Nenhuma causa registrada."
        lines = []
        for cause, count in sorted_causes[:5]:
            pct = count / len(self._trades) * 100 if self._trades else 0
            lines.append(f"  {cause}: {count} ocorrências ({pct:.1f}% dos trades)")
        return "Principais condições antes de perdas:\n" + "\n".join(lines)

    def win_antecedents(self) -> str:
        causes = self._result.win_causes
        sorted_causes = sorted(causes.items(), key=lambda x: x[1], reverse=True)
        if not sorted_causes:
            return "Nenhuma causa registrada."
        lines = []
        for cause, count in sorted_causes[:5]:
            pct = count / len([t for t in self._trades if t.result == "win"]) * 100 if self._trades else 0
            lines.append(f"  {cause}: {count} ocorrências ({pct:.1f}% dos wins)")
        return "Principais condições antes de ganhos:\n" + "\n".join(lines)

    def filters_to_strengthen(self) -> str:
        weak_filters = []
        for f in self._result.feature_ranking:
            if f['win_rate'] < 0.15 and f['total'] >= 5:
                weak_filters.append(f)
        if not weak_filters:
            return "Nenhum filtro crítico identificado."
        lines = ["Filtros que devem ser fortalecidos:"]
        for f in sorted(weak_filters, key=lambda x: x['win_rate']):
            lines.append(f"  {f['feature']}: WR={f['win_rate']:.1%} ({f['wins']}/{f['total']})")
        return "\n".join(lines)

    def filters_to_weaken(self) -> str:
        strong_filters = []
        for f in self._result.feature_ranking:
            if f['win_rate'] > 0.35 and f['total'] >= 5:
                strong_filters.append(f)
        if not strong_filters:
            return "Nenhum filtro excessivamente restritivo identificado."
        lines = ["Filtros que podem ser enfraquecidos (muito restritivos):"]
        for f in sorted(strong_filters, key=lambda x: x['win_rate'], reverse=True):
            lines.append(f"  {f['feature']}: WR={f['win_rate']:.1%} ({f['wins']}/{f['total']})")
        return "\n".join(lines)

    def full_report(self) -> str:
        lines = ["=" * 50, "  IA ANALYTICS — RELATÓRIO AUTOMÁTICO", "=" * 50, ""]
        lines.append(self.best_filter())
        lines.append(self.worst_filter())
        lines.append("")
        lines.append(f"Melhor ativo: {self.best_asset()}")
        lines.append(f"Pior ativo: {self.worst_asset()}")
        lines.append("")
        lines.append(f"Melhor timeframe: {self.best_timeframe()}")
        lines.append(f"Pior timeframe: {self.worst_timeframe()}")
        lines.append("")
        lines.append(f"Melhor setup: {self.best_setup()}")
        lines.append("")
        lines.append(self.loss_antecedents())
        lines.append("")
        lines.append(self.win_antecedents())
        lines.append("")
        lines.append(self.filters_to_strengthen())
        lines.append("")
        lines.append(self.filters_to_weaken())
        return "\n".join(lines)
