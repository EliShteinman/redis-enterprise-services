import logging
from collections.abc import Callable

from redis_enterprise_services.background.background_task_runner import BackgroundTaskRunner
from redis_enterprise_services.liveness.operation_heartbeats import OperationHeartbeats
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.prepared_run import PreparedRun
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.operations.start_once_result import StartOnceResult

logger: logging.Logger = logging.getLogger(name=__name__)


class OperationStarter:
    def __init__(
        self,
        *,
        store: OperationStore,
        task_runner: BackgroundTaskRunner,
        operation_heartbeats: OperationHeartbeats,
        public_errors: PublicErrors,
    ) -> None:
        self._store: OperationStore = store
        self._task_runner: BackgroundTaskRunner = task_runner
        self._operation_heartbeats: OperationHeartbeats = operation_heartbeats
        self._public_errors: PublicErrors = public_errors

    def start_once(self, *, trace_id: str, prepare_run: Callable[[], PreparedRun]) -> StartOnceResult:
        existing: Operation | None = self._store.find(trace_id=trace_id)
        if existing is not None:
            return existing_operation_result(operation=existing)
        return self._start_if_absent(trace_id=trace_id, prepared_run=prepare_run())

    def _start_if_absent(self, *, trace_id: str, prepared_run: PreparedRun) -> StartOnceResult:
        running_operation: Operation = Operation(trace_id=trace_id)
        existing: Operation | None = self._store.create_if_absent(operation=running_operation)
        if existing is not None:
            return existing_operation_result(operation=existing)
        self._run_in_background(trace_id=trace_id, prepared_run=prepared_run)
        logger.info(msg=f"{prepared_run.task_name} is started as {trace_id}")
        return StartOnceResult(operation=running_operation, already_existed=False)

    def _run_in_background(self, *, trace_id: str, prepared_run: PreparedRun) -> None:
        self._operation_heartbeats.track(trace_id=trace_id)
        try:
            self._task_runner.submit(
                task_name=prepared_run.task_name,
                task=self._operation_heartbeats.stopping_heartbeat_when_done(
                    trace_id=trace_id, task=prepared_run.task
                ),
            )
        except Exception as submit_error:
            self._reject_unsubmitted(
                trace_id=trace_id, task_name=prepared_run.task_name, submit_error=submit_error
            )
            raise

    def _reject_unsubmitted(self, *, trace_id: str, task_name: str, submit_error: Exception) -> None:
        logger.critical(msg=f"{task_name} cannot run in the background", exc_info=submit_error)
        self._store.save(
            operation=Operation.rejected(trace_id=trace_id, error=self._public_errors.internal_error())
        )
        self._operation_heartbeats.stop_heartbeat(trace_id=trace_id)


def existing_operation_result(*, operation: Operation) -> StartOnceResult:
    logger.info(msg=f"operation {operation.trace_id} already exists, it is {operation.status.value}")
    return StartOnceResult(operation=operation, already_existed=True)
