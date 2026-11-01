import logging
from collections.abc import Callable

from redis_enterprise_services.background.task_runner import TaskRunner
from redis_enterprise_services.operations.admission import Admission
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_errors import PublicErrors

logger: logging.Logger = logging.getLogger(name=__name__)


class OperationAcceptance:
    def __init__(self, *, store: OperationStore, runner: TaskRunner, errors: PublicErrors) -> None:
        self._store: OperationStore = store
        self._runner: TaskRunner = runner
        self._errors: PublicErrors = errors

    def repeated(self, *, trace_id: str) -> Admission | None:
        existing: Operation | None = self._store.find(trace_id=trace_id)
        return None if existing is None else self._repeat(operation=existing)

    def accept(self, *, trace_id: str, name: str, task: Callable[[], object]) -> Admission:
        accepted: Operation = Operation(trace_id=trace_id)
        existing: Operation | None = self._store.start(operation=accepted)
        if existing is not None:
            return self._repeat(operation=existing)
        try:
            self._runner.submit(name=name, task=task)
        except RuntimeError:
            logger.critical(msg=f"{name} cannot run in the background", exc_info=True)
            self._store.save(
                operation=Operation(
                    trace_id=trace_id, status=OperationStatus.REJECTED, error=self._errors.internal()
                )
            )
            raise
        logger.info(msg=f"{name} is accepted as {trace_id}")
        return Admission(operation=accepted, repeated=False)

    def _repeat(self, *, operation: Operation) -> Admission:
        logger.info(
            msg=f"operation {operation.trace_id} was already accepted, it is {operation.status.value}"
        )
        return Admission(operation=operation, repeated=True)
