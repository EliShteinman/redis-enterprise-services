import logging
from collections.abc import Callable
from typing import cast

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.config.state_settings import LockSettings
from redis_enterprise_services.exceptions.saga import ResourcesLockedError
from redis_enterprise_services.saga.contract.saga_lock import SagaLock
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling

logger: logging.Logger = logging.getLogger(name=__name__)

ACQUIRE_ALL_OR_RETURN_HOLDER: str = """
for i = 2, #KEYS do
    local holder = redis.call('GET', KEYS[i])
    if holder then
        return holder
    end
end
for i = 2, #KEYS do
    redis.call('SET', KEYS[i], ARGV[1])
    redis.call('SADD', KEYS[1], KEYS[i])
end
return false
"""

RELEASE_OWNED: str = """
local released = 0
for i = 2, #KEYS do
    if redis.call('GET', KEYS[i]) == ARGV[1] then
        released = released + redis.call('DEL', KEYS[i])
    end
    redis.call('SREM', KEYS[1], KEYS[i])
end
return released
"""


class RedisSagaLock(SagaLock):
    def __init__(
        self, *, client: Redis, keys: RedisKeys, settings: LockSettings, deadline_polling: DeadlinePolling
    ) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._settings: LockSettings = settings
        self._deadline_polling: DeadlinePolling = deadline_polling
        self._acquire_all_or_return_holder: Script = client.register_script(
            script=ACQUIRE_ALL_OR_RETURN_HOLDER
        )
        self._release_owned: Script = client.register_script(script=RELEASE_OWNED)

    def acquire(self, *, lock_keys: list[str], owner: str) -> None:
        attempts: LockAttempts = LockAttempts(
            lock_keys=lock_keys, try_acquire=lambda: self._try_acquire(lock_keys=lock_keys, owner=owner)
        )
        if not self._deadline_polling.poll_until(
            is_done=attempts.acquired_now,
            timeout_seconds=self._settings.wait_timeout_seconds,
            poll_interval_seconds=self._settings.poll_interval_seconds,
        ):
            logger.error(msg=f"{lock_keys} still locked by {attempts.last_holder}")
            raise ResourcesLockedError(message=f"{lock_keys} locked by {attempts.last_holder}")
        logger.info(msg=f"{lock_keys} locked by {owner}")

    def raise_unless_held(self, *, lock_keys: list[str], owner: str) -> None:
        holders: list[str | None] = self._holders(lock_keys=lock_keys)
        if not all_held_by(holders=holders, owner=owner):
            logger.error(msg=f"{lock_keys} are no longer held by {owner}: {holders}")
            raise ResourcesLockedError(message=f"{lock_keys} are no longer held by {owner}")

    def release(self, *, lock_keys: list[str], owner: str) -> None:
        released: int = self._release_owned(
            keys=self._held_set_and_lock_keys(lock_keys=lock_keys, owner=owner), args=[owner]
        )
        logger.info(msg=f"{released} of {lock_keys} released by {owner}")

    def _holders(self, *, lock_keys: list[str]) -> list[str | None]:
        return cast(
            list[str | None], self._client.mget(keys=[self._keys.lock(lock_key=key) for key in lock_keys])
        )

    def _try_acquire(self, *, lock_keys: list[str], owner: str) -> str | None:
        return self._acquire_all_or_return_holder(
            keys=self._held_set_and_lock_keys(lock_keys=lock_keys, owner=owner), args=[owner]
        )

    def _held_set_and_lock_keys(self, *, lock_keys: list[str], owner: str) -> list[str]:
        return [self._keys.held_locks(owner=owner), *(self._keys.lock(lock_key=key) for key in lock_keys)]


class LockAttempts:
    def __init__(self, *, lock_keys: list[str], try_acquire: Callable[[], str | None]) -> None:
        self._lock_keys: list[str] = lock_keys
        self._try_acquire: Callable[[], str | None] = try_acquire
        self.last_holder: str | None = None

    def acquired_now(self) -> bool:
        holder: str | None = self._try_acquire()
        if is_first_wait(holder=holder, last_holder=self.last_holder):
            logger.warning(msg=f"{self._lock_keys} locked by {holder}, waiting")
        self.last_holder = holder
        return holder is None


def is_first_wait(*, holder: str | None, last_holder: str | None) -> bool:
    return holder is not None and last_holder is None


def all_held_by(*, holders: list[str | None], owner: str) -> bool:
    return all(holder == owner for holder in holders)
