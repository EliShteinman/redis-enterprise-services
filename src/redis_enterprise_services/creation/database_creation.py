from functools import partial

from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.creation_request import CreationRequest
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_acceptance import OperationAcceptance


class DatabaseCreation:
    def __init__(
        self,
        *,
        preparation: CreationPreparation,
        execution: CreationExecution,
        acceptance: OperationAcceptance,
    ) -> None:
        self._preparation: CreationPreparation = preparation
        self._execution: CreationExecution = execution
        self._acceptance: OperationAcceptance = acceptance

    def accept(self, *, trace_id: str, request: CreationRequest) -> Operation:
        creation: PreparedCreation = self._preparation.prepare(request=request)
        return self._acceptance.accept(
            trace_id=trace_id,
            name=f"creating {creation.request.database.name}",
            task=partial(self._execution.run, trace_id=trace_id, creation=creation),
        )
