from functools import partial

from redis_enterprise_services.creation.create_database_request import CreateDatabaseRequest
from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.operation_starter import OperationStarter
from redis_enterprise_services.operations.prepared_run import PreparedRun
from redis_enterprise_services.operations.start_once_result import StartOnceResult


class DatabaseCreation:
    def __init__(
        self,
        *,
        preparation: CreationPreparation,
        execution: CreationExecution,
        operation_starter: OperationStarter,
    ) -> None:
        self._preparation: CreationPreparation = preparation
        self._execution: CreationExecution = execution
        self._operation_starter: OperationStarter = operation_starter

    def start_once(self, *, trace_id: str, creation_request: CreateDatabaseRequest) -> StartOnceResult:
        return self._operation_starter.start_once(
            trace_id=trace_id,
            prepare_run=partial(self._prepare_run, trace_id=trace_id, creation_request=creation_request),
        )

    def _prepare_run(self, *, trace_id: str, creation_request: CreateDatabaseRequest) -> PreparedRun:
        prepared_creation: PreparedCreation = self._preparation.prepare(creation_request=creation_request)
        return PreparedRun(
            task_name=f"creating {prepared_creation.spec.database.name}",
            task=partial(
                self._execution.run_and_save, trace_id=trace_id, prepared_creation=prepared_creation
            ),
        )
