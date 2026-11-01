import logging

from redis_enterprise_services.creation.creation_result import created_database
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.saga import DatabaseLockedError
from redis_enterprise_services.operations.error_info import ErrorInfo
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.planning.availability.creation_names import CreationNames
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.name_check_scope import NameCheckScope
from redis_enterprise_services.planning.single_site_creation import SingleSiteCreationPlanner
from redis_enterprise_services.saga.contract.models import SagaRecord, SagaStatus
from redis_enterprise_services.saga.engine.executor import SagaExecutor
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan

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
        store: OperationStore,
        internal_error_message: str,
    ) -> None:
        self._scope: NameCheckScope = scope
        self._availability: NameAvailability = availability
        self._names: CreationNames = names
        self._planner: SingleSiteCreationPlanner = planner
        self._executor: SagaExecutor = executor
        self._store: OperationStore = store
        self._internal_error: ErrorInfo = ErrorInfo(
            code=RedisEnterpriseServicesError.code, message=internal_error_message
        )

    def run(self, *, trace_id: str, creation: PreparedCreation) -> Operation:
        operation: Operation = self._outcome(trace_id=trace_id, creation=creation)
        self._store.save(operation=operation)
        return operation

    def _outcome(self, *, trace_id: str, creation: PreparedCreation) -> Operation:
        try:
            plan: SagaPlan = self._checked_plan(creation=creation)
        except RedisEnterpriseServicesError as error:
            return rejected(trace_id=trace_id, error=ErrorInfo(code=error.code, message=error.message))
        except Exception:
            logger.exception(msg=f"creating {creation.request.database.name} failed before its saga")
            return rejected(trace_id=trace_id, error=self._internal_error)
        try:
            record: SagaRecord = self._executor.run(saga_id=trace_id, plan=plan)
            return finished_operation(trace_id=trace_id, creation=creation, record=record)
        except DatabaseLockedError as error:
            return rejected(trace_id=trace_id, error=ErrorInfo(code=error.code, message=error.message))
        except Exception:
            logger.critical(msg=f"saga {trace_id} stopped on an unexpected error", exc_info=True)
            return Operation(
                trace_id=trace_id,
                status=OperationStatus.REQUIRES_MANUAL_INTERVENTION,
                error=self._internal_error,
            )

    def _checked_plan(self, *, creation: PreparedCreation) -> SagaPlan:
        self._availability.ensure_free(
            clusters=self._scope.clusters(chosen=creation.cluster),
            names=self._names.of(request=creation.request),
        )
        return self._planner.plan(
            cluster=creation.cluster, database=creation.request.database, users=creation.request.users
        )


def rejected(*, trace_id: str, error: ErrorInfo) -> Operation:
    logger.warning(msg=f"operation {trace_id} is rejected: {error.code}: {error.message}")
    return Operation(trace_id=trace_id, status=OperationStatus.REJECTED, error=error)


def finished_operation(*, trace_id: str, creation: PreparedCreation, record: SagaRecord) -> Operation:
    status: OperationStatus = OperationStatus(record.status.value)
    if record.status is not SagaStatus.SUCCEEDED:
        return Operation(trace_id=trace_id, status=status)
    return Operation(
        trace_id=trace_id, status=status, database=created_database(creation=creation, record=record)
    )
