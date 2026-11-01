import logging

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.operations.heartbeat_store import HeartbeatStore
from redis_enterprise_services.state.redis_keys import RedisKeys

logger: logging.Logger = logging.getLogger(name=__name__)

BEAT_ALL: str = """
for _, key in ipairs(KEYS) do
    redis.call('SET', key, 'alive', 'EX', ARGV[1])
end
return true
"""


class RedisHeartbeatStore(HeartbeatStore):
    def __init__(self, *, client: Redis, keys: RedisKeys, ttl_seconds: int) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._ttl_seconds: int = ttl_seconds
        self._beat_all: Script = client.register_script(script=BEAT_ALL)

    def beat(self, *, trace_ids: list[str]) -> None:
        self._beat_all(
            keys=[self._keys.heartbeat(trace_id=trace_id) for trace_id in trace_ids], args=[self._ttl_seconds]
        )
        logger.debug(msg=f"heartbeat of {len(trace_ids)} operations")

    def stop(self, *, trace_id: str) -> None:
        self._client.delete(self._keys.heartbeat(trace_id=trace_id))
        logger.debug(msg=f"heartbeat of {trace_id} stopped")
