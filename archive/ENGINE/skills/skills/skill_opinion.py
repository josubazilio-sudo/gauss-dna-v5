import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillMetrics:
    availability: float = 1.0
    avg_latency_ms: float = 0.0
    historical_precision: float = 0.0
    reliability: float = 1.0
    last_execution: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    recent_errors: int = 0
    total_calls: int = 0
    successful_calls: int = 0


@dataclass(frozen=True)
class SkillOpinion:
    skill_name: str
    confidence: float
    risk: float
    probability: float
    evidence: List[str]
    observations: str
    success: bool
    metrics: SkillMetrics = field(default_factory=SkillMetrics)

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")
        if not 0.0 <= self.risk <= 1.0:
            raise ValueError(f"risk must be 0.0-1.0, got {self.risk}")
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"probability must be 0.0-1.0, got {self.probability}")
