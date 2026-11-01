import logging

from pydantic import ValidationError

from redis_enterprise_services.creation.creation_result import created_database
from redis_enterprise_services.creation.planned_resource import PlannedResource, planned_resources
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.error_info import ErrorInfo
from redis_enterprise_services.operations.not_rolled_back import NotRolledBack
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.planning.resource_names import ResourceNames
from redis_enterprise_services.planning.single_site_creation import DATABASE_KEY, PERMISSIONS_KEY
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.saga.contract.models import (
    SagaRecord,
    SagaStatus,
    StepError,
    StepRecord,
    StepStatus,
)

logger: logging.Logger = logging.getLogger(name=__name__)

LEFT_BEHIND: frozenset[StepStatus] = frozenset(
    {StepStatus.DONE, StepStatus.UNRESOLVED, StepStatus.COMPENSATING, StepStatus.COMPENSATION_FAILED}
)


class CreationOutcome:
    def __init__(self, *, names: ResourceNames, errors: PublicErrors) -> None:
        self._names: ResourceNames = names
        self._errors: PublicErrors = errors

    def of(self, *, trace_id: str, creation: PreparedCreation, record: SagaRecord) -> Operation:
        status: OperationStatus = OperationStatus(record.status.value)
        if record.status is SagaStatus.SUCCEEDED:
            return Operation(
                trace_id=trace_id, status=status, database=created_database(creation=creation, record=record)
            )
        return Operation(
            trace_id=trace_id,
            status=status,
            error=self._error(creation=creation, record=record),
            not_rolled_back=self._not_rolled_back(creation=creation, record=record),
        )

    def _error(self, *, creation: PreparedCreation, record: SagaRecord) -> ErrorInfo:
        stopped: StepRecord | None = next(
            (step for step in record.steps if step.key == record.stopped_at), None
        )
        if stopped is None or stopped.error is None:
            logger.error(msg=f"saga {record.saga_id} ended {record.status.value} with no failed step")
            return self._errors.internal()
        return self._errors.info(
            code=stopped.error.code,
            message=stopped.error.message,
            cluster=creation.cluster.api_url,
            remote_code=stopped.error.remote_code,
        )

    def _not_rolled_back(self, *, creation: PreparedCreation, record: SagaRecord) -> list[NotRolledBack]:
        resources: dict[str, PlannedResource] = planned_resources(request=creation.request, names=self._names)
        return [
            NotRolledBack(
                cluster=creation.cluster.api_url,
                type=resources[step.key].type,
                name=resources[step.key].name,
                uid=resource_uid(record=record, step=step),
                error=self._described(error=step.compensation_error or step.error),
            )
            for step in record.steps
            if step.status in LEFT_BEHIND
        ]

    def _described(self, *, error: StepError | None) -> str | None:
        return None if error is None else f"{self._errors.public_code(code=error.code)}: {error.message}"


def resource_uid(*, record: SagaRecord, step: StepRecord) -> int | None:
    owner: StepRecord = (
        next(found for found in record.steps if found.key == DATABASE_KEY)
        if step.key == PERMISSIONS_KEY
        else step
    )
    try:
        return CreatedResource.model_validate(obj=owner.result).uid
    except ValidationError:
        return None
