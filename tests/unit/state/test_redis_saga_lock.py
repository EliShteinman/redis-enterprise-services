from unittest.mock import MagicMock, create_autospec

import pytest
from redis import Redis

from redis_enterprise_services.config.state_settings import LockSettings
from redis_enterprise_services.exceptions.saga import ResourcesLockedError
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_saga_lock import RedisSagaLock
from redis_enterprise_services.timing.clock import Clock
from redis_enterprise_services.timing.sleeper import Sleeper

SETTINGS: LockSettings = LockSettings(wait_timeout_seconds=10, poll_interval_seconds=2)


class ManualClock(Clock):
    def __init__(self) -> None:
        self.time: float = 0

    def monotonic_seconds(self) -> float:
        return self.time


class AdvancingSleeper(Sleeper):
    def __init__(self, *, clock: ManualClock) -> None:
        self._clock: ManualClock = clock

    def sleep(self, *, seconds: float) -> None:
        self._clock.time += seconds


def lock_with(*, acquire_all: MagicMock) -> RedisSagaLock:
    client: MagicMock = create_autospec(spec=Redis, instance=True)
    client.register_script.side_effect = [acquire_all, MagicMock()]
    clock: ManualClock = ManualClock()
    return RedisSagaLock(
        client=client,
        keys=RedisKeys(key_prefix="res:", hash_tag="state"),
        settings=SETTINGS,
        sleeper=AdvancingSleeper(clock=clock),
        clock=clock,
    )


def test_a_lock_released_while_waiting_is_taken() -> None:
    acquire_all: MagicMock = MagicMock(side_effect=["other-saga", None])

    lock_with(acquire_all=acquire_all).acquire(keys=["cluster1/db1"], owner="trace-1")

    assert acquire_all.call_count == 2


def test_a_lock_still_held_after_the_wait_timeout_is_refused() -> None:
    with pytest.raises(expected_exception=ResourcesLockedError):
        lock_with(acquire_all=MagicMock(side_effect=["other-saga"] * 10)).acquire(
            keys=["cluster1/db1"], owner="trace-1"
        )
