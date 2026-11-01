from typing import Protocol

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.recovery.mark_result import MarkResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.models import SagaRecord


class AbandonedStore(Protocol):
    def without_heartbeat(self) -> list[str]: ...

    def saga_of(self, *, trace_id: str) -> StoredSaga | None: ...

    def mark_abandoned(
        self, *, operation: Operation, read_saga: StoredSaga | None, stopped_saga: SagaRecord | None
    ) -> MarkResult: ...
