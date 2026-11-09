import logging
from typing import cast

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.state.record_expiry import finished_ttl_or_keep_open
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.tracked_record_writer import TrackedRecordWriter

logger: logging.Logger = logging.getLogger(name=__name__)

CREATE_IF_ABSENT: str = """
local existing = redis.call('GET', KEYS[1])
if existing then
    return existing
end
redis.call('SET', KEYS[1], ARGV[1])
redis.call('SADD', KEYS[2], ARGV[2])
redis.call('SET', KEYS[3], 'alive', 'EX', ARGV[3])
return false
"""


class RedisOperationStore(OperationStore):
    def __init__(
        self,
        *,
        client: Redis,
        keys: RedisKeys,
        record_writer: TrackedRecordWriter,
        finished_ttl_seconds: int,
        heartbeat_ttl_seconds: int,
    ) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._record_writer: TrackedRecordWriter = record_writer
        self._finished_ttl_seconds: int = finished_ttl_seconds
        self._heartbeat_ttl_seconds: int = heartbeat_ttl_seconds
        self._create_if_absent_script: Script = client.register_script(script=CREATE_IF_ABSENT)

    def create_if_absent(self, *, operation: Operation) -> Operation | None:
        existing: str | None = self._create_if_absent_script(
            keys=[
                self._keys.operation(trace_id=operation.trace_id),
                self._keys.open_trace_ids(),
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
        self._record_writer.save(
            record_key=self._keys.operation(trace_id=operation.trace_id),
            tracking_set_key=self._keys.open_trace_ids(),
            member=operation.trace_id,
            record_json=operation.model_dump_json(),
            ttl_seconds=finished_ttl_or_keep_open(
                has_ended_cleanly=operation.has_ended_cleanly(),
                finished_ttl_seconds=self._finished_ttl_seconds,
            ),
        )
        logger.info(msg=f"operation {operation.trace_id} stored as {operation.status.value}")

    def find(self, *, trace_id: str) -> Operation | None:
        stored: str | None = cast(str | None, self._client.get(name=self._keys.operation(trace_id=trace_id)))
        if stored is None:
            logger.info(msg=f"operation {trace_id} is not known")
            return None
        return Operation.model_validate_json(json_data=stored)
