"""
Sistema de Conhecimento Oficial do QuantOS.

Base validada de conhecimento sobre mercado, trading,
risco, estatística, engenharia e inteligência artificial.
"""

from .knowledge_engine import KnowledgeEngine
from .knowledge_entry import KnowledgeEntry, KnowledgeArea
from .knowledge_registry import KnowledgeRegistry
from .knowledge_search import KnowledgeSearch
from .knowledge_validator import KnowledgeValidator
from .knowledge_report import KnowledgeReport

__all__ = [
    "KnowledgeEngine",
    "KnowledgeEntry", "KnowledgeArea",
    "KnowledgeRegistry",
    "KnowledgeSearch",
    "KnowledgeValidator",
    "KnowledgeReport",
]
