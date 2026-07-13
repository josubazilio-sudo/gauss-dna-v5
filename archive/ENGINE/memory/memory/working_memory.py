import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from ENGINE.council.council_types import CouncilVerdict
from ENGINE.council.evidence_types import EvidenceGraph
from ENGINE.council.health_types import HealthScore
from ENGINE.council.weight_types import WeightDistribution
from ENGINE.market.market_types import MarketContext
from ENGINE.memory.working_memory_types import WorkingMemory
from ENGINE.meta.meta_types import MetaVerdict
from ENGINE.policy.policy_types import PolicyVerdict
from ENGINE.skills.skill_opinion import SkillOpinion
from ENGINE.world.world_types import WorldModel

log = logging.getLogger(__name__)


class WorkingMemoryManager:

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus
        self._current: Optional[WorkingMemory] = None

    @property
    def current(self) -> Optional[WorkingMemory]:
        return self._current

    def create(
        self,
        cycle_id: Optional[str] = None,
        market_context: Optional[MarketContext] = None,
        world_model: Optional[WorldModel] = None,
        skill_opinions: Optional[Dict[str, SkillOpinion]] = None,
        evidence_graph: Optional[EvidenceGraph] = None,
        health_scores: Optional[Dict[str, HealthScore]] = None,
        weight_distribution: Optional[WeightDistribution] = None,
        council_verdict: Optional[CouncilVerdict] = None,
        meta_verdict: Optional[MetaVerdict] = None,
        policy_verdict: Optional[PolicyVerdict] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkingMemory:
        cid = cycle_id or uuid4().hex[:16]
        opinions_list = None
        if skill_opinions is not None:
            opinions_list = list(skill_opinions.values())

        wm = WorkingMemory(
            cycle_id=cid,
            timestamp=datetime.now(timezone.utc),
            market_context=market_context,
            world_model=world_model,
            skill_opinions=opinions_list,
            evidence_graph=evidence_graph,
            health_scores=health_scores,
            weight_distribution=weight_distribution,
            council_verdict=council_verdict,
            meta_verdict=meta_verdict,
            policy_verdict=policy_verdict,
            metadata=metadata or {},
        )

        self._current = wm
        self._publish_created(wm)
        return wm

    def _publish_created(self, wm: WorkingMemory) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(Event(
                EventTypes.WORKING_MEMORY_CREATED,
                {"cycle_id": wm.cycle_id, "wm_hash": WorkingMemory.compute_hash(wm)},
            ))
        except Exception as e:
            log.error("Failed to publish working_memory.created: %s", e)

    def clear(self) -> None:
        self._current = None

    @staticmethod
    def from_dict(data: Dict) -> WorkingMemory:
        from ENGINE.council.evidence_types import EvidenceGraph
        from ENGINE.council.health_types import HealthScore
        from ENGINE.council.weight_types import WeightDistribution
        from ENGINE.council.council_types import CouncilVerdict
        from ENGINE.meta.meta_types import MetaVerdict
        from ENGINE.policy.policy_types import PolicyVerdict
        from ENGINE.market.market_types import MarketContext
        from ENGINE.skills.skill_opinion import SkillOpinion
        from ENGINE.world.world_types import WorldModel

        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)

        mc = data.get("market_context")
        if isinstance(mc, dict):
            from ENGINE.market.market_types import MarketContext, TechnicalIndicators, TrendDirection, MarketRegime, RsiZone, VolatilityZone
            ind_data = mc.get("indicators", {})
            if isinstance(ind_data, dict):
                from ENGINE.market.market_types import TechnicalIndicators
                ind = TechnicalIndicators(**{k: v for k, v in ind_data.items() if k in TechnicalIndicators.__dataclass_fields__})
            else:
                ind = ind_data
            mc_obj = MarketContext(
                pair=mc["pair"],
                timestamp=datetime.fromisoformat(mc["timestamp"]) if isinstance(mc.get("timestamp"), str) else mc.get("timestamp", ts),
                price=mc["price"],
                indicators=ind,
                trend=TrendDirection(mc.get("trend", "neutral")),
                trend_strength=mc.get("trend_strength", 0.0),
                regime=MarketRegime(mc.get("regime", "ranging")),
                regime_confidence=mc.get("regime_confidence", 0.0),
                funding_rate=mc.get("funding_rate", 0.0),
                spread=mc.get("spread", 0.0),
                btc_correlation=mc.get("btc_correlation", 0.0),
                eth_correlation=mc.get("eth_correlation", 0.0),
                btc_dominance=mc.get("btc_dominance", 0.0),
                open_interest=mc.get("open_interest"),
                rsi_zone=RsiZone(mc.get("rsi_zone", "normal")),
                volatility_zone=VolatilityZone(mc.get("volatility_zone", "moderate")),
                market_score=mc.get("market_score", 0.0),
                trend_score=mc.get("trend_score", 0.0),
                momentum_score=mc.get("momentum_score", 0.0),
                volatility_score=mc.get("volatility_score", 0.0),
                liquidity_score=mc.get("liquidity_score", 0.0),
                risk_score=mc.get("risk_score", 1.0),
                confidence_score=mc.get("confidence_score", 0.0),
                institutional_score=mc.get("institutional_score", 0.0),
            )
            mc = mc_obj

        wm_data = data.get("world_model")
        if isinstance(wm_data, dict):
            wm_data = WorldModel.from_dict(wm_data) if hasattr(WorldModel, 'from_dict') else None

        ops = data.get("skill_opinions")
        if isinstance(ops, list):
            ops = [SkillOpinion(**o) for o in ops]

        eg = data.get("evidence_graph")
        if isinstance(eg, dict):
            eg = EvidenceGraph.from_dict(eg)

        hs = data.get("health_scores")
        if isinstance(hs, dict) and hs:
            parsed = {}
            for k, v in hs.items():
                if isinstance(v, dict):
                    parsed[k] = HealthScore.from_dict(v)
                else:
                    parsed[k] = v
            hs = parsed

        wd = data.get("weight_distribution")
        if isinstance(wd, dict):
            wd = WeightDistribution.from_dict(wd)

        cv = data.get("council_verdict")
        if isinstance(cv, dict):
            cv = CouncilVerdict.from_dict(cv)

        mv = data.get("meta_verdict")
        if isinstance(mv, dict):
            mv = MetaVerdict.from_dict(mv)

        pv = data.get("policy_verdict")
        if isinstance(pv, dict):
            pv = PolicyVerdict.from_dict(pv)

        return WorkingMemory(
            cycle_id=data["cycle_id"],
            timestamp=ts,
            market_context=mc,
            world_model=wm_data,
            skill_opinions=ops,
            evidence_graph=eg,
            health_scores=hs,
            weight_distribution=wd,
            council_verdict=cv,
            meta_verdict=mv,
            policy_verdict=pv,
            metadata=data.get("metadata", {}),
        )

    @staticmethod
    def from_json(json_str: str) -> WorkingMemory:
        return WorkingMemoryManager.from_dict(json.loads(json_str))
