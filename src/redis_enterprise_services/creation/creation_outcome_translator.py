import logging

from pydantic import ValidationError

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.creation.created_database_result import created_database_result
from redis_enterprise_services.creation.created_resources import created_uid_or_none
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.operations.remaining_resource import RemainingResource
from redis_enterprise_services.planning.active_active_planned_resources import (
    SitePlannedResource,
    active_active_planned_resources,
)
from redis_enterprise_services.planning.creation_step_keys import on_site
from redis_enterprise_services.planning.planned_resources import (
    CRDB_RESOURCE_TYPE,
    PlannedResource,
    planned_resources_by_step_key,
)
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepError, StepRecord
from redis_enterprise_services.steps.create_crdb import CreatedCrdb

logger: logging.Logger = logging.getLogger(name=__name__)

OPERATION_STATUS_BY_FAILED_SAGA_STATUS: dict[SagaStatus, OperationStatus] = {
    SagaStatus.ROLLED_BACK: OperationStatus.ROLLED_BACK,
    SagaStatus.REQUIRES_MANUAL_INTERVENTION: OperationStatus.REQUIRES_MANUAL_INTERVENTION,
}


class CreationOutcomeTranslator:
    def __init__(
        self,
        *,
        resource_naming: UserResourceNaming,
        public_errors: PublicErrors,
        database_settings: DatabaseSettings,
    ) -> None:
        self._resource_naming: UserResourceNaming = resource_naming
        self._public_errors: PublicErrors = public_errors
        self._database_settings: DatabaseSettings = database_settings

    def operation_from_ended_record(
        self,
        *,
        trace_id: str,
        prepared_creation: PreparedCreation,
        record: SagaRecord,
        interruption_error: PublicError,
    ) -> Operation:
        if record.status is SagaStatus.SUCCEEDED:
            return succeeded_operation(
                trace_id=trace_id,
                database=created_database_result(
                    prepared_creation=prepared_creation,
                    record=record,
                    database_settings=self._database_settings,
                    resource_naming=self._resource_naming,
                ),
            )
        return self._failed_operation(
            trace_id=trace_id,
            prepared_creation=prepared_creation,
            record=record,
            interruption_error=interruption_error,
        )

    def _failed_operation(
        self,
        *,
        trace_id: str,
        prepared_creation: PreparedCreation,
        record: SagaRecord,
        interruption_error: PublicError,
    ) -> Operation:
        return Operation.failed(
            trace_id=trace_id,
            status=OPERATION_STATUS_BY_FAILED_SAGA_STATUS[record.status],
            error=self._stopped_step_error(
                prepared_creation=prepared_creation, record=record, interruption_error=interruption_error
            ),
            not_rolled_back=self.remaining_resources(prepared_creation=prepared_creation, record=record),
        )

    def _stopped_step_error(
        self, *, prepared_creation: PreparedCreation, record: SagaRecord, interruption_error: PublicError
    ) -> PublicError:
        stopped_step: StepRecord | None = record.stopped_step()
        if stopped_step is None or stopped_step.error is None:
            logger.warning(
                msg=f"saga {record.saga_id} ended {record.status.value} and its stopped step has no error "
                f"(it was interrupted), reported as {interruption_error.code}"
            )
            return interruption_error
        return self._public_errors.from_code(
            internal_code=stopped_step.error.code,
            message=stopped_step.error.message,
            cluster_url=self._site_of_step(
                prepared_creation=prepared_creation, step_key=stopped_step.key
            ).api_url,
            cluster_error_code=stopped_step.error.remote_code,
        )

    def remaining_resources(
        self, *, prepared_creation: PreparedCreation, record: SagaRecord
    ) -> list[RemainingResource]:
        planned_by_step_key: dict[str, SitePlannedResource] = self._planned_by_step_key(
            prepared_creation=prepared_creation
        )
        return [
            self._remaining_resource(planned=planned_by_step_key[step.key], record=record, step=step)
            for step in record.not_rolled_back_steps()
            if step.key in planned_by_step_key
        ]

    def _planned_by_step_key(self, *, prepared_creation: PreparedCreation) -> dict[str, SitePlannedResource]:
        if prepared_creation.active_active:
            return active_active_planned_resources(
                spec=prepared_creation.spec,
                resource_naming=self._resource_naming,
                clusters=prepared_creation.clusters,
            )
        return {
            step_key: SitePlannedResource(cluster=prepared_creation.cluster, resource=planned)
            for step_key, planned in planned_resources_by_step_key(
                spec=prepared_creation.spec, resource_naming=self._resource_naming
            ).items()
        }

    def _site_of_step(self, *, prepared_creation: PreparedCreation, step_key: str) -> ConfiguredCluster:
        planned: SitePlannedResource | None = self._planned_by_step_key(
            prepared_creation=prepared_creation
        ).get(step_key)
        if planned is not None:
            return planned.cluster
        return next(
            (
                cluster
                for cluster in prepared_creation.clusters
                if step_key.startswith(on_site(cluster_name=cluster.name, step_key=""))
            ),
            prepared_creation.cluster,
        )

    def _remaining_resource(
        self, *, planned: SitePlannedResource, record: SagaRecord, step: StepRecord
    ) -> RemainingResource:
        return RemainingResource(
            cluster_url=planned.cluster.api_url,
            resource_type=planned.resource.resource_type,
            name=planned.resource.name,
            uid=created_uid_or_none(record=record, step_key=planned.resource.uid_step_key),
            crdb_guid=created_crdb_guid_or_none(record=record, planned=planned.resource),
            last_error=self._public_code_and_message(error=step.last_error()),
        )

    def _public_code_and_message(self, *, error: StepError | None) -> str | None:
        if error is None:
            return None
        return f"{self._public_errors.public_code(internal_code=error.code)}: {error.message}"


def succeeded_operation(*, trace_id: str, database: DatabaseResult) -> Operation:
    return Operation(trace_id=trace_id, status=OperationStatus.SUCCEEDED, database=database)


def created_crdb_guid_or_none(*, record: SagaRecord, planned: PlannedResource) -> str | None:
    if planned.resource_type != CRDB_RESOURCE_TYPE:
        return None
    try:
        return CreatedCrdb.model_validate(obj=record.step(key=planned.uid_step_key).result).guid
    except ValidationError:
        return None
