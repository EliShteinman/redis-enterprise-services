import time
from typing import Protocol


class Sleeper(Protocol):
    def sleep(self, *, seconds: float) -> None: ...


class SystemSleeper(Sleeper):
    def sleep(self, *, seconds: float) -> None:
        time.sleep(seconds)
