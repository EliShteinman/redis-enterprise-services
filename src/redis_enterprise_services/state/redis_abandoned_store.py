import json
import logging
from typing import cast

from pydantic import ValidationError
from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.recovery.finalize_abandoned_result import FinalizeAbandonedResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.saga_record import SagaRecord
from redis_enterprise_services.state.record_expiry import KEEP_OPEN_WITHOUT_EXPIRY, finished_ttl_or_keep_open
from redis_enterprise_services.state.redis_keys import RedisKeys

logger: logging.Logger = logging.getLogger(name=__name__)

STATUS_FIELD: str = "status"
NO_INTERRUPTED_SAGA: str = ""
NO_EXPECTED_SAGA: str = ""
RELEASE_LOCKS: str = "1"
KEEP_LOCKS: str = "0"
NOT_ABANDONED_CODE: int = 0
FINALIZED_CODE: int = 1
SAGA_CHANGED_CODE: int = 2
OPERATION_MISSING_CODE: int = 3
FINALIZE_ABANDONED_RESULT_BY_CODE: dict[int, FinalizeAbandonedResult] = {
    NOT_ABANDONED_CODE: FinalizeAbandonedResult.NOT_ABANDONED,
    FINALIZED_CODE: FinalizeAbandonedResult.FINALIZED,
    SAGA_CHANGED_CODE: FinalizeAbandonedResult.SAGA_CHANGED,
    OPERATION_MISSING_CODE: FinalizeAbandonedResult.NOT_ABANDONED,
}

FINALIZE_IF_STILL_ABANDONED: str = f"""
if redis.call('EXISTS', KEYS[3]) == 1 then
    return {NOT_ABANDONED_CODE}
end
local stored = redis.call('GET', KEYS[1])
if not stored then
    redis.call('SREM', KEYS[2], ARGV[2])
    return {OPERATION_MISSING_CODE}
end
if cjson.decode(stored)['{STATUS_FIELD}'] ~= ARGV[5] then
    return {NOT_ABANDONED_CODE}
end
local saga = redis.call('GET', KEYS[4])
if (saga or '') ~= ARGV[6] then
    return {SAGA_CHANGED_CODE}
end
if ARGV[3] == '{KEEP_OPEN_WITHOUT_EXPIRY}' then
    redis.call('SET', KEYS[1], ARGV[1])
else
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
    redis.call('SREM', KEYS[2], ARGV[2])
end
if ARGV[4] ~= '{NO_INTERRUPTED_SAGA}' then
    redis.call('SET', KEYS[4], ARGV[4])
end
if ARGV[7] == '{RELEASE_LOCKS}' then
    for i = 6, #KEYS do
        if redis.call('GET', KEYS[i]) == ARGV[2] then
            redis.call('DEL', KEYS[i])
        end
        redis.call('SREM', KEYS[5], KEYS[i])
    end
end
return {FINALIZED_CODE}
"""


class RedisAbandonedStore(AbandonedStore):
    def __init__(self, *, client: Redis, keys: RedisKeys, finished_ttl_seconds: int) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._finished_ttl_seconds: int = finished_ttl_seconds
        self._finalize_if_still_abandoned_script: Script = client.register_script(
            script=FINALIZE_IF_STILL_ABANDONED
        )

    def abandoned_candidate_trace_ids(self) -> list[str]:
        return sorted(
            trace_id for trace_id in self._open_trace_ids() if self._is_abandoned_candidate(trace_id=trace_id)
        )

    def find_saga(self, *, trace_id: str) -> StoredSaga | None:
        raw: str | None = cast(str | None, self._client.get(name=self._keys.saga_record(saga_id=trace_id)))
        if raw is None:
            return None
        return StoredSaga(raw_json=raw, record=readable_saga_record(trace_id=trace_id, raw_json=raw))

    def finalize_if_still_abandoned(
        self,
        *,
        operation: Operation,
        expected_saga: StoredSaga | None,
        interrupted_saga: SagaRecord | None,
        release_locks: bool,
    ) -> FinalizeAbandonedResult:
        trace_id: str = operation.trace_id
        result_code: int = self._finalize_if_still_abandoned_script(
            keys=finalize_script_keys(
                keys=self._keys,
                trace_id=trace_id,
                held_lock_keys=self._held_lock_keys(trace_id=trace_id) if release_locks else [],
            ),
            args=finalize_script_args(
                operation=operation,
                expected_saga=expected_saga,
                interrupted_saga=interrupted_saga,
                release_locks=release_locks,
                finished_ttl_seconds=self._finished_ttl_seconds,
            ),
        )
        if result_code == OPERATION_MISSING_CODE:
            logger.warning(
                msg=f"operation {trace_id} was open but its record is gone, it leaves the open set; "
                "its locks and saga record are left as they are"
            )
        result: FinalizeAbandonedResult = FINALIZE_ABANDONED_RESULT_BY_CODE[result_code]
        logger.debug(msg=f"operation {trace_id}: {result.value}")
        return result

    def _is_abandoned_candidate(self, *, trace_id: str) -> bool:
        if self._has_heartbeat(trace_id=trace_id):
            return False
        return is_running_or_unrecorded(
            trace_id=trace_id, stored_json=self._stored_operation_json(trace_id=trace_id)
        )

    def _open_trace_ids(self) -> set[str]:
        return cast(set[str], self._client.smembers(name=self._keys.open_trace_ids()))

    def _has_heartbeat(self, *, trace_id: str) -> bool:
        return bool(self._client.exists(self._keys.heartbeat(trace_id=trace_id)))

    def _stored_operation_json(self, *, trace_id: str) -> str | None:
        return cast(str | None, self._client.get(name=self._keys.operation(trace_id=trace_id)))

    def _held_lock_keys(self, *, trace_id: str) -> list[str]:
        return sorted(cast(set[str], self._client.smembers(name=self._keys.held_locks(owner=trace_id))))


def readable_saga_record(*, trace_id: str, raw_json: str) -> SagaRecord | None:
    try:
        return SagaRecord.model_validate_json(json_data=raw_json)
    except ValidationError:
        logger.exception(msg=f"the saga record of operation {trace_id} cannot be read")
        return None


def is_running_or_unrecorded(*, trace_id: str, stored_json: str | None) -> bool:
    if stored_json is None:
        return True
    return stored_status(trace_id=trace_id, stored_json=stored_json) == OperationStatus.RUNNING.value


def stored_status(*, trace_id: str, stored_json: str) -> object:
    try:
        parsed: object = json.loads(stored_json)
    except json.JSONDecodeError:
        logger.error(msg=f"operation {trace_id} cannot be read, it is skipped")
        return None
    if not isinstance(parsed, dict):
        logger.error(msg=f"operation {trace_id} is not a JSON object, it is skipped")
        return None
    return cast(dict[str, object], parsed).get(STATUS_FIELD)


def finalize_script_keys(*, keys: RedisKeys, trace_id: str, held_lock_keys: list[str]) -> list[str]:
    return [
        keys.operation(trace_id=trace_id),
        keys.open_trace_ids(),
        keys.heartbeat(trace_id=trace_id),
        keys.saga_record(saga_id=trace_id),
        keys.held_locks(owner=trace_id),
        *held_lock_keys,
    ]


def finalize_script_args(
    *,
    operation: Operation,
    expected_saga: StoredSaga | None,
    interrupted_saga: SagaRecord | None,
    release_locks: bool,
    finished_ttl_seconds: int,
) -> list[str | int]:
    return [
        operation.model_dump_json(),
        operation.trace_id,
        finished_ttl_or_keep_open(
            has_ended_cleanly=operation.has_ended_cleanly(), finished_ttl_seconds=finished_ttl_seconds
        ),
        NO_INTERRUPTED_SAGA if interrupted_saga is None else interrupted_saga.model_dump_json(),
        OperationStatus.RUNNING.value,
        NO_EXPECTED_SAGA if expected_saga is None else expected_saga.raw_json,
        RELEASE_LOCKS if release_locks else KEEP_LOCKS,
    ]
