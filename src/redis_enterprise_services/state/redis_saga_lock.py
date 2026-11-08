import logging
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
        last_holder: str | None = None

        def acquired_now() -> bool:
            nonlocal last_holder
            holder: str | None = self._try_acquire(lock_keys=lock_keys, owner=owner)
            if holder is not None and last_holder is None:
                logger.warning(msg=f"{lock_keys} locked by {holder}, waiting")
            last_holder = holder
            return holder is None

        if not self._deadline_polling.poll_until(
            is_done=acquired_now,
            timeout_seconds=self._settings.wait_timeout_seconds,
            poll_interval_seconds=self._settings.poll_interval_seconds,
        ):
            logger.error(msg=f"{lock_keys} still locked by {last_holder}")
            raise ResourcesLockedError(message=f"{lock_keys} locked by {last_holder}")
        logger.info(msg=f"{lock_keys} locked by {owner}")

    def raise_unless_held(self, *, lock_keys: list[str], owner: str) -> None:
        holders: list[str | None] = cast(
            list[str | None], self._client.mget(keys=[self._keys.lock(lock_key=key) for key in lock_keys])
        )
        if any(holder != owner for holder in holders):
            logger.error(msg=f"{lock_keys} are no longer held by {owner}: {holders}")
            raise ResourcesLockedError(message=f"{lock_keys} are no longer held by {owner}")

    def release(self, *, lock_keys: list[str], owner: str) -> None:
        released: int = self._release_owned(
            keys=self._held_set_and_lock_keys(lock_keys=lock_keys, owner=owner), args=[owner]
        )
        logger.info(msg=f"{released} of {lock_keys} released by {owner}")

    def _try_acquire(self, *, lock_keys: list[str], owner: str) -> str | None:
        return self._acquire_all_or_return_holder(
            keys=self._held_set_and_lock_keys(lock_keys=lock_keys, owner=owner), args=[owner]
        )

    def _held_set_and_lock_keys(self, *, lock_keys: list[str], owner: str) -> list[str]:
        return [self._keys.held_locks(owner=owner), *(self._keys.lock(lock_key=key) for key in lock_keys)]
