import logging
import time

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.config.state_settings import LockSettings
from redis_enterprise_services.exceptions.saga import DatabaseLockedError
from redis_enterprise_services.saga.lock import DatabaseLock
from redis_enterprise_services.state.redis_keys import RedisKeys

logger: logging.Logger = logging.getLogger(name=__name__)

ACQUIRE_ALL: str = """
for _, key in ipairs(KEYS) do
    local holder = redis.call('GET', key)
    if holder then
        return holder
    end
end
for _, key in ipairs(KEYS) do
    redis.call('SET', key, ARGV[1])
end
return false
"""

RELEASE_OWNED: str = """
for _, key in ipairs(KEYS) do
    if redis.call('GET', key) == ARGV[1] then
        redis.call('DEL', key)
    end
end
return true
"""


class RedisDatabaseLock(DatabaseLock):
    def __init__(self, *, client: Redis, keys: RedisKeys, settings: LockSettings) -> None:
        self._keys: RedisKeys = keys
        self._settings: LockSettings = settings
        self._acquire_all: Script = client.register_script(script=ACQUIRE_ALL)
        self._release_owned: Script = client.register_script(script=RELEASE_OWNED)

    def acquire(self, *, keys: list[str], owner: str) -> None:
        deadline: float = time.monotonic() + self._settings.wait_timeout_seconds
        while (holder := self._acquire_all(keys=self._lock_keys(keys=keys), args=[owner])) is not None:
            if time.monotonic() >= deadline:
                logger.error(msg=f"{keys} still locked by {holder}")
                raise DatabaseLockedError(message=f"{keys} locked by {holder}")
            logger.warning(msg=f"{keys} locked by {holder}, waiting")
            time.sleep(self._settings.poll_seconds)
        logger.info(msg=f"{keys} locked by {owner}")

    def release(self, *, keys: list[str], owner: str) -> None:
        self._release_owned(keys=self._lock_keys(keys=keys), args=[owner])
        logger.info(msg=f"{keys} released by {owner}")

    def _lock_keys(self, *, keys: list[str]) -> list[str]:
        return [self._keys.lock(key=key) for key in keys]
