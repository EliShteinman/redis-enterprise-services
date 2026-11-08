import time
from typing import Protocol


class Clock(Protocol):
    def monotonic_seconds(self) -> float: ...


class MonotonicClock(Clock):
    def monotonic_seconds(self) -> float:
        return time.monotonic()
