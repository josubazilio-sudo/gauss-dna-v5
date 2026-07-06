"""
Coordenador central do sistema de memória.

Integra todos os subsistemas de memória em uma única interface.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .file_store import FileStore
from .lesson_registry import LessonRegistry, Lesson
from .improvement_log import ImprovementLog, ImprovementEntry
from .parameter_history import ParameterHistory, ParameterRecord
from .backtest_records import BacktestRecords, BacktestRecord
from .change_log import ChangeLog, ChangeEntry
from .dna_updater import DNAUpdater
from .memory_query import MemoryQuery
from .memory_report import MemoryReport

log = logging.getLogger(__name__)


class MemoryEngine:
    """Motor central do sistema de memória permanente.

    Usage:
        engine = MemoryEngine(memory_dir=Path("MEMORY"))
        engine.lessons.add(Lesson.create("titulo", "descricao"))
        print(engine.report.summary())
    """

    def __init__(self, memory_dir: Optional[Path] = None) -> None:
        self._dir = memory_dir or Path("MEMORY")
        self._store = FileStore(self._dir)

        self.lessons = LessonRegistry(self._store)
        self.improvements = ImprovementLog(self._store)
        self.parameters = ParameterHistory(self._store)
        self.backtests = BacktestRecords(self._store)
        self.changes = ChangeLog(self._store)
        self.dna = DNAUpdater()
        self.query = MemoryQuery(self._store)
        self.report = MemoryReport(
            self.lessons,
            self.improvements,
            self.parameters,
            self.backtests,
            self.changes,
        )

        log.info("Memory Engine inicializado: %s", self._dir)

    def record_change(
        self,
        change_type: str,
        module: str,
        description: str,
        previous_value: str = "",
        new_value: str = "",
        author: str = "system",
        version: str = "",
    ) -> str:
        """Registra uma mudança e retorna seu ID."""
        entry = ChangeEntry.create(
            change_type=change_type,
            module=module,
            description=description,
            previous_value=previous_value,
            new_value=new_value,
            author=author,
            version=version,
        )
        self.changes.log(entry)
        return entry.change_id

    def record_lesson(
        self,
        title: str,
        description: str,
        category: str = "general",
        severity: str = "info",
        source: str = "manual",
    ) -> str:
        """Registra uma lição aprendida e retorna seu ID."""
        lesson = Lesson.create(
            title=title,
            description=description,
            category=category,
            severity=severity,
            source=source,
        )
        self.lessons.add(lesson)
        return lesson.lesson_id

    def record_improvement(
        self,
        title: str,
        description: str,
        category: str = "feature",
        status: str = "pending",
        module: str = "unknown",
        version: str = "",
        author: str = "system",
    ) -> str:
        """Registra uma melhoria e retorna seu ID."""
        entry = ImprovementEntry.create(
            title=title,
            description=description,
            category=category,
            status=status,
            module=module,
            version=version,
            author=author,
        )
        self.improvements.add(entry)
        return entry.improvement_id

    def record_backtest(self, **kwargs) -> str:
        """Registra um backtest e retorna seu ID."""
        record = BacktestRecord.create(**kwargs)
        self.backtests.add(record)
        return record.backtest_id

    def record_parameters(
        self,
        strategy: str,
        parameters: Dict,
        result: str = "neutral",
        metric: str = "profit_factor",
        metric_value: float = 0.0,
    ) -> str:
        """Registra parâmetros e retorna seu ID."""
        record = ParameterRecord.create(
            strategy=strategy,
            parameters=parameters,
            result=result,
            metric=metric,
            metric_value=metric_value,
        )
        self.parameters.add(record)
        return record.param_id
