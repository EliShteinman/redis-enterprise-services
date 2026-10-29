from unittest.mock import MagicMock, create_autospec

import pytest
from redis import Redis

from redis_enterprise_services.config.state_settings import LockSettings
from redis_enterprise_services.exceptions.saga import DatabaseLockedError
from redis_enterprise_services.state.redis_database_lock import RedisDatabaseLock
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.timing.clock import Clock
from redis_enterprise_services.timing.sleeper import Sleeper

SETTINGS: LockSettings = LockSettings(wait_timeout_seconds=10, poll_seconds=2)


class StepClock(Clock):
    def __init__(self) -> None:
        self.time: float = 0

    def now(self) -> float:
        return self.time


class AdvancingSleeper(Sleeper):
    def __init__(self, *, clock: StepClock) -> None:
        self._clock: StepClock = clock

    def sleep(self, *, seconds: float) -> None:
        self._clock.time += seconds


def lock_with(*, holders: list[str | None]) -> RedisDatabaseLock:
    client: MagicMock = create_autospec(spec=Redis, instance=True)
    acquire_all: MagicMock = MagicMock(side_effect=holders)
    client.register_script.side_effect = [acquire_all, MagicMock()]
    clock: StepClock = StepClock()
    return RedisDatabaseLock(
        client=client,
        keys=RedisKeys(prefix="res:", hash_tag="state"),
        settings=SETTINGS,
        sleeper=AdvancingSleeper(clock=clock),
        clock=clock,
    )


def test_a_lock_released_while_waiting_is_taken() -> None:
    lock_with(holders=["other-saga", None]).acquire(keys=["cluster1/db1"], owner="trace-1")


def test_a_lock_still_held_after_the_wait_timeout_is_refused() -> None:
    with pytest.raises(expected_exception=DatabaseLockedError):
        lock_with(holders=["other-saga"] * 10).acquire(keys=["cluster1/db1"], owner="trace-1")
