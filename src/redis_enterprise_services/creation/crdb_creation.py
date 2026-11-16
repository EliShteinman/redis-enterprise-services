from functools import partial

from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.preparation.active_active_preparation import ActiveActivePreparation
from redis_enterprise_services.creation.preparation.prepared_active_active_creation import (
    PreparedActiveActiveCreation,
)
from redis_enterprise_services.creation.requests.create_crdb_request import CreateCrdbRequest
from redis_enterprise_services.operations.operation_starter import OperationStarter
from redis_enterprise_services.operations.prepared_run import PreparedRun


class CrdbCreation:
    def __init__(
        self,
        *,
        preparation: ActiveActivePreparation,
        execution: CreationExecution[PreparedActiveActiveCreation],
        operation_starter: OperationStarter,
    ) -> None:
        self._preparation: ActiveActivePreparation = preparation
        self._execution: CreationExecution[PreparedActiveActiveCreation] = execution
        self._operation_starter: OperationStarter = operation_starter

    def start_once(self, *, trace_id: str, creation_request: CreateCrdbRequest) -> None:
        self._operation_starter.start_once(
            trace_id=trace_id,
            prepare_run=partial(self._prepare_run, trace_id=trace_id, creation_request=creation_request),
        )

    def _prepare_run(self, *, trace_id: str, creation_request: CreateCrdbRequest) -> PreparedRun:
        prepared_creation: PreparedActiveActiveCreation = self._preparation.prepare(
            creation_request=creation_request
        )
        return PreparedRun(
            task_name=f"creating Active-Active {prepared_creation.spec.database.name}",
            task=partial(
                self._execution.run_and_save, trace_id=trace_id, prepared_creation=prepared_creation
            ),
        )
