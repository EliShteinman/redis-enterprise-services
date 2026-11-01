import logging

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import EXPIRING
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.state.redis_keys import RedisKeys

logger: logging.Logger = logging.getLogger(name=__name__)

SAVE_OPEN: str = """
redis.call('SET', KEYS[1], ARGV[1])
redis.call('SADD', KEYS[2], ARGV[2])
return true
"""

SAVE_FINISHED: str = """
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
redis.call('SREM', KEYS[2], ARGV[2])
return true
"""


class RedisOperationStore(OperationStore):
    def __init__(self, *, client: Redis, keys: RedisKeys, finished_ttl_seconds: int) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._finished_ttl_seconds: int = finished_ttl_seconds
        self._save_open: Script = client.register_script(script=SAVE_OPEN)
        self._save_finished: Script = client.register_script(script=SAVE_FINISHED)

    def save(self, *, operation: Operation) -> None:
        keys: list[str] = [self._keys.operation(trace_id=operation.trace_id), self._keys.open_operations()]
        if operation.status in EXPIRING:
            self._save_finished(
                keys=keys, args=[operation.model_dump_json(), operation.trace_id, self._finished_ttl_seconds]
            )
        else:
            self._save_open(keys=keys, args=[operation.model_dump_json(), operation.trace_id])
        logger.info(msg=f"operation {operation.trace_id} stored as {operation.status.value}")

    def find(self, *, trace_id: str) -> Operation | None:
        stored: str | bytes | None = self._client.get(name=self._keys.operation(trace_id=trace_id))
        if stored is None:
            logger.info(msg=f"operation {trace_id} is not known")
            return None
        return Operation.model_validate_json(json_data=stored)
