"""
Armazenamento de resultados de backtests.

Registra cada backtest executado com métricas completas
para consulta histórica e comparação entre versões.
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .memory_store import MemoryStore

log = logging.getLogger(__name__)

_COLLECTION = "backtests"


@dataclass
class BacktestRecord:
    """Resultado completo de um backtest.

    Attributes:
        backtest_id: Identificador único.
        strategy: Estratégia testada.
        version: Versão do sistema.
        symbol: Símbolo/par negociado.
        timeframe: Timeframe utilizado.
        date_range: Período do backtest.
        total_trades: Número total de operações.
        win_rate: Percentual de acertos.
        profit_factor: Fator de lucro.
        total_return: Retorno total percentual.
        max_drawdown: Drawdown máximo percentual.
        sharpe: Índice de Sharpe.
        expectancy: Expectância por operação.
        parameters: Parâmetros utilizados.
        notes: Observações.
        passed: Se atingiu os critérios mínimos.
        created_at: Timestamp UTC.
    """
    backtest_id: str
    strategy: str
    version: str
    symbol: str
    timeframe: str
    date_range: str
    total_trades: int
    win_rate: float
    profit_factor: float
    total_return: float
    max_drawdown: float
    sharpe: float
    expectancy: float
    parameters: Dict[str, Any]
    notes: str
    passed: bool
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        strategy: str,
        version: str,
        symbol: str = "",
        timeframe: str = "",
        date_range: str = "",
        total_trades: int = 0,
        win_rate: float = 0.0,
        profit_factor: float = 0.0,
        total_return: float = 0.0,
        max_drawdown: float = 0.0,
        sharpe: float = 0.0,
        expectancy: float = 0.0,
        parameters: Optional[Dict[str, Any]] = None,
        notes: str = "",
    ) -> "BacktestRecord":
        passed = (
            win_rate >= 60.0
            and profit_factor >= 2.50
            and max_drawdown <= 10.0
        )
        return cls(
            backtest_id=uuid4().hex[:12],
            strategy=strategy,
            version=version,
            symbol=symbol,
            timeframe=timeframe,
            date_range=date_range,
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_return=total_return,
            max_drawdown=max_drawdown,
            sharpe=sharpe,
            expectancy=expectancy,
            parameters=parameters or {},
            notes=notes,
            passed=passed,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class BacktestRecords:
    """Gerencia o armazenamento de resultados de backtests."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, record: BacktestRecord) -> None:
        self._store.save(_COLLECTION, record.backtest_id, record.to_dict())
        log.info(
            "Backtest registrado: %s [%s] PF=%.2f WR=%.1f%%",
            record.backtest_id, record.strategy,
            record.profit_factor, record.win_rate,
        )

    def get(self, backtest_id: str) -> Optional[BacktestRecord]:
        data = self._store.load(_COLLECTION, backtest_id)
        if data is None:
            return None
        return BacktestRecord(**data)

    def list_by_strategy(self, strategy: str) -> List[BacktestRecord]:
        all_records = self._list_all()
        return [r for r in all_records if r.strategy == strategy]

    def list_passed(self) -> List[BacktestRecord]:
        all_records = self._list_all()
        return [r for r in all_records if r.passed]

    def best_by_metric(self, metric: str = "profit_factor") -> Optional[BacktestRecord]:
        all_records = self._list_all()
        if not all_records:
            return None
        return max(all_records, key=lambda r: getattr(r, metric, 0.0))

    def _list_all(self) -> List[BacktestRecord]:
        ids = self._store.list_ids(_COLLECTION)
        results = []
        for bid in ids:
            record = self.get(bid)
            if record:
                results.append(record)
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    def count(self) -> int:
        return self._store.count(_COLLECTION)
