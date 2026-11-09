import logging

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.creation.created_database_result import created_database_result
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.operations.remaining_resource import RemainingResource
from redis_enterprise_services.planning.planned_resources import (
    PlannedResource,
    planned_resources_by_step_key,
)
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.resources.created_uid import created_uid_or_none
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepError, StepRecord

logger: logging.Logger = logging.getLogger(name=__name__)


class CreationOutcomeTranslator:
    def __init__(self, *, resource_naming: UserResourceNaming, public_errors: PublicErrors) -> None:
        self._resource_naming: UserResourceNaming = resource_naming
        self._public_errors: PublicErrors = public_errors

    def operation_from_ended_record(
        self, *, trace_id: str, prepared_creation: PreparedCreation, record: SagaRecord
    ) -> Operation:
        if record.status is SagaStatus.SUCCEEDED:
            return succeeded_operation(trace_id=trace_id, prepared_creation=prepared_creation, record=record)
        return self._failed_operation(trace_id=trace_id, prepared_creation=prepared_creation, record=record)

    def _failed_operation(
        self, *, trace_id: str, prepared_creation: PreparedCreation, record: SagaRecord
    ) -> Operation:
        return Operation(
            trace_id=trace_id,
            status=OperationStatus(record.status.value),
            error=self._stopped_step_error(cluster=prepared_creation.cluster, record=record),
            not_rolled_back=self._not_rolled_back_resources(
                prepared_creation=prepared_creation, record=record
            ),
        )

    def _stopped_step_error(self, *, cluster: ConfiguredCluster, record: SagaRecord) -> PublicError:
        stopped_step: StepRecord | None = record.stopped_step()
        if stopped_step is None or stopped_step.error is None:
            logger.error(msg=f"saga {record.saga_id} ended {record.status.value} with no failed step")
            return self._public_errors.internal_error()
        return self._public_errors.from_code(
            internal_code=stopped_step.error.code,
            message=stopped_step.error.message,
            cluster_url=cluster.api_url,
            cluster_error_code=stopped_step.error.remote_code,
        )

    def _not_rolled_back_resources(
        self, *, prepared_creation: PreparedCreation, record: SagaRecord
    ) -> list[RemainingResource]:
        planned_by_step_key: dict[str, PlannedResource] = planned_resources_by_step_key(
            spec=prepared_creation.spec, resource_naming=self._resource_naming
        )
        return [
            self._remaining_resource(
                cluster=prepared_creation.cluster,
                planned=planned_by_step_key[step.key],
                record=record,
                step=step,
            )
            for step in record.not_rolled_back_steps()
        ]

    def _remaining_resource(
        self, *, cluster: ConfiguredCluster, planned: PlannedResource, record: SagaRecord, step: StepRecord
    ) -> RemainingResource:
        return RemainingResource(
            cluster_url=cluster.api_url,
            resource_type=planned.resource_type,
            name=planned.name,
            uid=created_uid_or_none(step_result=record.step(key=planned.uid_step_key).result),
            last_error=self._public_code_and_message(error=step.last_error()),
        )

    def _public_code_and_message(self, *, error: StepError | None) -> str | None:
        if error is None:
            return None
        return f"{self._public_errors.public_code(internal_code=error.code)}: {error.message}"


def succeeded_operation(
    *, trace_id: str, prepared_creation: PreparedCreation, record: SagaRecord
) -> Operation:
    return Operation(
        trace_id=trace_id,
        status=OperationStatus.SUCCEEDED,
        database=created_database_result(prepared_creation=prepared_creation, record=record),
    )


def record_interrupted_if_running(*, record: SagaRecord) -> SagaRecord:
    if record.status is not SagaStatus.RUNNING:
        return record
    logger.critical(msg=f"saga {record.saga_id} is stored as running, reported as manual intervention")
    return record.interrupted_copy()
