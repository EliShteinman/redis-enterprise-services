import logging

from redis_enterprise_services.creation.creation_result import created_database
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
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
    ) -> None:
        self._scope: NameCheckScope = scope
        self._availability: NameAvailability = availability
        self._names: CreationNames = names
        self._planner: SingleSiteCreationPlanner = planner
        self._executor: SagaExecutor = executor
        self._store: OperationStore = store

    def run(self, *, trace_id: str, creation: PreparedCreation) -> Operation:
        try:
            record: SagaRecord = self._create(trace_id=trace_id, creation=creation)
        except RedisEnterpriseServicesError as error:
            logger.warning(msg=f"creating {creation.request.database.name} is rejected: {error.describe()}")
            operation: Operation = Operation(
                trace_id=trace_id,
                status=OperationStatus.REJECTED,
                error=ErrorInfo(code=error.code, message=error.message),
            )
        else:
            operation = finished_operation(trace_id=trace_id, creation=creation, record=record)
        self._store.save(operation=operation)
        return operation

    def _create(self, *, trace_id: str, creation: PreparedCreation) -> SagaRecord:
        self._availability.ensure_free(
            clusters=self._scope.clusters(chosen=creation.cluster),
            names=self._names.of(request=creation.request),
        )
        plan: SagaPlan = self._planner.plan(
            cluster=creation.cluster, database=creation.request.database, users=creation.request.users
        )
        return self._executor.run(saga_id=trace_id, plan=plan)


def finished_operation(*, trace_id: str, creation: PreparedCreation, record: SagaRecord) -> Operation:
    status: OperationStatus = OperationStatus(record.status.value)
    if record.status is not SagaStatus.SUCCEEDED:
        return Operation(trace_id=trace_id, status=status)
    return Operation(
        trace_id=trace_id, status=status, database=created_database(creation=creation, record=record)
    )
