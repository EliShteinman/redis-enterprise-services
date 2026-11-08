import logging

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import EXPIRING_STATUSES
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.state.redis_keys import RedisKeys

logger: logging.Logger = logging.getLogger(name=__name__)

SAVE_WITHOUT_EXPIRY_AND_ADD_TO_OPEN_SET: str = """
redis.call('SET', KEYS[1], ARGV[1])
redis.call('SADD', KEYS[2], ARGV[2])
return true
"""

START_IF_ABSENT: str = """
local existing = redis.call('GET', KEYS[1])
if existing then
    return existing
end
redis.call('SET', KEYS[1], ARGV[1])
redis.call('SADD', KEYS[2], ARGV[2])
redis.call('SET', KEYS[3], 'alive', 'EX', ARGV[3])
return false
"""

SAVE_WITH_EXPIRY_AND_REMOVE_FROM_OPEN_SET: str = """
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
redis.call('SREM', KEYS[2], ARGV[2])
return true
"""


class RedisOperationStore(OperationStore):
    def __init__(
        self,
        *,
        client: Redis,
        keys: RedisKeys,
        finished_ttl_seconds: int,
        heartbeat_ttl_seconds: int,
    ) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._finished_ttl_seconds: int = finished_ttl_seconds
        self._heartbeat_ttl_seconds: int = heartbeat_ttl_seconds
        self._save_without_expiry_and_add_to_open_set: Script = client.register_script(
            script=SAVE_WITHOUT_EXPIRY_AND_ADD_TO_OPEN_SET
        )
        self._save_with_expiry_and_remove_from_open_set: Script = client.register_script(
            script=SAVE_WITH_EXPIRY_AND_REMOVE_FROM_OPEN_SET
        )
        self._start_if_absent_script: Script = client.register_script(script=START_IF_ABSENT)

    def start_if_absent(self, *, operation: Operation) -> Operation | None:
        existing: str | None = self._start_if_absent_script(
            keys=[
                *self._record_and_open_set_keys(trace_id=operation.trace_id),
                self._keys.heartbeat(trace_id=operation.trace_id),
            ],
            args=[operation.model_dump_json(), operation.trace_id, self._heartbeat_ttl_seconds],
        )
        if existing is None:
            logger.info(msg=f"operation {operation.trace_id} started")
            return None
        logger.info(msg=f"operation {operation.trace_id} already exists")
        return Operation.model_validate_json(json_data=existing)

    def save(self, *, operation: Operation) -> None:
        keys: list[str] = self._record_and_open_set_keys(trace_id=operation.trace_id)
        if operation.status in EXPIRING_STATUSES:
            self._save_with_expiry_and_remove_from_open_set(
                keys=keys,
                args=[operation.model_dump_json(), operation.trace_id, self._finished_ttl_seconds],
            )
        else:
            self._save_without_expiry_and_add_to_open_set(
                keys=keys, args=[operation.model_dump_json(), operation.trace_id]
            )
        logger.info(msg=f"operation {operation.trace_id} stored as {operation.status.value}")

    def find(self, *, trace_id: str) -> Operation | None:
        stored: str | bytes | None = self._client.get(name=self._keys.operation(trace_id=trace_id))
        if stored is None:
            logger.info(msg=f"operation {trace_id} is not known")
            return None
        return Operation.model_validate_json(json_data=stored)

    def _record_and_open_set_keys(self, *, trace_id: str) -> list[str]:
        return [self._keys.operation(trace_id=trace_id), self._keys.open_trace_ids()]
