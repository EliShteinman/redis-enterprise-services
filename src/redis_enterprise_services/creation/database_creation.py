import logging
from functools import partial

from redis_enterprise_services.background.task_runner import TaskRunner
from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.creation_request import CreationRequest
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_store import OperationStore

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseCreation:
    def __init__(
        self,
        *,
        preparation: CreationPreparation,
        execution: CreationExecution,
        store: OperationStore,
        runner: TaskRunner,
    ) -> None:
        self._preparation: CreationPreparation = preparation
        self._execution: CreationExecution = execution
        self._store: OperationStore = store
        self._runner: TaskRunner = runner

    def accept(self, *, trace_id: str, request: CreationRequest) -> Operation:
        creation: PreparedCreation = self._preparation.prepare(request=request)
        accepted: Operation = Operation(trace_id=trace_id)
        self._store.save(operation=accepted)
        self._runner.submit(
            name=f"creating {creation.request.database.name}",
            task=partial(self._execution.run, trace_id=trace_id, creation=creation),
        )
        logger.info(msg=f"creating {creation.request.database.name} is accepted as {trace_id}")
        return accepted
