import logging
from functools import partial

from redis_enterprise_services.creation.creation_outcome_translator import (
    CreationOutcomeTranslator,
    record_interrupted_if_running,
)
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.planning.availability.creation_naming import CreationNaming
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.name_check_scope import NameCheckScope
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.saga.contract.saga_record import SagaRecord
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordReader
from redis_enterprise_services.saga.engine.saga_executor import SagaExecutor

logger: logging.Logger = logging.getLogger(name=__name__)


class CreationExecution:
    def __init__(
        self,
        *,
        name_check_scope: NameCheckScope,
        name_availability: NameAvailability,
        creation_naming: CreationNaming,
        planner: SingleSiteCreationPlanner,
        saga_executor: SagaExecutor,
        outcome_translator: CreationOutcomeTranslator,
        public_errors: PublicErrors,
        saga_record_reader: SagaRecordReader,
        operation_store: OperationStore,
    ) -> None:
        self._name_check_scope: NameCheckScope = name_check_scope
        self._name_availability: NameAvailability = name_availability
        self._creation_naming: CreationNaming = creation_naming
        self._planner: SingleSiteCreationPlanner = planner
        self._saga_executor: SagaExecutor = saga_executor
        self._outcome_translator: CreationOutcomeTranslator = outcome_translator
        self._public_errors: PublicErrors = public_errors
        self._saga_record_reader: SagaRecordReader = saga_record_reader
        self._operation_store: OperationStore = operation_store

    def run_and_save(self, *, trace_id: str, prepared_creation: PreparedCreation) -> Operation:
        operation: Operation = self._final_operation(trace_id=trace_id, prepared_creation=prepared_creation)
        self._operation_store.save(operation=operation)
        return operation

    def _final_operation(self, *, trace_id: str, prepared_creation: PreparedCreation) -> Operation:
        try:
            record: SagaRecord = self._run_saga(trace_id=trace_id, prepared_creation=prepared_creation)
        except RedisEnterpriseServicesError as error:
            return self._operation_after_saga_error(
                trace_id=trace_id, prepared_creation=prepared_creation, saga_error=error
            )
        except Exception as error:
            logger.critical(msg=f"creation {trace_id} failed on an unexpected error", exc_info=True)
            return self._operation_after_saga_error(
                trace_id=trace_id, prepared_creation=prepared_creation, saga_error=error
            )
        return self._translated_or_manual_intervention_operation(
            trace_id=trace_id, prepared_creation=prepared_creation, record=record
        )

    def _run_saga(self, *, trace_id: str, prepared_creation: PreparedCreation) -> SagaRecord:
        return self._saga_executor.run(
            saga_id=trace_id,
            plan=self._planner.plan(
                cluster=prepared_creation.cluster,
                database=prepared_creation.spec.database,
                users=prepared_creation.spec.users,
            ),
            check_before_start=partial(self._ensure_names_free, prepared_creation=prepared_creation),
        )

    def _ensure_names_free(self, *, prepared_creation: PreparedCreation) -> None:
        self._name_availability.ensure_free(
            clusters=self._name_check_scope.clusters_to_check(chosen=prepared_creation.cluster),
            requested_names=self._creation_naming.requested_names(spec=prepared_creation.spec),
        )

    def _operation_after_saga_error(
        self, *, trace_id: str, prepared_creation: PreparedCreation, saga_error: Exception
    ) -> Operation:
        error_if_not_started: PublicError = self._public_errors.from_exception(
            error=saga_error, cluster_url=prepared_creation.cluster.api_url
        )
        stored_record: SagaRecord | None = self._saga_record_reader.find(saga_id=trace_id)
        if stored_record is None:
            return rejected_operation(trace_id=trace_id, error=error_if_not_started)
        logger.critical(
            msg=f"saga {trace_id} stopped after it started, its outcome comes from its record",
            exc_info=saga_error,
        )
        return self._translated_or_manual_intervention_operation(
            trace_id=trace_id,
            prepared_creation=prepared_creation,
            record=record_interrupted_if_running(record=stored_record),
        )

    def _translated_or_manual_intervention_operation(
        self, *, trace_id: str, prepared_creation: PreparedCreation, record: SagaRecord
    ) -> Operation:
        try:
            return self._outcome_translator.operation_from_ended_record(
                trace_id=trace_id, prepared_creation=prepared_creation, record=record
            )
        except Exception:
            logger.critical(
                msg=f"saga {trace_id} ended {record.status.value}, but its result cannot be read",
                exc_info=True,
            )
            return Operation.requires_manual_intervention(
                trace_id=trace_id, error=self._public_errors.internal_error()
            )


def rejected_operation(*, trace_id: str, error: PublicError) -> Operation:
    logger.warning(msg=f"operation {trace_id} is rejected: {error.code}: {error.message}")
    return Operation.rejected(trace_id=trace_id, error=error)
