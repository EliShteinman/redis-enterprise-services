from typing import Protocol

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.recovery.abandoned_mark_result import AbandonedMarkResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


class AbandonedStore(Protocol):
    def open_trace_ids_without_heartbeat(self) -> list[str]: ...

    def find_saga(self, *, trace_id: str) -> StoredSaga | None: ...

    def mark_abandoned(
        self, *, operation: Operation, expected_saga: StoredSaga | None, interrupted_saga: SagaRecord | None
    ) -> AbandonedMarkResult: ...
