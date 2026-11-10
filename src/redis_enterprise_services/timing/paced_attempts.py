from collections.abc import Iterator

from redis_enterprise_services.config.saga_settings import RetrySettings
from redis_enterprise_services.timing.sleeper import Sleeper


def paced_attempts(*, retry: RetrySettings, sleeper: Sleeper) -> Iterator[int]:
    for attempt in range(1, retry.attempts + 1):
        yield attempt
        if attempt < retry.attempts:
            sleeper.sleep(seconds=retry.backoff_step_seconds * attempt)
