"""
Modelo de dados para entries de conhecimento.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class KnowledgeArea(Enum):
    """Áreas oficiais de conhecimento do QuantOS."""
    MARKET = "market"
    TRADING = "trading"
    ORDERFLOW = "orderflow"
    RISK = "risk"
    STATISTICS = "statistics"
    ENGINEERING = "engineering"
    AI = "ai"


_AREA_LABELS = {
    KnowledgeArea.MARKET: "Mercado",
    KnowledgeArea.TRADING: "Trading",
    KnowledgeArea.ORDERFLOW: "Order Flow",
    KnowledgeArea.RISK: "Gestão de Risco",
    KnowledgeArea.STATISTICS: "Estatística",
    KnowledgeArea.ENGINEERING: "Engenharia",
    KnowledgeArea.AI: "Inteligência Artificial",
}


def area_label(area: KnowledgeArea) -> str:
    """Retorna o label amigável de uma área."""
    return _AREA_LABELS.get(area, area.value)


@dataclass
class KnowledgeEntry:
    """Um entry de conhecimento validado.

    Attributes:
        entry_id: Identificador único.
        area: Área de conhecimento.
        title: Título do entry.
        content: Conteúdo markdown/texto.
        source: Fonte do conhecimento.
        tags: Lista de tags para busca.
        version: Versão do entry.
        author: Autor do entry.
        references: Referências.
        created_at: Timestamp UTC de criação.
    """
    entry_id: str
    area: KnowledgeArea
    title: str
    content: str
    source: str
    tags: List[str]
    version: str
    author: str
    references: List[str]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["area"] = self.area.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeEntry":
        data = dict(data)
        data["area"] = KnowledgeArea(data["area"])
        return cls(**data)

    @classmethod
    def create(
        cls,
        area: KnowledgeArea,
        title: str,
        content: str,
        source: str = "manual",
        tags: Optional[List[str]] = None,
        version: str = "1.0.0",
        author: str = "system",
        references: Optional[List[str]] = None,
    ) -> "KnowledgeEntry":
        """Cria um novo entry de conhecimento.

        Args:
            area: Área de conhecimento.
            title: Título descritivo.
            content: Conteúdo do conhecimento.
            source: Fonte (manual, pesquisa, auditoria, etc).
            tags: Tags para categorização e busca.
            version: Versão semântica.
            author: Responsável pelo entry.
            references: IDs de documentos ou URLs relacionados.

        Returns:
            KnowledgeEntry configurado.
        """
        return cls(
            entry_id=uuid4().hex[:12],
            area=area,
            title=title,
            content=content,
            source=source,
            tags=tags or [],
            version=version,
            author=author,
            references=references or [],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
