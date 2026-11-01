import logging
from typing import cast

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import EXPIRING, OperationStatus
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.saga.contract.models import SagaRecord
from redis_enterprise_services.state.redis_keys import RedisKeys

logger: logging.Logger = logging.getLogger(name=__name__)

KEEP_OPEN: int = 0
NO_SAGA: str = ""

MARK_ABANDONED: str = """
if redis.call('EXISTS', KEYS[3]) == 1 then
    return 0
end
local stored = redis.call('GET', KEYS[1])
if not stored then
    redis.call('SREM', KEYS[2], ARGV[2])
    return 0
end
if cjson.decode(stored)['status'] ~= ARGV[5] then
    return 0
end
local saga = redis.call('GET', KEYS[4])
if (saga or '') ~= ARGV[6] then
    return 0
end
if ARGV[3] == '0' then
    redis.call('SET', KEYS[1], ARGV[1])
else
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
    redis.call('SREM', KEYS[2], ARGV[2])
end
if ARGV[4] ~= '' then
    redis.call('SET', KEYS[4], ARGV[4])
end
return 1
"""


class RedisAbandonedStore(AbandonedStore):
    def __init__(self, *, client: Redis, keys: RedisKeys, finished_ttl_seconds: int) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._finished_ttl_seconds: int = finished_ttl_seconds
        self._mark_abandoned: Script = client.register_script(script=MARK_ABANDONED)

    def without_heartbeat(self) -> list[str]:
        open_ids: set[str] = cast(set[str], self._client.smembers(name=self._keys.open_operations()))
        return sorted(
            trace_id
            for trace_id in open_ids
            if not self._client.exists(self._keys.heartbeat(trace_id=trace_id))
            and self._running(trace_id=trace_id)
        )

    def _running(self, *, trace_id: str) -> bool:
        stored: str | bytes | None = self._client.get(name=self._keys.operation(trace_id=trace_id))
        return (
            stored is None
            or Operation.model_validate_json(json_data=stored).status is OperationStatus.RUNNING
        )

    def mark_abandoned(
        self, *, operation: Operation, read_saga: SagaRecord | None, stopped_saga: SagaRecord | None
    ) -> bool:
        trace_id: str = operation.trace_id
        marked: int = self._mark_abandoned(
            keys=[
                self._keys.operation(trace_id=trace_id),
                self._keys.open_operations(),
                self._keys.heartbeat(trace_id=trace_id),
                self._keys.saga(saga_id=trace_id),
            ],
            args=[
                operation.model_dump_json(),
                trace_id,
                self._finished_ttl_seconds if operation.status in EXPIRING else KEEP_OPEN,
                NO_SAGA if stopped_saga is None else stopped_saga.model_dump_json(),
                OperationStatus.RUNNING.value,
                NO_SAGA if read_saga is None else read_saga.model_dump_json(),
            ],
        )
        logger.debug(msg=f"operation {trace_id} {'marked' if marked else 'left as it is'}")
        return marked == 1
