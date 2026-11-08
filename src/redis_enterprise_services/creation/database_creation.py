from functools import partial

from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.creation_request import CreationRequest
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.find_or_start_result import FindOrStartResult
from redis_enterprise_services.operations.operation_starter import OperationStarter
from redis_enterprise_services.operations.prepared_run import PreparedRun


class DatabaseCreation:
    def __init__(
        self,
        *,
        preparation: CreationPreparation,
        execution: CreationExecution,
        acceptance: OperationStarter,
    ) -> None:
        self._preparation: CreationPreparation = preparation
        self._execution: CreationExecution = execution
        self._acceptance: OperationStarter = acceptance

    def accept(self, *, trace_id: str, request: CreationRequest) -> FindOrStartResult:
        return self._acceptance.find_or_start(
            trace_id=trace_id, prepare_run=partial(self._prepared_run, trace_id=trace_id, request=request)
        )

    def _prepared_run(self, *, trace_id: str, request: CreationRequest) -> PreparedRun:
        creation: PreparedCreation = self._preparation.prepare(request=request)
        return PreparedRun(
            task_name=f"creating {creation.spec.database.name}",
            task=partial(self._execution.run, trace_id=trace_id, creation=creation),
        )
