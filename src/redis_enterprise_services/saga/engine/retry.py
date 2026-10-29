import time
from typing import Protocol

from redis_enterprise_services.config.saga_settings import RetrySettings


class Sleeper(Protocol):
    def sleep(self, *, seconds: float) -> None: ...


class SystemSleeper(Sleeper):
    def sleep(self, *, seconds: float) -> None:
        time.sleep(seconds)


def pause(*, retry: RetrySettings, attempt: int, sleeper: Sleeper) -> None:
    sleeper.sleep(seconds=retry.backoff_seconds * attempt)
