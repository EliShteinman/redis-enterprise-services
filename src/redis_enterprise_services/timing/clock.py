import time
from typing import Protocol


class Clock(Protocol):
    def now_seconds(self) -> float: ...


class MonotonicClock(Clock):
    def now_seconds(self) -> float:
        return time.monotonic()
