"""
Registro imutável de lições aprendidas.

Cada lição é registrada uma vez e nunca pode ser alterada.
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .memory_store import MemoryStore

log = logging.getLogger(__name__)

_COLLECTION = "lessons"


@dataclass
class Lesson:
    """Uma lição aprendida registrada permanentemente.

    Attributes:
        lesson_id: Identificador único.
        title: Título resumido da lição.
        description: Descrição detalhada.
        category: Categoria (ex: 'architecture', 'trading', 'security').
        severity: Gravidade ('info', 'warning', 'critical').
        source: Origem da lição (ex: 'audit', 'bug', 'review').
        created_at: Timestamp UTC de criação.
    """
    lesson_id: str
    title: str
    description: str
    category: str
    severity: str
    source: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        category: str = "general",
        severity: str = "info",
        source: str = "manual",
    ) -> "Lesson":
        return cls(
            lesson_id=uuid4().hex[:12],
            title=title,
            description=description,
            category=category,
            severity=severity,
            source=source,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class LessonRegistry:
    """Gerencia o registro de lições aprendidas."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, lesson: Lesson) -> None:
        self._store.save(_COLLECTION, lesson.lesson_id, lesson.to_dict())
        log.info("Licao registrada: %s [%s]", lesson.lesson_id, lesson.title)

    def get(self, lesson_id: str) -> Optional[Lesson]:
        data = self._store.load(_COLLECTION, lesson_id)
        if data is None:
            return None
        return Lesson(**data)

    def list_all(self) -> List[Lesson]:
        ids = self._store.list_ids(_COLLECTION)
        results = []
        for lid in ids:
            lesson = self.get(lid)
            if lesson:
                results.append(lesson)
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    def count(self) -> int:
        return self._store.count(_COLLECTION)
