import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float: ...


class MonotonicClock(Clock):
    def now(self) -> float:
        return time.monotonic()
