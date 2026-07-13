from ENGINE.core.state_types import SystemState

FORWARD_ORDER = [
    SystemState.INITIALIZING,
    SystemState.MARKET_READY,
    SystemState.WORLD_READY,
    SystemState.SKILLS_RUNNING,
    SystemState.SKILLS_READY,
    SystemState.GRAPH_BUILDING,
    SystemState.GRAPH_READY,
    SystemState.HEALTH_READY,
    SystemState.WEIGHTS_READY,
    SystemState.CONSENSUS_READY,
    SystemState.META_READY,
    SystemState.POLICY_READY,
    SystemState.WORKING_MEMORY_READY,
    SystemState.DECISION_CONTEXT_READY,
    SystemState.DECISION_READY,
    SystemState.RISK_READY,
    SystemState.EXECUTION_READY,
    SystemState.LEARNING_READY,
    SystemState.FINISHED,
]

FORWARD_MAP = {}
for i in range(len(FORWARD_ORDER) - 1):
    FORWARD_MAP[FORWARD_ORDER[i]] = FORWARD_ORDER[i + 1]

FINAL_STATES = {SystemState.FINISHED, SystemState.CANCELLED}

RECOVERY_MAP = {
    SystemState.ERROR: None,
    SystemState.RECOVERY: None,
    SystemState.RETRY: None,
}

INITIAL_STATE = SystemState.INITIALIZING

MAX_RETRIES = 3

STATE_TIMEOUT_MS = {
    SystemState.INITIALIZING: 30000,
    SystemState.MARKET_READY: 30000,
    SystemState.WORLD_READY: 30000,
    SystemState.SKILLS_RUNNING: 60000,
    SystemState.SKILLS_READY: 10000,
    SystemState.GRAPH_BUILDING: 30000,
    SystemState.GRAPH_READY: 10000,
    SystemState.HEALTH_READY: 10000,
    SystemState.WEIGHTS_READY: 10000,
    SystemState.CONSENSUS_READY: 10000,
    SystemState.META_READY: 10000,
    SystemState.POLICY_READY: 10000,
    SystemState.WORKING_MEMORY_READY: 10000,
    SystemState.DECISION_CONTEXT_READY: 10000,
    SystemState.DECISION_READY: 30000,
    SystemState.RISK_READY: 30000,
    SystemState.EXECUTION_READY: 60000,
    SystemState.LEARNING_READY: 30000,
    SystemState.FINISHED: 5000,
    SystemState.ERROR: 30000,
    SystemState.RECOVERY: 30000,
    SystemState.RETRY: 30000,
    SystemState.CANCELLED: 5000,
}

MODULE_BY_STATE = {
    SystemState.INITIALIZING: "SystemBoot",
    SystemState.MARKET_READY: "MarketDataProvider",
    SystemState.WORLD_READY: "WorldModelEngine",
    SystemState.SKILLS_RUNNING: "SkillsEngine",
    SystemState.SKILLS_READY: "SkillsEngine",
    SystemState.GRAPH_BUILDING: "EvidenceGraphBuilder",
    SystemState.GRAPH_READY: "EvidenceGraphBuilder",
    SystemState.HEALTH_READY: "HealthManager",
    SystemState.WEIGHTS_READY: "DynamicWeightCalculator",
    SystemState.CONSENSUS_READY: "ConsensusEngine",
    SystemState.META_READY: "MetaIntelligence",
    SystemState.POLICY_READY: "PolicyEngine",
    SystemState.WORKING_MEMORY_READY: "WorkingMemoryManager",
    SystemState.DECISION_CONTEXT_READY: "DecisionContextBuilder",
    SystemState.DECISION_READY: "DecisionEngineV10",
    SystemState.RISK_READY: "RiskManager",
    SystemState.EXECUTION_READY: "ExecutionOrchestrator",
    SystemState.LEARNING_READY: "LearningLoop",
    SystemState.FINISHED: "System",
    SystemState.ERROR: "System",
    SystemState.RECOVERY: "RecoveryManager",
    SystemState.RETRY: "RetryManager",
    SystemState.CANCELLED: "System",
}
