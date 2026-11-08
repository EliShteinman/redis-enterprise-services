import logging
from typing import cast

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.config.state_settings import LockSettings
from redis_enterprise_services.exceptions.saga import ResourcesLockedError
from redis_enterprise_services.saga.contract.saga_lock import SagaLock
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.timing.clock import Clock
from redis_enterprise_services.timing.sleeper import Sleeper

logger: logging.Logger = logging.getLogger(name=__name__)

ACQUIRE_ALL: str = """
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


class RedisDatabaseLock(SagaLock):
    def __init__(
        self, *, client: Redis, keys: RedisKeys, settings: LockSettings, sleeper: Sleeper, clock: Clock
    ) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._settings: LockSettings = settings
        self._sleeper: Sleeper = sleeper
        self._clock: Clock = clock
        self._acquire_all: Script = client.register_script(script=ACQUIRE_ALL)
        self._release_owned: Script = client.register_script(script=RELEASE_OWNED)

    def acquire(self, *, keys: list[str], owner: str) -> None:
        deadline: float = self._clock.monotonic_seconds() + self._settings.wait_timeout_seconds
        holder: str | None = self._acquire_all(keys=self._lock_keys(keys=keys, owner=owner), args=[owner])
        if holder is not None:
            logger.warning(msg=f"{keys} locked by {holder}, waiting")
        while holder is not None:
            if self._clock.monotonic_seconds() >= deadline:
                logger.error(msg=f"{keys} still locked by {holder}")
                raise ResourcesLockedError(message=f"{keys} locked by {holder}")
            self._sleeper.sleep(seconds=self._settings.poll_interval_seconds)
            holder = self._acquire_all(keys=self._lock_keys(keys=keys, owner=owner), args=[owner])
        logger.info(msg=f"{keys} locked by {owner}")

    def ensure_held(self, *, keys: list[str], owner: str) -> None:
        holders: list[str | None] = cast(
            list[str | None], self._client.mget(keys=[self._keys.lock(key=key) for key in keys])
        )
        if any(holder != owner for holder in holders):
            logger.error(msg=f"{keys} are no longer held by {owner}: {holders}")
            raise ResourcesLockedError(message=f"{keys} are no longer held by {owner}")

    def release(self, *, keys: list[str], owner: str) -> None:
        released: int = self._release_owned(keys=self._lock_keys(keys=keys, owner=owner), args=[owner])
        logger.info(msg=f"{released} of {keys} released by {owner}")

    def _lock_keys(self, *, keys: list[str], owner: str) -> list[str]:
        return [self._keys.held_locks(owner=owner), *(self._keys.lock(key=key) for key in keys)]
