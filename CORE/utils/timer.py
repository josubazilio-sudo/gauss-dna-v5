import logging
import time
from contextlib import contextmanager
from typing import Generator

log = logging.getLogger(__name__)


class Timer:
    def __init__(self):
        self.start_time: float = 0.0
        self.elapsed: float = 0.0

    def start(self) -> None:
        self.start_time = time.time()
        log.debug("Timer started")

    def stop(self) -> float:
        self.elapsed = time.time() - self.start_time
        log.debug("Timer stopped: %.4fs", self.elapsed)
        return self.elapsed

    def reset(self) -> None:
        self.start_time = 0.0
        self.elapsed = 0.0
        log.debug("Timer reset")


@contextmanager
def measure_time() -> Generator[Timer, None, None]:
    timer = Timer()
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()
