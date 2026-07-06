"""
Registro de histórico de melhorias.

Armazena mudanças aprovadas e rejeitadas com contexto completo.
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .memory_store import MemoryStore

log = logging.getLogger(__name__)

_COLLECTION = "improvements"


@dataclass
class ImprovementEntry:
    """Registro de uma melhoria.

    Attributes:
        improvement_id: Identificador único.
        title: Título da melhoria.
        description: Descrição detalhada.
        category: Categoria (feature, bugfix, refactor, optimization).
        status: 'approved' | 'rejected' | 'pending'.
        reason: Motivo da decisão.
        module: Módulo afetado.
        version: Versão em que foi aplicada.
        author: Responsável pela mudança.
        created_at: Timestamp UTC.
    """
    improvement_id: str
    title: str
    description: str
    category: str
    status: str
    reason: str
    module: str
    version: str
    author: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        category: str = "feature",
        status: str = "pending",
        reason: str = "",
        module: str = "unknown",
        version: str = "0.0.0",
        author: str = "system",
    ) -> "ImprovementEntry":
        return cls(
            improvement_id=uuid4().hex[:12],
            title=title,
            description=description,
            category=category,
            status=status,
            reason=reason,
            module=module,
            version=version,
            author=author,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class ImprovementLog:
    """Gerencia o registro de melhorias."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, entry: ImprovementEntry) -> None:
        self._store.save(_COLLECTION, entry.improvement_id, entry.to_dict())
        log.info("Melhoria registrada: %s [%s]", entry.improvement_id, entry.title)

    def get(self, improvement_id: str) -> Optional[ImprovementEntry]:
        data = self._store.load(_COLLECTION, improvement_id)
        if data is None:
            return None
        return ImprovementEntry(**data)

    def list_by_status(self, status: str) -> List[ImprovementEntry]:
        all_items = self._list_all()
        return [i for i in all_items if i.status == status]

    def list_by_module(self, module: str) -> List[ImprovementEntry]:
        all_items = self._list_all()
        return [i for i in all_items if i.module == module]

    def _list_all(self) -> List[ImprovementEntry]:
        ids = self._store.list_ids(_COLLECTION)
        results = []
        for iid in ids:
            entry = self.get(iid)
            if entry:
                results.append(entry)
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    def count(self) -> int:
        return self._store.count(_COLLECTION)
