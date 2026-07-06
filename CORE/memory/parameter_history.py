"""
Histórico de parâmetros vencedores e perdedores.

Registra configurações de parâmetros e seus resultados
para evitar repetir combinações comprovadamente ruins.
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .memory_store import MemoryStore

log = logging.getLogger(__name__)

_COLLECTION = "parameters"


@dataclass
class ParameterRecord:
    """Registro de parâmetros e seu resultado.

    Attributes:
        param_id: Identificador único.
        strategy: Estratégia à qual os parâmetros pertencem.
        parameters: Dicionário de parâmetros nome -> valor.
        result: 'winning' | 'losing' | 'neutral'.
        metric: Métrica de avaliação (ex: profit_factor, win_rate).
        metric_value: Valor da métrica.
        notes: Observações sobre o resultado.
        backtest_id: ID do backtest关联ado (opcional).
        created_at: Timestamp UTC.
    """
    param_id: str
    strategy: str
    parameters: Dict[str, Any]
    result: str
    metric: str
    metric_value: float
    notes: str
    backtest_id: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        strategy: str,
        parameters: Dict[str, Any],
        result: str = "neutral",
        metric: str = "profit_factor",
        metric_value: float = 0.0,
        notes: str = "",
        backtest_id: str = "",
    ) -> "ParameterRecord":
        return cls(
            param_id=uuid4().hex[:12],
            strategy=strategy,
            parameters=dict(parameters),
            result=result,
            metric=metric,
            metric_value=metric_value,
            notes=notes,
            backtest_id=backtest_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class ParameterHistory:
    """Gerencia o histórico de parâmetros."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, record: ParameterRecord) -> None:
        self._store.save(_COLLECTION, record.param_id, record.to_dict())
        log.info(
            "Parametro registrado: %s [%s] %s=%.4f",
            record.param_id, record.strategy, record.metric, record.metric_value,
        )

    def get(self, param_id: str) -> Optional[ParameterRecord]:
        data = self._store.load(_COLLECTION, param_id)
        if data is None:
            return None
        return ParameterRecord(**data)

    def list_by_result(self, result: str) -> List[ParameterRecord]:
        all_records = self._list_all()
        return [r for r in all_records if r.result == result]

    def list_by_strategy(self, strategy: str) -> List[ParameterRecord]:
        all_records = self._list_all()
        return [r for r in all_records if r.strategy == strategy]

    def _list_all(self) -> List[ParameterRecord]:
        ids = self._store.list_ids(_COLLECTION)
        results = []
        for pid in ids:
            record = self.get(pid)
            if record:
                results.append(record)
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    def count(self) -> int:
        return self._store.count(_COLLECTION)
