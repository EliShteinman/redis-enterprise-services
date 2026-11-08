import logging

from pydantic import ValidationError

from redis_enterprise_services.creation.creation_result import created_database
from redis_enterprise_services.creation.planned_resource import PlannedResource, planned_resources
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.operations.remaining_resource import RemainingResource
from redis_enterprise_services.planning.single_site_creation_planner import (
    DATABASE_STEP_KEY,
    PERMISSIONS_STEP_KEY,
)
from redis_enterprise_services.planning.user_resource_names import UserResourceNames
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.saga.contract.saga_record import (
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
    def __init__(self, *, names: UserResourceNames, public_errors: PublicErrors) -> None:
        self._names: UserResourceNames = names
        self._public_errors: PublicErrors = public_errors

    def of(self, *, trace_id: str, creation: PreparedCreation, record: SagaRecord) -> Operation:
        settled: SagaRecord = ended(record=record)
        status: OperationStatus = OperationStatus(settled.status.value)
        if settled.status is SagaStatus.SUCCEEDED:
            return Operation(
                trace_id=trace_id, status=status, database=created_database(creation=creation, record=settled)
            )
        return Operation(
            trace_id=trace_id,
            status=status,
            error=self._error(creation=creation, record=settled),
            not_rolled_back=self._not_rolled_back(creation=creation, record=settled),
        )

    def _error(self, *, creation: PreparedCreation, record: SagaRecord) -> PublicError:
        stopped: StepRecord | None = next(
            (step for step in record.steps if step.key == record.stopped_at), None
        )
        if stopped is None or stopped.error is None:
            logger.error(msg=f"saga {record.saga_id} ended {record.status.value} with no failed step")
            return self._public_errors.internal_error()
        return self._public_errors.from_code(
            error_code=stopped.error.code,
            message=stopped.error.message,
            cluster_url=creation.cluster.api_url,
            cluster_error_code=stopped.error.remote_code,
        )

    def _not_rolled_back(self, *, creation: PreparedCreation, record: SagaRecord) -> list[RemainingResource]:
        resources: dict[str, PlannedResource] = planned_resources(request=creation.request, names=self._names)
        return [
            RemainingResource(
                cluster_url=creation.cluster.api_url,
                resource_type=resources[step.key].type,
                name=resources[step.key].name,
                uid=resource_uid(record=record, step=step),
                last_error=self._described(error=step.compensation_error or step.error),
            )
            for step in record.steps
            if step.status in LEFT_BEHIND
        ]

    def _described(self, *, error: StepError | None) -> str | None:
        return (
            None
            if error is None
            else f"{self._public_errors.public_code(error_code=error.code)}: {error.message}"
        )


def resource_uid(*, record: SagaRecord, step: StepRecord) -> int | None:
    owner: StepRecord = (
        next(found for found in record.steps if found.key == DATABASE_STEP_KEY)
        if step.key == PERMISSIONS_STEP_KEY
        else step
    )
    try:
        return CreatedResource.model_validate(obj=owner.result).uid
    except ValidationError:
        return None


def ended(*, record: SagaRecord) -> SagaRecord:
    if record.status is not SagaStatus.RUNNING:
        return record
    logger.critical(msg=f"saga {record.saga_id} is stored as running, reported as manual intervention")
    stopped: SagaRecord = record.model_copy(deep=True)
    stopped.mark_interrupted()
    return stopped
