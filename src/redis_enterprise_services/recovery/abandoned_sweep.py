import logging

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.saga.contract.models import SagaRecord, SagaStatus
from redis_enterprise_services.saga.contract.state import SagaRecordReader

logger: logging.Logger = logging.getLogger(name=__name__)


class AbandonedSweep:
    def __init__(self, *, store: AbandonedStore, records: SagaRecordReader, errors: PublicErrors) -> None:
        self._store: AbandonedStore = store
        self._records: SagaRecordReader = records
        self._errors: PublicErrors = errors

    def sweep(self) -> None:
        trace_ids: list[str] = self._store.without_heartbeat()
        logger.debug(msg=f"checking {len(trace_ids)} open operations without a heartbeat")
        for trace_id in trace_ids:
            self._check(trace_id=trace_id)

    def _check(self, *, trace_id: str) -> None:
        saga: SagaRecord | None = self._records.find(saga_id=trace_id)
        operation: Operation = Operation(
            trace_id=trace_id,
            status=OperationStatus.REJECTED if saga is None else OperationStatus.REQUIRES_MANUAL_INTERVENTION,
            error=self._errors.internal(),
        )
        if self._store.mark_abandoned(operation=operation, stopped_saga=stopped(saga=saga)):
            logger.critical(
                msg=f"operation {trace_id} was left by a pod that stopped, marked {operation.status.value}"
            )


def stopped(*, saga: SagaRecord | None) -> SagaRecord | None:
    if saga is None or saga.status is not SagaStatus.RUNNING:
        return None
    halted: SagaRecord = saga.model_copy(deep=True)
    halted.stop_running()
    return halted
