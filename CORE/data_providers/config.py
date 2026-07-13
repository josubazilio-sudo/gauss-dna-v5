import os
import logging

log = logging.getLogger(__name__)

DEBUG_MODE = os.getenv("QUANTOS_DEBUG", "false").lower() in ("true", "1", "yes")

# Elegibilidade de pares para discovery — usado por get_symbols() dos providers
# para descartar pares sem liquidez suficiente antes mesmo de tentar escanear.
MIN_VOLUME_USDT = float(os.getenv("QUANTOS_MIN_VOLUME_USDT", "50000"))

# Debug thresholds (only used when DEBUG_MODE=True)
DEBUG_CONSENSUS_MINIMUM_SCORE = 35
DEBUG_QUALITY_GATE_MIN_SCORE = 0.30
DEBUG_QUALITY_GATE_CONFIDENCE_MIN = 0.20
DEBUG_QUALITY_GATE_RISK_MAX = 0.85

# Production thresholds (used when DEBUG_MODE=False)
PROD_CONSENSUS_MINIMUM_SCORE = 70
PROD_QUALITY_GATE_MIN_SCORE = 0.45
PROD_QUALITY_GATE_CONFIDENCE_MIN = 0.40
PROD_QUALITY_GATE_RISK_MAX = 0.70


def log_environment_banner(provider_name: str):
    if DEBUG_MODE:
        from ENGINE.scanner.scanner_config import (
            QUALITY_GATE_MIN_SCORE, QUALITY_GATE_CONFIDENCE_MIN, QUALITY_GATE_RISK_MAX,
        )
        log.info("=" * 60)
        log.info("[DEBUG] Modo DESENVOLVIMENTO ativo")
        log.info("[DEBUG] Mock Provider: %s", provider_name)
        log.info("[DEBUG] Candles reais: NAO")
        log.info("[DEBUG] Threshold reduzido: SIM")
        log.info("[DEBUG] Quality Gate min: %.2f", QUALITY_GATE_MIN_SCORE)
        log.info("[DEBUG] Confidence min: %.2f", QUALITY_GATE_CONFIDENCE_MIN)
        log.info("[DEBUG] Risk max: %.2f", QUALITY_GATE_RISK_MAX)
        log.info("=" * 60)
    else:
        log.info("=" * 60)
        log.info("[PRODUCTION] Modo PRODUCAO ativo")
        log.info("[PRODUCTION] Exchange: %s", provider_name)
        log.info("[PRODUCTION] Candles reais: SIM")
        log.info("[PRODUCTION] Threshold institucional: SIM")
        log.info("[PRODUCTION] Consensus min: %s", PROD_CONSENSUS_MINIMUM_SCORE)
        log.info("=" * 60)
