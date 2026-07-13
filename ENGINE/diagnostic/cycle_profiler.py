import json
import logging
import statistics
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List

log = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).resolve().parents[2] / "MEMORY" / "profiling"


class CycleProfiler:
    """Mede o tempo real gasto em cada etapa do pipeline (candles, indicadores,
    scanner, decisao/risco, telegram) por ciclo de scan, para identificar
    gargalos antes de alterar limites como MAX_SCAN_PAIRS."""

    def __init__(self):
        self._lock = threading.Lock()
        self._samples: Dict[str, List[float]] = {}
        self._cycle_start = 0.0
        self._cycle_num = 0

    def start_cycle(self, cycle_num: int) -> None:
        self._cycle_num = cycle_num
        self._cycle_start = time.time()
        with self._lock:
            self._samples = {}

    def record(self, stage: str, seconds: float) -> None:
        with self._lock:
            self._samples.setdefault(stage, []).append(seconds)

    @contextmanager
    def stage(self, name: str):
        t0 = time.time()
        try:
            yield
        finally:
            self.record(name, time.time() - t0)

    def end_cycle(self, pairs_processed: int) -> dict:
        total = time.time() - self._cycle_start
        with self._lock:
            samples = {k: list(v) for k, v in self._samples.items()}

        summary = {
            "cycle": self._cycle_num,
            "pairs": pairs_processed,
            "total_seconds": round(total, 2),
            "stages": {},
        }
        for stage, values in samples.items():
            if not values:
                continue
            ordered = sorted(values)
            summary["stages"][stage] = {
                "count": len(values),
                "total_s": round(sum(values), 3),
                "avg_ms": round(statistics.mean(values) * 1000, 2),
                "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1] * 1000, 2),
                "max_ms": round(ordered[-1] * 1000, 2),
            }

        resumo = " | ".join(
            f"{k}={v['total_s']}s(avg={v['avg_ms']}ms,p95={v['p95_ms']}ms)"
            for k, v in summary["stages"].items()
        )
        log.info(
            "PROFILING ciclo #%d: %.1fs total | %d pares | %s",
            self._cycle_num, total, pairs_processed, resumo,
        )
        try:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            out = PROFILE_DIR / f"cycle_{self._cycle_num}.json"
            out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning("CycleProfiler: falha ao gravar profiling em disco: %s", e)
        return summary
