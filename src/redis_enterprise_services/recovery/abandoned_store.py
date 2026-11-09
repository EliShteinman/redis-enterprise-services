from typing import Protocol

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.recovery.finalize_abandoned_result import FinalizeAbandonedResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


class AbandonedStore(Protocol):
    def abandoned_candidate_trace_ids(self) -> list[str]: ...

    def find_saga(self, *, trace_id: str) -> StoredSaga | None: ...

    def finalize_if_still_abandoned(
        self, *, operation: Operation, expected_saga: StoredSaga | None, interrupted_saga: SagaRecord | None
    ) -> FinalizeAbandonedResult: ...
