import pytest
from redis import Redis

from redis_enterprise_services.config.state_settings import LockSettings
from redis_enterprise_services.exceptions.saga import ResourcesLockedError
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_saga_lock import RedisSagaLock
from redis_enterprise_services.timing.clock import MonotonicClock
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling
from redis_enterprise_services.timing.sleeper import SystemSleeper

OTHER_OWNER: str = "itest-other-owner"


@pytest.fixture
def lock(client: Redis, keys: RedisKeys) -> RedisSagaLock:
    return RedisSagaLock(
        client=client,
        keys=keys,
        settings=LockSettings(wait_timeout_seconds=0, poll_interval_seconds=0.01),
        deadline_polling=DeadlinePolling(clock=MonotonicClock(), sleeper=SystemSleeper()),
    )


def test_acquired_locks_are_held_by_their_owner(
    lock: RedisSagaLock, lock_keys: list[str], trace_id: str
) -> None:
    lock.acquire(lock_keys=lock_keys, owner=trace_id)

    lock.raise_unless_held(lock_keys=lock_keys, owner=trace_id)


def test_a_lock_held_by_another_owner_is_refused(
    client: Redis, keys: RedisKeys, lock: RedisSagaLock, lock_keys: list[str], trace_id: str
) -> None:
    client.set(keys.lock(lock_key=lock_keys[1]), OTHER_OWNER)

    with pytest.raises(expected_exception=ResourcesLockedError):
        lock.acquire(lock_keys=lock_keys, owner=trace_id)


def test_a_refused_acquire_takes_none_of_the_keys(
    client: Redis, keys: RedisKeys, lock: RedisSagaLock, lock_keys: list[str], trace_id: str
) -> None:
    client.set(keys.lock(lock_key=lock_keys[1]), OTHER_OWNER)

    with pytest.raises(expected_exception=ResourcesLockedError):
        lock.acquire(lock_keys=lock_keys, owner=trace_id)

    assert not client.exists(keys.lock(lock_key=lock_keys[0]))


def test_release_frees_the_owners_locks(
    client: Redis, keys: RedisKeys, lock: RedisSagaLock, lock_keys: list[str], trace_id: str
) -> None:
    lock.acquire(lock_keys=lock_keys, owner=trace_id)

    lock.release(lock_keys=lock_keys, owner=trace_id)

    assert client.exists(*[keys.lock(lock_key=lock_key) for lock_key in lock_keys]) == 0


def test_release_leaves_a_lock_that_another_owner_took(
    client: Redis, keys: RedisKeys, lock: RedisSagaLock, lock_keys: list[str], trace_id: str
) -> None:
    lock.acquire(lock_keys=lock_keys, owner=trace_id)
    client.set(keys.lock(lock_key=lock_keys[0]), OTHER_OWNER)

    lock.release(lock_keys=lock_keys, owner=trace_id)

    assert client.get(keys.lock(lock_key=lock_keys[0])) == OTHER_OWNER
