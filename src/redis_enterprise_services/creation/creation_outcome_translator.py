import logging

from redis_enterprise_services.creation.created_crdb_guid import created_crdb_guid_or_none
from redis_enterprise_services.creation.created_resources import created_uid_or_none
from redis_enterprise_services.creation.creation_record_reader import CreationRecordReader
from redis_enterprise_services.operations.active_active_database_result import ActiveActiveDatabaseResult
from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.operations.remaining_resource import RemainingResource
from redis_enterprise_services.planning.site_planned_resource import SitePlannedResource
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepError, StepRecord

logger: logging.Logger = logging.getLogger(name=__name__)

OPERATION_STATUS_BY_FAILED_SAGA_STATUS: dict[SagaStatus, OperationStatus] = {
    SagaStatus.ROLLED_BACK: OperationStatus.ROLLED_BACK,
    SagaStatus.REQUIRES_MANUAL_INTERVENTION: OperationStatus.REQUIRES_MANUAL_INTERVENTION,
}


class CreationOutcomeTranslator[TPrepared]:
    def __init__(
        self, *, record_reader: CreationRecordReader[TPrepared], public_errors: PublicErrors
    ) -> None:
        self._record_reader: CreationRecordReader[TPrepared] = record_reader
        self._public_errors: PublicErrors = public_errors

    def operation_from_ended_record(
        self,
        *,
        trace_id: str,
        prepared_creation: TPrepared,
        record: SagaRecord,
        interruption_error: PublicError,
    ) -> Operation:
        if record.status is SagaStatus.SUCCEEDED:
            return succeeded_operation(
                trace_id=trace_id,
                database=self._record_reader.database_result(
                    prepared_creation=prepared_creation, record=record
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
        prepared_creation: TPrepared,
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
        self, *, prepared_creation: TPrepared, record: SagaRecord, interruption_error: PublicError
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
            cluster_url=self._record_reader.cluster_of_step(
                prepared_creation=prepared_creation, step_key=stopped_step.key
            ).api_url,
            cluster_error_code=stopped_step.error.remote_code,
        )

    def remaining_resources(
        self, *, prepared_creation: TPrepared, record: SagaRecord
    ) -> list[RemainingResource]:
        planned_by_step_key: dict[str, SitePlannedResource] = self._record_reader.planned_resources(
            prepared_creation=prepared_creation
        )
        return [
            self._remaining_resource(planned=planned_by_step_key[step.key], record=record, step=step)
            for step in record.not_rolled_back_steps()
            if step.key in planned_by_step_key
        ]

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


def succeeded_operation(*, trace_id: str, database: DatabaseResult | ActiveActiveDatabaseResult) -> Operation:
    return Operation(trace_id=trace_id, status=OperationStatus.SUCCEEDED, database=database)
