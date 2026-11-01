import logging

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.recovery.mark_result import MarkResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.models import SagaRecord, SagaStatus

logger: logging.Logger = logging.getLogger(name=__name__)


class AbandonedSweep:
    def __init__(self, *, store: AbandonedStore, errors: PublicErrors) -> None:
        self._store: AbandonedStore = store
        self._errors: PublicErrors = errors

    def sweep(self) -> None:
        trace_ids: list[str] = self._store.without_heartbeat()
        logger.debug(msg=f"checking {len(trace_ids)} open operations without a heartbeat")
        for trace_id in trace_ids:
            self._check(trace_id=trace_id)

    def _check(self, *, trace_id: str) -> None:
        saga: StoredSaga | None = self._store.saga_of(trace_id=trace_id)
        operation: Operation = Operation(
            trace_id=trace_id,
            status=OperationStatus.REJECTED if saga is None else OperationStatus.REQUIRES_MANUAL_INTERVENTION,
            error=self._errors.internal(),
        )
        result: MarkResult = self._store.mark_abandoned(
            operation=operation, read_saga=saga, stopped_saga=stopped(saga=saga)
        )
        if result is MarkResult.MARKED:
            logger.critical(
                msg=f"operation {trace_id} was left by a pod that stopped, marked {operation.status.value}"
            )
        elif result is MarkResult.SAGA_CHANGED:
            logger.warning(msg=f"saga {trace_id} changed while it was checked, it is checked again next time")


def stopped(*, saga: StoredSaga | None) -> SagaRecord | None:
    if saga is None or saga.record.status is not SagaStatus.RUNNING:
        return None
    halted: SagaRecord = saga.record.model_copy(deep=True)
    halted.stop_running()
    return halted
