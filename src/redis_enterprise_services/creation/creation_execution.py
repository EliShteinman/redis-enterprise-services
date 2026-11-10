import logging
from collections.abc import Callable
from functools import partial

from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.saga import UnreadableSagaRecordError
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.operations.remaining_resource import RemainingResource
from redis_enterprise_services.planning.availability.creation_names_check import CreationNamesCheck
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordReader
from redis_enterprise_services.saga.engine.saga_executor import SagaExecutor

logger: logging.Logger = logging.getLogger(name=__name__)


class CreationExecution:
    def __init__(
        self,
        *,
        names_check: CreationNamesCheck,
        planner: SingleSiteCreationPlanner,
        saga_executor: SagaExecutor,
        outcome_translator: CreationOutcomeTranslator,
        public_errors: PublicErrors,
        saga_record_reader: SagaRecordReader,
        operation_store: OperationStore,
    ) -> None:
        self._names_check: CreationNamesCheck = names_check
        self._planner: SingleSiteCreationPlanner = planner
        self._saga_executor: SagaExecutor = saga_executor
        self._outcome_translator: CreationOutcomeTranslator = outcome_translator
        self._public_errors: PublicErrors = public_errors
        self._saga_record_reader: SagaRecordReader = saga_record_reader
        self._operation_store: OperationStore = operation_store

    def run_and_save(self, *, trace_id: str, prepared_creation: PreparedCreation) -> Operation:
        operation: Operation = self._run_saga_and_translate_outcome(
            trace_id=trace_id, prepared_creation=prepared_creation
        )
        self._operation_store.save(operation=operation)
        return operation

    def _run_saga_and_translate_outcome(
        self, *, trace_id: str, prepared_creation: PreparedCreation
    ) -> Operation:
        try:
            record: SagaRecord = self._run_saga(trace_id=trace_id, prepared_creation=prepared_creation)
        except RedisEnterpriseServicesError as error:
            return self._operation_after_saga_error(
                trace_id=trace_id,
                prepared_creation=prepared_creation,
                saga_error=error,
                error_if_not_started=partial(
                    self._public_errors.for_rejection,
                    error=error,
                    cluster_url=prepared_creation.cluster.api_url,
                ),
            )
        except Exception as error:
            logger.critical(msg=f"creation {trace_id} failed on an unexpected error", exc_info=True)
            return self._operation_after_saga_error(
                trace_id=trace_id,
                prepared_creation=prepared_creation,
                saga_error=error,
                error_if_not_started=self._public_errors.internal_error,
            )
        return self._translated_or_manual_intervention_operation(
            trace_id=trace_id, prepared_creation=prepared_creation, record=record
        )

    def _run_saga(self, *, trace_id: str, prepared_creation: PreparedCreation) -> SagaRecord:
        return self._saga_executor.run(
            saga_id=trace_id,
            plan=self._planner.plan(cluster=prepared_creation.cluster, spec=prepared_creation.spec),
            check_before_start=partial(self._ensure_names_free, prepared_creation=prepared_creation),
        )

    def _ensure_names_free(self, *, prepared_creation: PreparedCreation) -> None:
        self._names_check.ensure_free(cluster=prepared_creation.cluster, spec=prepared_creation.spec)

    def _operation_after_saga_error(
        self,
        *,
        trace_id: str,
        prepared_creation: PreparedCreation,
        saga_error: Exception,
        error_if_not_started: Callable[[], PublicError],
    ) -> Operation:
        try:
            stored_record: SagaRecord | None = self._saga_record_reader.find(saga_id=trace_id)
        except UnreadableSagaRecordError:
            logger.critical(msg=f"the record of saga {trace_id} cannot be read", exc_info=True)
            return Operation.requires_manual_intervention(
                trace_id=trace_id, error=self._public_errors.internal_error()
            )
        if stored_record is None:
            return rejected_operation(trace_id=trace_id, error=error_if_not_started())
        logger.critical(
            msg=f"saga {trace_id} stopped after it started ({type(saga_error).__name__}), "
            "its outcome comes from its record"
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
            return Operation(
                trace_id=trace_id,
                status=OperationStatus.REQUIRES_MANUAL_INTERVENTION,
                error=self._public_errors.internal_error(),
                not_rolled_back=self._remaining_resources_or_none(
                    trace_id=trace_id, prepared_creation=prepared_creation, record=record
                ),
            )

    def _remaining_resources_or_none(
        self, *, trace_id: str, prepared_creation: PreparedCreation, record: SagaRecord
    ) -> list[RemainingResource] | None:
        try:
            return self._outcome_translator.remaining_resources(
                prepared_creation=prepared_creation, record=record
            )
        except Exception:
            logger.critical(
                msg=f"what saga {trace_id} left on the cluster cannot be read either", exc_info=True
            )
            return None


def rejected_operation(*, trace_id: str, error: PublicError) -> Operation:
    logger.warning(msg=f"operation {trace_id} is rejected: {error.code}: {error.message}")
    return Operation.rejected(trace_id=trace_id, error=error)


def record_interrupted_if_running(*, record: SagaRecord) -> SagaRecord:
    if record.status is not SagaStatus.RUNNING:
        return record
    logger.critical(msg=f"saga {record.saga_id} is stored as running, reported as manual intervention")
    return record.interrupted_copy()
