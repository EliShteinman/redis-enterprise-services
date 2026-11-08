import logging

from pydantic import ValidationError

from redis_enterprise_services.creation.created_database_result import created_database_result
from redis_enterprise_services.creation.planned_resource import PlannedResource, planned_resources_by_step_key
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
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.saga.contract.saga_record import (
    SagaRecord,
    SagaStatus,
    StepError,
    StepRecord,
    StepStatus,
)

logger: logging.Logger = logging.getLogger(name=__name__)

NOT_ROLLED_BACK_STEP_STATUSES: frozenset[StepStatus] = frozenset(
    {StepStatus.DONE, StepStatus.UNRESOLVED, StepStatus.COMPENSATING, StepStatus.COMPENSATION_FAILED}
)


class CreationOutcomeTranslator:
    def __init__(self, *, resource_naming: UserResourceNaming, public_errors: PublicErrors) -> None:
        self._resource_naming: UserResourceNaming = resource_naming
        self._public_errors: PublicErrors = public_errors

    def operation_for(self, *, trace_id: str, creation: PreparedCreation, record: SagaRecord) -> Operation:
        settled: SagaRecord = settled_record(record=record)
        status: OperationStatus = OperationStatus(settled.status.value)
        if settled.status is SagaStatus.SUCCEEDED:
            return Operation(
                trace_id=trace_id,
                status=status,
                database=created_database_result(creation=creation, record=settled),
            )
        return Operation(
            trace_id=trace_id,
            status=status,
            error=self._stopped_step_error(creation=creation, record=settled),
            not_rolled_back=self._not_rolled_back_resources(creation=creation, record=settled),
        )

    def _stopped_step_error(self, *, creation: PreparedCreation, record: SagaRecord) -> PublicError:
        stopped_step: StepRecord | None = next(
            (step for step in record.steps if step.key == record.stopped_at), None
        )
        if stopped_step is None or stopped_step.error is None:
            logger.error(msg=f"saga {record.saga_id} ended {record.status.value} with no failed step")
            return self._public_errors.internal_error()
        return self._public_errors.from_code(
            internal_code=stopped_step.error.code,
            message=stopped_step.error.message,
            cluster_url=creation.cluster.api_url,
            cluster_error_code=stopped_step.error.remote_code,
        )

    def _not_rolled_back_resources(
        self, *, creation: PreparedCreation, record: SagaRecord
    ) -> list[RemainingResource]:
        planned_by_step_key: dict[str, PlannedResource] = planned_resources_by_step_key(
            spec=creation.spec, resource_naming=self._resource_naming
        )
        return [
            RemainingResource(
                cluster_url=creation.cluster.api_url,
                resource_type=planned_by_step_key[step.key].resource_type,
                name=planned_by_step_key[step.key].name,
                uid=resource_uid(record=record, step=step),
                last_error=self._last_error_text(error=step.compensation_error or step.error),
            )
            for step in record.steps
            if step.status in NOT_ROLLED_BACK_STEP_STATUSES
        ]

    def _last_error_text(self, *, error: StepError | None) -> str | None:
        return (
            None
            if error is None
            else f"{self._public_errors.public_code(internal_code=error.code)}: {error.message}"
        )


def resource_uid(*, record: SagaRecord, step: StepRecord) -> int | None:
    uid_step: StepRecord = (
        next(found for found in record.steps if found.key == DATABASE_STEP_KEY)
        if step.key == PERMISSIONS_STEP_KEY
        else step
    )
    try:
        return CreatedResource.model_validate(obj=uid_step.result).uid
    except ValidationError:
        return None


def settled_record(*, record: SagaRecord) -> SagaRecord:
    if record.status is not SagaStatus.RUNNING:
        return record
    logger.critical(msg=f"saga {record.saga_id} is stored as running, reported as manual intervention")
    interrupted: SagaRecord = record.model_copy(deep=True)
    interrupted.mark_interrupted()
    return interrupted
