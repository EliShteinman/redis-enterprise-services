import logging

from pydantic import ValidationError

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.recovery.mark_result import MarkResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus

logger: logging.Logger = logging.getLogger(name=__name__)


class AbandonedSweep:
    def __init__(self, *, store: AbandonedStore, errors: PublicErrors) -> None:
        self._store: AbandonedStore = store
        self._errors: PublicErrors = errors

    def sweep(self) -> None:
        trace_ids: list[str] = self._store.without_heartbeat()
        logger.debug(msg=f"checking {len(trace_ids)} open operations without a heartbeat")
        for trace_id in trace_ids:
            try:
                self._find_outcome(trace_id=trace_id)
            except ValidationError:
                logger.exception(msg=f"the records of operation {trace_id} cannot be read, it is skipped")

    def _find_outcome(self, *, trace_id: str) -> None:
        saga: StoredSaga | None = self._store.saga_of(trace_id=trace_id)
        status: OperationStatus = status_after_crash(saga=saga)
        operation: Operation = Operation(
            trace_id=trace_id,
            status=status,
            error=self._errors.internal(),
            not_rolled_back=[] if status is OperationStatus.ROLLED_BACK else None,
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


def status_after_crash(*, saga: StoredSaga | None) -> OperationStatus:
    if saga is None:
        return OperationStatus.REJECTED
    if saga.record.status is SagaStatus.ROLLED_BACK:
        return OperationStatus.ROLLED_BACK
    return OperationStatus.REQUIRES_MANUAL_INTERVENTION


def stopped(*, saga: StoredSaga | None) -> SagaRecord | None:
    if saga is None or saga.record.status is not SagaStatus.RUNNING:
        return None
    halted: SagaRecord = saga.record.model_copy(deep=True)
    halted.mark_interrupted()
    return halted
