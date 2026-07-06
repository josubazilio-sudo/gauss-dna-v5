"""
Geração de relatórios do sistema de memória.
"""

import logging
from typing import Dict

from .lesson_registry import LessonRegistry
from .improvement_log import ImprovementLog
from .parameter_history import ParameterHistory
from .backtest_records import BacktestRecords
from .change_log import ChangeLog

log = logging.getLogger(__name__)


class MemoryReport:
    """Relatórios consolidados do sistema de memória."""

    def __init__(
        self,
        lessons: LessonRegistry,
        improvements: ImprovementLog,
        parameters: ParameterHistory,
        backtests: BacktestRecords,
        changes: ChangeLog,
    ) -> None:
        self._lessons = lessons
        self._improvements = improvements
        self._parameters = parameters
        self._backtests = backtests
        self._changes = changes

    def summary(self) -> Dict[str, int]:
        """Resumo quantitativo de toda a memória.

        Returns:
            Dicionário com contagens de cada coleção.
        """
        return {
            "licoes": self._lessons.count(),
            "melhorias": self._improvements.count(),
            "parametros": self._parameters.count(),
            "backtests": self._backtests.count(),
            "mudancas": self._changes.count(),
        }

    def generate(self) -> str:
        """Gera relatório textual completo.

        Returns:
            String formatada com o relatório.
        """
        summary = self.summary()
        lines = [
            "=== Relatorio da Memoria ===\n",
            f"Licoes aprendidas:      {summary['licoes']}",
            f"Melhorias registradas:  {summary['melhorias']}",
            f"Parametros historicos:  {summary['parametros']}",
            f"Backtests armazenados:  {summary['backtests']}",
            f"Mudancas registradas:   {summary['mudancas']}",
        ]
        if summary["backtests"] > 0:
            best = self._backtests.best_by_metric()
            if best:
                lines.append(f"\nMelhor backtest:")
                lines.append(f"  Estrategia: {best.strategy}")
                lines.append(f"  Profit Factor: {best.profit_factor:.2f}")
                lines.append(f"  Win Rate: {best.win_rate:.1f}%")
        return "\n".join(lines)
