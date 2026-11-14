from collections.abc import Callable

from redis_enterprise_services.timing.clock import Clock
from redis_enterprise_services.timing.sleeper import Sleeper


class DeadlinePolling:
    def __init__(self, *, clock: Clock, sleeper: Sleeper) -> None:
        self._clock: Clock = clock
        self._sleeper: Sleeper = sleeper

    def poll_until(
        self, *, is_done: Callable[[], bool], timeout_seconds: float, poll_interval_seconds: float
    ) -> bool:
        deadline: float = self._clock.monotonic_seconds() + timeout_seconds
        while not is_done():
            wait_seconds: float | None = next_wait_seconds(
                now=self._clock.monotonic_seconds(),
                deadline=deadline,
                poll_interval_seconds=poll_interval_seconds,
            )
            if wait_seconds is None:
                return False
            self._sleeper.sleep(seconds=wait_seconds)
        return True


def next_wait_seconds(*, now: float, deadline: float, poll_interval_seconds: float) -> float | None:
    if now >= deadline:
        return None
    return min(poll_interval_seconds, deadline - now)
