import os
import json
import time
import logging
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from .update_engine import UpdateEngine

log = logging.getLogger(__name__)

STATE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "MEMORY", "state"
)
STATE_FILE = os.path.join(STATE_DIR, "active_operations.json")

COOLDOWN_SECONDS = 600  # 10 minutes
EXPIRY_HOURS = 72


class OperationStatus(Enum):
    ATIVA = "ATIVA"
    ENCERRADA = "ENCERRADA"
    CANCELADA = "CANCELADA"


@dataclass
class ActiveOperation:
    operation_id: str
    asset: str
    timeframe: str
    direction: str
    entry: float = 0.0
    stop: float = 0.0
    take_profit: float = 0.0
    risk_reward: float = 0.0
    score: float = 0.0
    quality: float = 0.0
    probability: float = 0.0
    confidence: float = 0.0
    consensus: float = 0.0
    confluence: float = 0.0
    flow: float = 0.0
    liquidity: float = 0.0
    structure: float = 0.0
    risk_field: float = 0.0
    trend: str = ""
    kalman: str = ""
    conviction: str = ""
    expectancy: str = ""
    coherence: float = 0.0
    timestamp: float = 0.0
    last_sent_data: Dict[str, Any] = field(default_factory=dict)
    status: str = "ATIVA"
    last_update_ts: float = 0.0

    def is_expired(self) -> bool:
        if self.timestamp == 0:
            return False
        return (time.time() - self.timestamp) > EXPIRY_HOURS * 3600


def _make_op_id(asset: str, timeframe: str) -> str:
    return f"{asset.upper()}_{timeframe}"


@dataclass
class Resolution:
    action: str  # "new" | "send" | "skip"
    update_label: Optional[str] = None
    skip_reason: str = ""
    impact_score: int = 0


class ActiveSignalManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._operations: Dict[str, ActiveOperation] = {}
        self._load()

    def get_active(self, asset: str, timeframe: str) -> Optional[ActiveOperation]:
        op_id = _make_op_id(asset, timeframe)
        op = self._operations.get(op_id)
        if op and op.status == "ATIVA" and not op.is_expired():
            return op
        return None

    def resolve(
        self, asset: str, timeframe: str, direction: str, new_data: Dict[str, Any]
    ) -> Resolution:
        op = self.get_active(asset, timeframe)
        if op is None:
            return Resolution(action="new")

        if op.direction != direction.upper():
            self.close(op.operation_id)
            log.info(
                "Operacao encerrada. Reversao detectada para %s_%s: %s -> %s",
                asset, timeframe, op.direction, direction.upper(),
            )
            return Resolution(
                action="reversal",
                update_label="🔄 REVERSÃO DE TENDÊNCIA",
            )

        impact = UpdateEngine.calculate_impact_score(op.last_sent_data, new_data)
        if not impact.is_send:
            return Resolution(
                action="skip",
                skip_reason="ignored",
                impact_score=impact.impact_score,
            )

        if self._is_in_cooldown(op) and impact.impact_score < 80:
            return Resolution(
                action="skip",
                skip_reason="cooldown",
                impact_score=impact.impact_score,
            )

        return Resolution(
            action="send",
            update_label=impact.update_type,
            impact_score=impact.impact_score,
        )

    def create(
        self, asset: str, timeframe: str, direction: str, data: Dict[str, Any]
    ) -> ActiveOperation:
        op_id = _make_op_id(asset, timeframe)
        now = time.time()
        op = ActiveOperation(
            operation_id=op_id,
            asset=asset.upper(),
            timeframe=timeframe.upper(),
            direction=direction.upper(),
            entry=float(data.get("entry_price", data.get("entry", 0))),
            stop=float(data.get("stop_loss", data.get("stop", 0))),
            take_profit=float(
                data.get("take_profit_1", data.get("take_profit", 0))
            ),
            risk_reward=float(data.get("risk_reward", 0)),
            score=float(
                data.get("overall_score_value", data.get("score", 0))
            ),
            quality=float(
                data.get("quality_score", data.get("quality", 0))
            ),
            probability=float(
                data.get("probability", 0)
                if isinstance(data.get("probability"), (int, float))
                else data.get("probability", {}).get("probability", 0)
            ),
            confidence=float(
                data.get("conviction", data.get("confidence", 0))
            ),
            consensus=float(
                data.get("consensus", data.get("consensus_score", 0))
            ),
            confluence=float(data.get("confluence_score", 0)),
            flow=float(data.get("flow_score", 0)),
            liquidity=float(data.get("liquidity_score", 0)),
            structure=float(data.get("structure_score", 0)),
            risk_field=float(data.get("risk_score", 0)),
            trend=str(data.get("trend", "")),
            kalman=str(data.get("kalman_direction", "")),
            conviction=str(data.get("conviction_level", "")),
            expectancy=str(data.get("expectancy_level", "")),
            coherence=float(
                data.get("coherence_score", {})
                .get("coherence_score", 0)
                if isinstance(data.get("coherence_score"), dict)
                else 0
            ),
            timestamp=now,
            last_sent_data=data,
            status="ATIVA",
            last_update_ts=now,
        )
        self._operations[op_id] = op
        self._save()
        log.info(
            "Operacao criada: %s_%s %s (score=%.1f)",
            asset, timeframe, direction.upper(), op.score,
        )
        return op

    def mark_sent(self, operation_id: str, data: Dict[str, Any]) -> None:
        op = self._operations.get(operation_id)
        if not op:
            return
        op.last_sent_data = data
        op.last_update_ts = time.time()
        op.entry = float(
            data.get("entry_price", data.get("entry", op.entry))
        )
        op.stop = float(
            data.get("stop_loss", data.get("stop", op.stop))
        )
        op.take_profit = float(
            data.get("take_profit_1", data.get("take_profit", op.take_profit))
        )
        op.risk_reward = float(data.get("risk_reward", op.risk_reward))
        op.score = float(
            data.get("overall_score_value", data.get("score", op.score))
        )
        op.direction = str(data.get("direction", op.direction)).upper()
        self._save()

    def close(self, operation_id: str) -> None:
        op = self._operations.get(operation_id)
        if op and op.status == "ATIVA":
            op.status = "ENCERRADA"
            self._save()
            log.info(
                "Operacao encerrada: %s (score=%.1f)",
                operation_id, op.score,
            )

    def cancel(self, operation_id: str) -> None:
        op = self._operations.get(operation_id)
        if op and op.status == "ATIVA":
            op.status = "CANCELADA"
            self._save()
            log.info(
                "Operacao cancelada: %s (score=%.1f)",
                operation_id, op.score,
            )

    def _is_in_cooldown(self, op: ActiveOperation) -> bool:
        return (time.time() - op.last_update_ts) < COOLDOWN_SECONDS

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [
            oid for oid, op in self._operations.items()
            if op.status == "ATIVA" and op.timestamp > 0
            and (now - op.timestamp) > EXPIRY_HOURS * 3600
        ]
        for oid in expired:
            self._operations[oid].status = "ENCERRADA"
        if expired:
            self._save()
            log.info("ActiveSignalManager: expired %d operations", len(expired))
        return len(expired)

    def active_count(self) -> int:
        return sum(
            1 for op in self._operations.values()
            if op.status == "ATIVA" and not op.is_expired()
        )

    def get_recently_active_pairs(self, window_hours: float = 4.0) -> list:
        cutoff = time.time() - window_hours * 3600
        return [
            op.asset for op in self._operations.values()
            if op.timestamp >= cutoff
        ]

    def _save(self) -> None:
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            data = [asdict(op) for op in self._operations.values()]
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            log.warning("ActiveSignalManager: error saving: %s", e)

    def _load(self) -> None:
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                for d in data:
                    d["status"] = d.get("status", "ATIVA")
                    if isinstance(d.get("status"), str):
                        pass
                    op = ActiveOperation(**d)
                    self._operations[op.operation_id] = op
                log.info(
                    "ActiveSignalManager: loaded %d operations",
                    len(self._operations),
                )
        except Exception as e:
            log.warning("ActiveSignalManager: error loading: %s", e)
