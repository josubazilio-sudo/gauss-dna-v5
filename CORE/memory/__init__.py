"""
Sistema de Memória Permanente do QuantOS.

Armazena lições aprendidas, histórico de melhorias, parâmetros,
resultados de backtests e mudanças — tudo persistente e imutável.
"""

from .memory_engine import MemoryEngine
from .lesson_registry import LessonRegistry, Lesson
from .improvement_log import ImprovementLog, ImprovementEntry
from .parameter_history import ParameterHistory, ParameterRecord
from .backtest_records import BacktestRecord, BacktestRecords
from .change_log import ChangeLog, ChangeEntry
from .dna_updater import DNAUpdater
from .memory_store import MemoryStore
from .file_store import FileStore
from .memory_query import MemoryQuery
from .memory_report import MemoryReport

__all__ = [
    "MemoryEngine",
    "LessonRegistry", "Lesson",
    "ImprovementLog", "ImprovementEntry",
    "ParameterHistory", "ParameterRecord",
    "BacktestRecord", "BacktestRecords",
    "ChangeLog", "ChangeEntry",
    "DNAUpdater",
    "MemoryStore",
    "FileStore",
    "MemoryQuery",
    "MemoryReport",
]
