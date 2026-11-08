import logging
from functools import partial

from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
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
        executor: SagaExecutor,
        outcome_translator: CreationOutcomeTranslator,
        public_errors: PublicErrors,
        record_reader: SagaRecordReader,
        store: OperationStore,
    ) -> None:
        self._name_check_scope: NameCheckScope = name_check_scope
        self._name_availability: NameAvailability = name_availability
        self._creation_naming: CreationNaming = creation_naming
        self._planner: SingleSiteCreationPlanner = planner
        self._executor: SagaExecutor = executor
        self._outcome_translator: CreationOutcomeTranslator = outcome_translator
        self._public_errors: PublicErrors = public_errors
        self._record_reader: SagaRecordReader = record_reader
        self._store: OperationStore = store

    def run(self, *, trace_id: str, creation: PreparedCreation) -> Operation:
        operation: Operation = self._final_operation(trace_id=trace_id, creation=creation)
        self._store.save(operation=operation)
        return operation

    def _final_operation(self, *, trace_id: str, creation: PreparedCreation) -> Operation:
        try:
            record: SagaRecord = self._executor.run(
                saga_id=trace_id,
                plan=self._planner.plan(
                    cluster=creation.cluster, database=creation.spec.database, users=creation.spec.users
                ),
                check_before_start=partial(self._ensure_names_free, creation=creation),
            )
        except RedisEnterpriseServicesError as error:
            public_error: PublicError = self._public_errors.from_error(
                error=error, cluster_url=creation.cluster.api_url
            )
            return self._operation_from_stored_record(
                trace_id=trace_id, creation=creation, error_if_not_started=public_error
            )
        except Exception:
            logger.critical(msg=f"creation {trace_id} failed on an unexpected error", exc_info=True)
            return self._operation_from_stored_record(
                trace_id=trace_id,
                creation=creation,
                error_if_not_started=self._public_errors.internal_error(),
            )
        return self._translated_operation(trace_id=trace_id, creation=creation, record=record)

    def _ensure_names_free(self, *, creation: PreparedCreation) -> None:
        self._name_availability.find_taken_and_raise_if_any(
            clusters=self._name_check_scope.clusters_to_check(chosen=creation.cluster),
            requested_names=self._creation_naming.requested_names(spec=creation.spec),
        )

    def _operation_from_stored_record(
        self, *, trace_id: str, creation: PreparedCreation, error_if_not_started: PublicError
    ) -> Operation:
        try:
            stored: SagaRecord | None = self._record_reader.find(saga_id=trace_id)
        except Exception:
            logger.critical(msg=f"the record of saga {trace_id} cannot be read", exc_info=True)
            return self._manual_intervention_operation(trace_id=trace_id)
        if stored is None:
            return rejected_operation(trace_id=trace_id, error=error_if_not_started)
        logger.critical(
            msg=f"saga {trace_id} stopped after it started, its outcome comes from its record", exc_info=True
        )
        return self._translated_operation(trace_id=trace_id, creation=creation, record=stored)

    def _translated_operation(
        self, *, trace_id: str, creation: PreparedCreation, record: SagaRecord
    ) -> Operation:
        try:
            return self._outcome_translator.operation_for(trace_id=trace_id, creation=creation, record=record)
        except Exception:
            logger.critical(
                msg=f"saga {trace_id} ended {record.status.value}, but its result cannot be read",
                exc_info=True,
            )
            return self._manual_intervention_operation(trace_id=trace_id)

    def _manual_intervention_operation(self, *, trace_id: str) -> Operation:
        return Operation(
            trace_id=trace_id,
            status=OperationStatus.REQUIRES_MANUAL_INTERVENTION,
            error=self._public_errors.internal_error(),
        )


def rejected_operation(*, trace_id: str, error: PublicError) -> Operation:
    logger.warning(msg=f"operation {trace_id} is rejected: {error.code}: {error.message}")
    return Operation(trace_id=trace_id, status=OperationStatus.REJECTED, error=error)
