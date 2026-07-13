LATENCY_THRESHOLDS = {
    "excellent": 100,
    "good": 500,
    "fair": 1000,
    "degraded": 5000,
}

EXCELLENT_MIN = 0.9
GOOD_MIN = 0.7
FAIR_MIN = 0.5
DEGRADED_MIN = 0.3

WEIGHT_AVAILABILITY = 0.20
WEIGHT_RELIABILITY = 0.20
WEIGHT_PRECISION = 0.25
WEIGHT_LATENCY = 0.15
WEIGHT_STABILITY = 0.20

PENALTY_TIMEOUT_PER_UNIT = 0.05
PENALTY_ERROR_PER_UNIT = 0.10
PENALTY_MAX = 0.80

REC_LATENCY_HIGH = "Investigar aumento de latencia"
REC_ERRORS = "Verificar falhas recorrentes"
REC_PRECISION_LOW = "Recalibrar parametros"
REC_ALGORITHM = "Revisar algoritmo"
REC_WEIGHT_REDUCE = "Reduzir peso da Skill"
REC_AVAILABILITY_LOW = "Verificar disponibilidade do servico"
REC_STABILITY_LOW = "Investigar instabilidade nas execucoes"
