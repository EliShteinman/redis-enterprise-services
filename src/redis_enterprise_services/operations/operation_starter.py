import logging
from collections.abc import Callable

from redis_enterprise_services.background.background_task_runner import BackgroundTaskRunner
from redis_enterprise_services.liveness.in_process_operation_heartbeats import InProcessOperationHeartbeats
from redis_enterprise_services.operations.find_or_start_result import FindOrStartResult
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.prepared_run import PreparedRun
from redis_enterprise_services.operations.public_errors import PublicErrors

logger: logging.Logger = logging.getLogger(name=__name__)


class OperationStarter:
    def __init__(
        self,
        *,
        store: OperationStore,
        task_runner: BackgroundTaskRunner,
        operation_heartbeats: InProcessOperationHeartbeats,
        public_errors: PublicErrors,
    ) -> None:
        self._store: OperationStore = store
        self._task_runner: BackgroundTaskRunner = task_runner
        self._operation_heartbeats: InProcessOperationHeartbeats = operation_heartbeats
        self._public_errors: PublicErrors = public_errors

    def find_or_start(self, *, trace_id: str, prepare_run: Callable[[], PreparedRun]) -> FindOrStartResult:
        existing: Operation | None = self._store.find(trace_id=trace_id)
        if existing is not None:
            return existing_operation_result(operation=existing)
        return self._start_and_submit_if_absent(trace_id=trace_id, prepared_run=prepare_run())

    def _start_and_submit_if_absent(self, *, trace_id: str, prepared_run: PreparedRun) -> FindOrStartResult:
        running_operation: Operation = Operation(trace_id=trace_id)
        existing: Operation | None = self._store.start_if_absent(operation=running_operation)
        if existing is not None:
            return existing_operation_result(operation=existing)
        self._operation_heartbeats.track(trace_id=trace_id)
        try:
            self._task_runner.submit(
                task_name=prepared_run.task_name,
                task=self._operation_heartbeats.stopping_heartbeat_when_done(
                    trace_id=trace_id, task=prepared_run.task
                ),
            )
        except Exception:
            logger.critical(msg=f"{prepared_run.task_name} cannot run in the background", exc_info=True)
            self._operation_heartbeats.stop_heartbeat(trace_id=trace_id)
            self._store.save(
                operation=Operation(
                    trace_id=trace_id,
                    status=OperationStatus.REJECTED,
                    error=self._public_errors.internal_error(),
                )
            )
            raise
        logger.info(msg=f"{prepared_run.task_name} is started as {trace_id}")
        return FindOrStartResult(operation=running_operation, already_existed=False)


def existing_operation_result(*, operation: Operation) -> FindOrStartResult:
    logger.info(msg=f"operation {operation.trace_id} already exists, it is {operation.status.value}")
    return FindOrStartResult(operation=operation, already_existed=True)
