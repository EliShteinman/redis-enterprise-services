import logging
from collections.abc import Callable

from redis_enterprise_services.background.background_task_runner import BackgroundTaskRunner
from redis_enterprise_services.liveness.live_operations import LiveOperations
from redis_enterprise_services.operations.acceptance_result import AcceptanceResult
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.prepared_run import PreparedRun
from redis_enterprise_services.operations.public_errors import PublicErrors

logger: logging.Logger = logging.getLogger(name=__name__)


class OperationAcceptance:
    def __init__(
        self,
        *,
        store: OperationStore,
        runner: BackgroundTaskRunner,
        live_operations: LiveOperations,
        public_errors: PublicErrors,
    ) -> None:
        self._store: OperationStore = store
        self._runner: BackgroundTaskRunner = runner
        self._live_operations: LiveOperations = live_operations
        self._public_errors: PublicErrors = public_errors

    def accept(self, *, trace_id: str, prepare: Callable[[], PreparedRun]) -> AcceptanceResult:
        existing: Operation | None = self._store.find(trace_id=trace_id)
        if existing is not None:
            return acceptance_of_existing(operation=existing)
        return self._store_and_submit(trace_id=trace_id, run=prepare())

    def _store_and_submit(self, *, trace_id: str, run: PreparedRun) -> AcceptanceResult:
        running: Operation = Operation(trace_id=trace_id)
        existing: Operation | None = self._store.save_if_absent(operation=running)
        if existing is not None:
            return acceptance_of_existing(operation=existing)
        self._live_operations.track(trace_id=trace_id)
        try:
            self._runner.submit(
                name=run.task_name,
                task=self._live_operations.untracking_when_done(trace_id=trace_id, task=run.task),
            )
        except Exception:
            logger.critical(msg=f"{run.task_name} cannot run in the background", exc_info=True)
            self._live_operations.untrack_and_delete_heartbeat(trace_id=trace_id)
            self._store.save(
                operation=Operation(
                    trace_id=trace_id,
                    status=OperationStatus.REJECTED,
                    error=self._public_errors.internal_error(),
                )
            )
            raise
        logger.info(msg=f"{run.task_name} is accepted as {trace_id}")
        return AcceptanceResult(operation=running, already_accepted=False)


def acceptance_of_existing(*, operation: Operation) -> AcceptanceResult:
    logger.info(msg=f"operation {operation.trace_id} was already accepted, it is {operation.status.value}")
    return AcceptanceResult(operation=operation, already_accepted=True)
