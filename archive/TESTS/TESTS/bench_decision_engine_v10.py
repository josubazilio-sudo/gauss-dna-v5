
import unittest
import time
import tracemalloc
import statistics
import concurrent.futures
import hashlib
import json
from datetime import datetime, timezone
from typing import List, Dict, Any

from ENGINE.decision.decision_types import DecisionContext, DecisionResult, DecisionStatus
from ENGINE.decision.decision_engine_v10 import DecisionEngineV10
from TESTS.test_decision_engine_v10 import (
    MockWorkingMemory, MockDecisionTrace, MockWorldModel,
    MockSkillsEngine, MockEvidenceGraph, MockHealthMonitor,
    MockWeightDistribution, MockCouncilVerdict, MockMetaIntelligence, MockPolicyEngine
)

class DecisionEngineBenchmark:
    def __init__(self):
        # Setup Mocks
        self.mock_wm = MockWorkingMemory()
        self.mock_trace = MockDecisionTrace()
        self.mock_world_model = MockWorldModel()
        self.mock_skills_engine = MockSkillsEngine()
        self.mock_evidence_graph = MockEvidenceGraph()
        self.mock_health_monitor = MockHealthMonitor()
        self.mock_weight_dist = MockWeightDistribution()
        self.mock_council_verdict = MockCouncilVerdict()
        self.mock_meta_intelligence = MockMetaIntelligence()
        self.mock_policy_engine = MockPolicyEngine()

        self.engine = DecisionEngineV10(
            world_model=self.mock_world_model,
            skill_opinions=self.mock_skills_engine,
            evidence_graph=self.mock_evidence_graph,
            health_scores=self.mock_health_monitor,
            weight_distribution=self.mock_weight_dist,
            council_verdict=self.mock_council_verdict,
            meta_intelligence=self.mock_meta_intelligence,
            policy_engine=self.mock_policy_engine,
            working_memory=self.mock_wm,
            decision_trace=self.mock_trace
        )

    def _create_context(self, cycle_id: str) -> DecisionContext:
        ctx = DecisionContext(
            cycle_id=cycle_id,
            timestamp=datetime.now(timezone.utc),
            meta_verdict="PROCEED",
            policy_verdict="APPROVED",
            world_model=self.mock_world_model,
            skill_opinions=self.mock_skills_engine,
            evidence_graph=self.mock_evidence_graph,
            health_scores={"global_health": 0.8},
            weight_distribution={"default": 1.0},
            council_verdict="PROCEED",
            working_memory=self.mock_wm,
            decision_trace=self.mock_trace
        )
        ctx.context_hash = hashlib.sha256(json.dumps(ctx.to_dict(), sort_keys=True).encode()).hexdigest()
        return ctx

    def run_benchmark(self, n_cycles: int, threads: int = 1):
        latencies = []
        tracemalloc.start()
        start_time = time.perf_counter()

        def _task(_):
            ctx = self._create_context("bench")
            t0 = time.perf_counter()
            self.engine.make_decision(ctx)
            return time.perf_counter() - t0

        if threads == 1:
            for i in range(n_cycles):
                latencies.append(_task(i))
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                latencies = list(executor.map(_task, range(n_cycles)))

        total_time = time.perf_counter() - start_time
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        latencies_ms = [l * 1000 for l in latencies]
        return {
            "n": n_cycles,
            "total_time": total_time,
            "throughput": n_cycles / total_time,
            "avg_latency_ms": statistics.mean(latencies_ms),
            "p50_ms": statistics.median(latencies_ms),
            "p95_ms": statistics.quantiles(latencies_ms, n=20)[18], # Approximate P95
            "p99_ms": statistics.quantiles(latencies_ms, n=100)[98], # Approximate P99
            "min_ms": min(latencies_ms),
            "max_ms": max(latencies_ms),
            "peak_mem_mb": peak / 1024 / 1024
        }

if __name__ == "__main__":
    bench = DecisionEngineBenchmark()
    for n in [100, 1000, 10000]:
        print(f"--- Running {n} cycles ---")
        results = bench.run_benchmark(n)
        print(json.dumps(results, indent=2))
