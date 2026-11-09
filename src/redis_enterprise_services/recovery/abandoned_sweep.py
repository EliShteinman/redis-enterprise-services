import logging

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.recovery.finalize_abandoned_result import FinalizeAbandonedResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus

logger: logging.Logger = logging.getLogger(name=__name__)


class AbandonedSweep:
    def __init__(self, *, store: AbandonedStore, public_errors: PublicErrors) -> None:
        self._store: AbandonedStore = store
        self._public_errors: PublicErrors = public_errors

    def sweep(self) -> None:
        trace_ids: list[str] = self._store.abandoned_candidate_trace_ids()
        logger.debug(msg=f"checking {len(trace_ids)} running operations without a heartbeat")
        for trace_id in trace_ids:
            self._finalize_abandoned(trace_id=trace_id)

    def _finalize_abandoned(self, *, trace_id: str) -> None:
        saga: StoredSaga | None = self._store.find_saga(trace_id=trace_id)
        operation: Operation = operation_after_crash(
            trace_id=trace_id, saga=saga, error=self._public_errors.internal_error()
        )
        result: FinalizeAbandonedResult = self._store.finalize_if_still_abandoned(
            operation=operation, expected_saga=saga, interrupted_saga=interrupted_running_saga(saga=saga)
        )
        log_finalize_result(trace_id=trace_id, status=operation.status, result=result)


def operation_after_crash(*, trace_id: str, saga: StoredSaga | None, error: PublicError) -> Operation:
    status: OperationStatus = status_after_crash(saga=saga)
    return Operation(
        trace_id=trace_id,
        status=status,
        error=error,
        not_rolled_back=[] if status is OperationStatus.ROLLED_BACK else None,
    )


def status_after_crash(*, saga: StoredSaga | None) -> OperationStatus:
    if saga is None:
        return OperationStatus.REJECTED
    if saga.record is not None and saga.record.status is SagaStatus.ROLLED_BACK:
        return OperationStatus.ROLLED_BACK
    return OperationStatus.REQUIRES_MANUAL_INTERVENTION


def interrupted_running_saga(*, saga: StoredSaga | None) -> SagaRecord | None:
    if saga is None or saga.record is None or saga.record.status is not SagaStatus.RUNNING:
        return None
    return saga.record.interrupted_copy()


def log_finalize_result(*, trace_id: str, status: OperationStatus, result: FinalizeAbandonedResult) -> None:
    if result is FinalizeAbandonedResult.FINALIZED:
        logger.critical(
            msg=f"operation {trace_id} was left by a pod that stopped, finalized as {status.value}"
        )
    elif result is FinalizeAbandonedResult.SAGA_CHANGED:
        logger.warning(msg=f"saga {trace_id} changed while it was checked, it is checked again next time")
