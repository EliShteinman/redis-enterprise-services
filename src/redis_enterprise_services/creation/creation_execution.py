import logging
from collections.abc import Callable
from functools import partial

from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.creation_planning import CreationPlanning
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.saga import UnreadableSagaRecordError
from redis_enterprise_services.operations.errors.public_error import PublicError
from redis_enterprise_services.operations.errors.public_errors import PublicErrors
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.remaining_resource import RemainingResource
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordReader
from redis_enterprise_services.saga.engine.saga_executor import SagaExecutor

logger: logging.Logger = logging.getLogger(name=__name__)

UNREADABLE_REMAINING_RESOURCES: None = None


class CreationExecution[TPrepared]:
    def __init__(
        self,
        *,
        planning: CreationPlanning[TPrepared],
        saga_executor: SagaExecutor,
        outcome_translator: CreationOutcomeTranslator[TPrepared],
        public_errors: PublicErrors,
        saga_record_reader: SagaRecordReader,
        operation_store: OperationStore,
    ) -> None:
        self._planning: CreationPlanning[TPrepared] = planning
        self._saga_executor: SagaExecutor = saga_executor
        self._outcome_translator: CreationOutcomeTranslator[TPrepared] = outcome_translator
        self._public_errors: PublicErrors = public_errors
        self._saga_record_reader: SagaRecordReader = saga_record_reader
        self._operation_store: OperationStore = operation_store

    def run_and_save(self, *, trace_id: str, prepared_creation: TPrepared) -> Operation:
        operation: Operation = self._run_saga_and_translate_outcome(
            trace_id=trace_id, prepared_creation=prepared_creation
        )
        self._operation_store.save(operation=operation)
        return operation

    def _run_saga_and_translate_outcome(self, *, trace_id: str, prepared_creation: TPrepared) -> Operation:
        fallback_cluster_url: str = self._planning.fallback_cluster_url(prepared_creation=prepared_creation)
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
                    fallback_cluster_url=fallback_cluster_url,
                ),
                interruption_error=self._public_errors.from_error(
                    error=error, fallback_cluster_url=fallback_cluster_url
                ),
            )
        except Exception as error:
            logger.critical(msg=f"creation {trace_id} failed on an unexpected error", exc_info=True)
            unexpected_error: PublicError = self._public_errors.unexpected_error(error=error)
            return self._operation_after_saga_error(
                trace_id=trace_id,
                prepared_creation=prepared_creation,
                saga_error=error,
                error_if_not_started=lambda: unexpected_error,
                interruption_error=unexpected_error,
            )
        return self._translated_or_manual_intervention_operation(
            trace_id=trace_id,
            prepared_creation=prepared_creation,
            record=record,
            interruption_error=self._public_errors.internal_error(),
        )

    def _run_saga(self, *, trace_id: str, prepared_creation: TPrepared) -> SagaRecord:
        return self._saga_executor.run(
            saga_id=trace_id,
            plan=self._planning.plan(trace_id=trace_id, prepared_creation=prepared_creation),
            check_before_start=partial(self._planning.ensure_names_free, prepared_creation=prepared_creation),
        )

    def _operation_after_saga_error(
        self,
        *,
        trace_id: str,
        prepared_creation: TPrepared,
        saga_error: Exception,
        error_if_not_started: Callable[[], PublicError],
        interruption_error: PublicError,
    ) -> Operation:
        try:
            stored_record: SagaRecord | None = self._saga_record_reader.find(saga_id=trace_id)
        except UnreadableSagaRecordError:
            logger.critical(msg=f"the record of saga {trace_id} cannot be read", exc_info=True)
            return Operation.requires_manual_intervention(trace_id=trace_id, error=interruption_error)
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
            interruption_error=interruption_error,
        )

    def _translated_or_manual_intervention_operation(
        self,
        *,
        trace_id: str,
        prepared_creation: TPrepared,
        record: SagaRecord,
        interruption_error: PublicError,
    ) -> Operation:
        try:
            return self._outcome_translator.operation_from_ended_record(
                trace_id=trace_id,
                prepared_creation=prepared_creation,
                record=record,
                interruption_error=interruption_error,
            )
        except Exception as error:
            logger.critical(
                msg=f"saga {trace_id} ended {record.status.value}, but its result cannot be read",
                exc_info=True,
            )
            return Operation.failed(
                trace_id=trace_id,
                status=OperationStatus.REQUIRES_MANUAL_INTERVENTION,
                error=self._public_errors.unexpected_error(error=error),
                not_rolled_back=self._remaining_resources_if_readable(
                    trace_id=trace_id, prepared_creation=prepared_creation, record=record
                ),
            )

    def _remaining_resources_if_readable(
        self, *, trace_id: str, prepared_creation: TPrepared, record: SagaRecord
    ) -> list[RemainingResource] | None:
        try:
            return self._outcome_translator.remaining_resources(
                prepared_creation=prepared_creation, record=record
            )
        except Exception:
            logger.critical(
                msg=f"what saga {trace_id} left on the cluster cannot be read either", exc_info=True
            )
            return UNREADABLE_REMAINING_RESOURCES


def rejected_operation(*, trace_id: str, error: PublicError) -> Operation:
    logger.warning(msg=f"operation {trace_id} is rejected: {error.code}: {error.message}")
    return Operation.rejected(trace_id=trace_id, error=error)


def record_interrupted_if_running(*, record: SagaRecord) -> SagaRecord:
    if record.status is not SagaStatus.RUNNING:
        return record
    logger.critical(msg=f"saga {record.saga_id} is stored as running, reported as manual intervention")
    return record.interrupted_copy()
