import logging

from redis import Redis

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import EXPIRING
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.state.redis_keys import RedisKeys

logger: logging.Logger = logging.getLogger(name=__name__)


class RedisOperationStore(OperationStore):
    def __init__(self, *, client: Redis, keys: RedisKeys, finished_ttl_seconds: int) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._finished_ttl_seconds: int = finished_ttl_seconds

    def save(self, *, operation: Operation) -> None:
        expiry: int | None = self._finished_ttl_seconds if operation.status in EXPIRING else None
        self._client.set(
            name=self._keys.operation(trace_id=operation.trace_id),
            value=operation.model_dump_json(),
            ex=expiry,
        )
        logger.info(msg=f"operation {operation.trace_id} stored as {operation.status.value}")

    def find(self, *, trace_id: str) -> Operation | None:
        stored: str | bytes | None = self._client.get(name=self._keys.operation(trace_id=trace_id))
        if stored is None:
            logger.info(msg=f"operation {trace_id} is not known")
            return None
        return Operation.model_validate_json(json_data=stored)
