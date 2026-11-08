from collections.abc import Iterator

from redis_enterprise_services.timing.sleeper import Sleeper


def paced_attempts(*, attempts: int, backoff_step_seconds: float, sleeper: Sleeper) -> Iterator[int]:
    for attempt in range(1, attempts + 1):
        yield attempt
        if attempt < attempts:
            sleeper.sleep(seconds=backoff_step_seconds * attempt)
