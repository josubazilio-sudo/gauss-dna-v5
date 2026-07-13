"""
Ferramenta temporaria de medicao para a RFC de recalibracao de sinais.
Registra, para TODO sinal avaliado (aprovado ou nao), os scores brutos e o
estado dos motores de tendencia — usado para calibrar os novos thresholds
com dados reais antes de trava-los em producao. Ver RFC_RECALIBRACAO_SINAIS_INSTITUCIONAL.md.
"""
import csv
import logging
import threading
from pathlib import Path

log = logging.getLogger(__name__)

OUT_PATH = Path(__file__).resolve().parents[2] / "MEMORY" / "profiling" / "calibration_measurement.csv"

_lock = threading.Lock()
_header_written = False


def _regime_direction(regime: str) -> str:
    r = (regime or "").lower()
    if "up" in r:
        return "up"
    if "down" in r:
        return "down"
    return "neutral"


def _kalman_direction_normalized(kalman_dir: str) -> str:
    k = (kalman_dir or "").upper()
    if "UP" in k or "LONG" in k or "ALT" in k:
        return "up"
    if "DOWN" in k or "SHORT" in k or "BAIX" in k:
        return "down"
    return "neutral"


def record(pair: str, tf: str, sd, sig) -> None:
    global _header_written
    scores = getattr(sig, "scores", None) if sig is not None else None
    row = {
        "pair": pair,
        "timeframe": tf,
        "direction": sd.direction,
        "quality": round(sd.quality, 4),
        "confidence": round(sig.confidence, 4) if sig is not None else "",
        "consensus": round(sd.consensus, 4),
        "entry_score": round(sd.entry_score, 4),
        "risk_reward": round(sd.risk_reward, 4),
        "regime": sig.regime if sig is not None else "",
        "kalman_direction": sig.kalman_direction if sig is not None else "",
        "kalman_trend_state": sig.kalman_trend_state if sig is not None else "",
        "trend_vs_kalman_conflict": (
            _regime_direction(sig.regime) != "neutral"
            and _kalman_direction_normalized(sig.kalman_direction) != "neutral"
            and _regime_direction(sig.regime) != _kalman_direction_normalized(sig.kalman_direction)
        ) if sig is not None else "",
        "confidence_minus_quality": round(sig.confidence - sd.quality, 4) if sig is not None else "",
        "approved": sd.approved,
        "reject_reason": sd.reject_reason,
        # componentes individuais da formula de quality_score (ver
        # ENGINE/scanner/scanner_scoring.py:compute_quality_score) — para
        # identificar qual componente trava o teto de 0.668 observado.
        "institutional_score": round(scores.institutional_score, 4) if scores else "",
        "structural_score": round(scores.structural_score, 4) if scores else "",
        "market_score": round(scores.market_score, 4) if scores else "",
        "momentum_score": round(scores.momentum_score, 4) if scores else "",
        "liquidity_score": round(scores.liquidity_score, 4) if scores else "",
        "risk_score": round(scores.risk_score, 4) if scores else "",
        "confidence_score_scanner": round(scores.confidence_score, 4) if scores else "",
        "flow_score": round(scores.flow_score, 4) if scores else "",
        "timing_index": round(scores.timing_index, 4) if scores else "",
        "conviction_score": round(scores.conviction_score, 4) if scores else "",
        "entry_score_scanner": round(scores.entry_score, 4) if scores else "",
    }
    try:
        with _lock:
            OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            is_new = _header_written is False and not OUT_PATH.exists()
            with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                if is_new:
                    writer.writeheader()
                    globals()["_header_written"] = True
                writer.writerow(row)
    except Exception as e:
        log.warning("calibration_measurement: falha ao gravar linha: %s", e)
