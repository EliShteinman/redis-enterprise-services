import json
import logging
from typing import cast

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import EXPIRING_STATUSES, OperationStatus
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.recovery.mark_abandoned_result import MarkAbandonedResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.saga_record import SagaRecord
from redis_enterprise_services.state.redis_keys import RedisKeys

logger: logging.Logger = logging.getLogger(name=__name__)

NO_EXPIRY: int = 0
STATUS_FIELD: str = "status"
NO_SAGA: str = ""
MARK_ABANDONED_RESULT_BY_CODE: dict[int, MarkAbandonedResult] = {
    0: MarkAbandonedResult.NOT_ABANDONED,
    1: MarkAbandonedResult.MARKED,
    2: MarkAbandonedResult.SAGA_CHANGED,
}

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
    return 2
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
if ARGV[6] == '' then
    for i = 6, #KEYS do
        if redis.call('GET', KEYS[i]) == ARGV[2] then
            redis.call('DEL', KEYS[i])
        end
        redis.call('SREM', KEYS[5], KEYS[i])
    end
end
return 1
"""


class RedisAbandonedStore(AbandonedStore):
    def __init__(self, *, client: Redis, keys: RedisKeys, finished_operation_ttl_seconds: int) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._finished_operation_ttl_seconds: int = finished_operation_ttl_seconds
        self._mark_abandoned: Script = client.register_script(script=MARK_ABANDONED)

    def open_trace_ids_without_heartbeat(self) -> list[str]:
        open_ids: set[str] = cast(set[str], self._client.smembers(name=self._keys.open_operations()))
        return sorted(
            trace_id
            for trace_id in open_ids
            if not self._client.exists(self._keys.heartbeat(trace_id=trace_id))
            and self._running_or_not_recorded(trace_id=trace_id)
        )

    def find_saga(self, *, trace_id: str) -> StoredSaga | None:
        raw: str | None = cast(str | None, self._client.get(name=self._keys.saga(saga_id=trace_id)))
        if raw is None:
            return None
        return StoredSaga(raw_json=raw, record=SagaRecord.model_validate_json(json_data=raw))

    def _running_or_not_recorded(self, *, trace_id: str) -> bool:
        stored: str | None = cast(str | None, self._client.get(name=self._keys.operation(trace_id=trace_id)))
        if stored is None:
            return True
        try:
            parsed: object = json.loads(stored)
        except json.JSONDecodeError:
            logger.error(msg=f"operation {trace_id} cannot be read, it is skipped")
            return False
        if not isinstance(parsed, dict):
            logger.error(msg=f"operation {trace_id} is not a JSON object, it is skipped")
            return False
        return cast(dict[str, object], parsed).get(STATUS_FIELD) == OperationStatus.RUNNING.value

    def mark_abandoned(
        self, *, operation: Operation, expected_saga: StoredSaga | None, interrupted_saga: SagaRecord | None
    ) -> MarkAbandonedResult:
        trace_id: str = operation.trace_id
        held_locks: str = self._keys.held_locks(owner=trace_id)
        result_code: int = self._mark_abandoned(
            keys=[
                self._keys.operation(trace_id=trace_id),
                self._keys.open_operations(),
                self._keys.heartbeat(trace_id=trace_id),
                self._keys.saga(saga_id=trace_id),
                held_locks,
                *sorted(cast(set[str], self._client.smembers(name=held_locks))),
            ],
            args=[
                operation.model_dump_json(),
                trace_id,
                self._finished_operation_ttl_seconds if operation.status in EXPIRING_STATUSES else NO_EXPIRY,
                NO_SAGA if interrupted_saga is None else interrupted_saga.model_dump_json(),
                OperationStatus.RUNNING.value,
                NO_SAGA if expected_saga is None else expected_saga.raw_json,
            ],
        )
        result: MarkAbandonedResult = MARK_ABANDONED_RESULT_BY_CODE[result_code]
        logger.debug(msg=f"operation {trace_id}: {result.value}")
        return result
