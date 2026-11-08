import logging
from functools import partial

from redis_enterprise_services.creation.creation_outcome import CreationOutcome
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.planning.availability.creation_names import CreationNames
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
        scope: NameCheckScope,
        availability: NameAvailability,
        names: CreationNames,
        planner: SingleSiteCreationPlanner,
        executor: SagaExecutor,
        outcome: CreationOutcome,
        public_errors: PublicErrors,
        records: SagaRecordReader,
        store: OperationStore,
    ) -> None:
        self._scope: NameCheckScope = scope
        self._availability: NameAvailability = availability
        self._names: CreationNames = names
        self._planner: SingleSiteCreationPlanner = planner
        self._executor: SagaExecutor = executor
        self._outcome: CreationOutcome = outcome
        self._public_errors: PublicErrors = public_errors
        self._record_writer: SagaRecordReader = records
        self._store: OperationStore = store

    def run(self, *, trace_id: str, creation: PreparedCreation) -> Operation:
        operation: Operation = self._finished(trace_id=trace_id, creation=creation)
        self._store.save(operation=operation)
        return operation

    def _finished(self, *, trace_id: str, creation: PreparedCreation) -> Operation:
        try:
            record: SagaRecord = self._executor.run(
                saga_id=trace_id,
                plan=self._planner.plan(
                    cluster=creation.cluster, database=creation.request.database, users=creation.request.users
                ),
                check_before_start=partial(self._ensure_names_free, creation=creation),
            )
        except RedisEnterpriseServicesError as error:
            public: PublicError = self._public_errors.from_error(
                error=error, cluster_url=creation.cluster.api_url
            )
            return self._from_record(trace_id=trace_id, creation=creation, missing=public)
        except Exception:
            logger.critical(msg=f"creation {trace_id} failed on an unexpected error", exc_info=True)
            return self._from_record(
                trace_id=trace_id, creation=creation, missing=self._public_errors.internal_error()
            )
        return self._translated(trace_id=trace_id, creation=creation, record=record)

    def _ensure_names_free(self, *, creation: PreparedCreation) -> None:
        self._availability.ensure_free(
            clusters=self._scope.clusters_to_check(chosen=creation.cluster),
            names=self._names.requested_names(request=creation.request),
        )

    def _from_record(self, *, trace_id: str, creation: PreparedCreation, missing: PublicError) -> Operation:
        try:
            stored: SagaRecord | None = self._record_writer.find(saga_id=trace_id)
        except Exception:
            logger.critical(msg=f"the record of saga {trace_id} cannot be read", exc_info=True)
            return self._needs_manual_intervention(trace_id=trace_id)
        if stored is None:
            return rejected(trace_id=trace_id, error=missing)
        logger.critical(
            msg=f"saga {trace_id} stopped after it started, its outcome comes from its record", exc_info=True
        )
        return self._translated(trace_id=trace_id, creation=creation, record=stored)

    def _translated(self, *, trace_id: str, creation: PreparedCreation, record: SagaRecord) -> Operation:
        try:
            return self._outcome.of(trace_id=trace_id, creation=creation, record=record)
        except Exception:
            logger.critical(
                msg=f"saga {trace_id} ended {record.status.value}, but its result cannot be read",
                exc_info=True,
            )
            return self._needs_manual_intervention(trace_id=trace_id)

    def _needs_manual_intervention(self, *, trace_id: str) -> Operation:
        return Operation(
            trace_id=trace_id,
            status=OperationStatus.REQUIRES_MANUAL_INTERVENTION,
            error=self._public_errors.internal_error(),
        )


def rejected(*, trace_id: str, error: PublicError) -> Operation:
    logger.warning(msg=f"operation {trace_id} is rejected: {error.code}: {error.message}")
    return Operation(trace_id=trace_id, status=OperationStatus.REJECTED, error=error)
