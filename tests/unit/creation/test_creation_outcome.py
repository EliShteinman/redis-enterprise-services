from pydantic import JsonValue

from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.config.decomposition_settings import DecompositionSettings
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.creation.creation_outcome import CreationOutcome
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.operations.error_info import ErrorInfo
from redis_enterprise_services.operations.not_rolled_back import NotRolledBack
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.planning.database_request import DatabaseRequest, DatabaseUserRequest
from redis_enterprise_services.planning.resource_names import ResourceNames
from redis_enterprise_services.saga.contract.kind import StepKind
from redis_enterprise_services.saga.contract.models import (
    SagaRecord,
    SagaStatus,
    StepError,
    StepRecord,
    StepStatus,
)

DECOMPOSITION: DecompositionSettings = DecompositionSettings(
    acl_name="{database}-{user}-acl", role_name="{database}-{user}-role", role_management="db_viewer"
)
OUTCOME: CreationOutcome = CreationOutcome(
    names=ResourceNames(settings=DECOMPOSITION),
    errors=PublicErrors(
        settings=OperationSettings(public_error_codes={"cluster_error": "step_rejected"}),
        internal_error_message="internal error",
    ),
)
CREATION: PreparedCreation = PreparedCreation(
    cluster=ClusterEntry(
        name="c1", network="net-a", environment="DEV", site="dc1", type="generic", api_url="https://c1:9443"
    ),
    request=DatabaseRequest(
        database=NewDatabase(name="orders", memory_size=104857600),
        users=[DatabaseUserRequest(name="app", password="p1", acl="+@all ~orders:*")],
    ),
)
REJECTED_BY_CLUSTER: StepError = StepError(
    code="cluster_error", message="user name is taken", remote_code="name_already_exists"
)
UNDO_FAILED: StepError = StepError(code="cluster_unavailable", message="relay is down")


def step(
    *, key: str, status: StepStatus, uid: int | None = None, error: StepError | None = None
) -> StepRecord:
    result: JsonValue = None if uid is None else {"uid": uid, "name": key, "action_uid": None}
    return StepRecord(key=key, kind=StepKind.COMPENSATABLE, status=status, result=result, error=error)


def outcome(*, status: SagaStatus, steps: list[StepRecord]) -> Operation:
    return OUTCOME.of(
        trace_id="trace-1",
        creation=CREATION,
        record=SagaRecord(saga_id="trace-1", status=status, steps=steps),
    )


def test_a_rolled_back_creation_reports_the_cluster_error_of_the_failed_step() -> None:
    operation: Operation = outcome(
        status=SagaStatus.ROLLED_BACK,
        steps=[
            step(key="database", status=StepStatus.COMPENSATED, uid=7),
            step(key="user/app", status=StepStatus.FAILED, error=REJECTED_BY_CLUSTER),
        ],
    )

    assert (operation.error, operation.not_rolled_back) == (
        ErrorInfo(
            code="step_rejected",
            message="user name is taken",
            cluster="https://c1:9443",
            cluster_error_code="name_already_exists",
        ),
        [],
    )


def test_a_creation_that_needs_intervention_lists_what_was_not_rolled_back() -> None:
    operation: Operation = outcome(
        status=SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        steps=[
            step(key="database", status=StepStatus.DONE, uid=7),
            step(key="acl/app", status=StepStatus.COMPENSATION_FAILED, uid=11, error=UNDO_FAILED),
            step(key="role/app", status=StepStatus.COMPENSATED, uid=12),
            step(key="user/app", status=StepStatus.FAILED, error=REJECTED_BY_CLUSTER),
        ],
    )

    assert operation.not_rolled_back == [
        NotRolledBack(cluster="https://c1:9443", type="database", name="orders", uid=7, error=None),
        NotRolledBack(
            cluster="https://c1:9443",
            type="acl",
            name="orders-app-acl",
            uid=11,
            error="cluster_unavailable: relay is down",
        ),
    ]
