"""
Registro oficial das áreas de conhecimento e suas categorias.
"""

from typing import Dict, List

from .knowledge_entry import KnowledgeArea


class KnowledgeRegistry:
    """Centraliza o registro de áreas e categorias de conhecimento."""

    _AREAS: Dict[KnowledgeArea, List[str]] = {
        KnowledgeArea.MARKET: [
            "regimes", "tendencia", "lateralizacao", "volatilidade",
            "liquidez", "funding", "correlacao",
        ],
        KnowledgeArea.TRADING: [
            "smart_money", "order_blocks", "fair_value_gap",
            "liquidity_sweep", "bos", "choch", "market_structure",
        ],
        KnowledgeArea.ORDERFLOW: [
            "delta", "cvd", "volume", "absorcao",
            "agressao", "desequilibrio",
        ],
        KnowledgeArea.RISK: [
            "position_size", "stop_loss", "take_profit",
            "drawdown", "exposicao", "risk_reward",
        ],
        KnowledgeArea.STATISTICS: [
            "win_rate", "profit_factor", "expectancia", "payoff",
            "monte_carlo", "walk_forward", "robustez",
        ],
        KnowledgeArea.ENGINEERING: [
            "arquitetura", "clean_code", "modularidade",
            "performance", "seguranca", "testes",
        ],
        KnowledgeArea.AI: [
            "prompt_engineering", "raciocinio", "auditoria",
            "governanca", "evolucao", "aprendizado",
        ],
    }

    def categories(self, area: KnowledgeArea) -> List[str]:
        """Retorna as categorias de uma área."""
        return self._AREAS.get(area, [])

    def areas(self) -> List[KnowledgeArea]:
        """Retorna todas as áreas registradas."""
        return list(self._AREAS.keys())

    def search_categories(self, term: str) -> Dict[KnowledgeArea, List[str]]:
        """Busca categorias por termo textual."""
        results: Dict[KnowledgeArea, List[str]] = {}
        term_lower = term.lower()
        for area, cats in self._AREAS.items():
            matched = [c for c in cats if term_lower in c.lower()]
            if matched:
                results[area] = matched
        return results
