from pydantic import JsonValue

from redis_enterprise_services.config.cluster_inventory import ClusterEntry
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.creation.creation_outcome import CreationOutcome
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.operations.remaining_resource import RemainingResource
from redis_enterprise_services.planning.database_creation_request import (
    DatabaseCreationRequest,
    DatabaseUserRequest,
)
from redis_enterprise_services.planning.user_resource_names import UserResourceNames
from redis_enterprise_services.saga.contract.saga_record import (
    SagaRecord,
    SagaStatus,
    StepError,
    StepRecord,
    StepStatus,
)
from redis_enterprise_services.saga.contract.step_kind import StepKind

USER_RESOURCES: UserResourcesSettings = UserResourcesSettings(
    acl_name_template="{database}-{user}-acl",
    role_name_template="{database}-{user}-role",
    role_management="db_viewer",
)
OUTCOME: CreationOutcome = CreationOutcome(
    names=UserResourceNames(settings=USER_RESOURCES),
    public_errors=PublicErrors(
        settings=OperationSettings(
            public_code_by_error_code={
                "cluster_rejected_request": "cluster_request_failed",
                "unreadable_cluster_response": "cluster_unavailable",
            },
            cluster_caused_public_codes=frozenset({"cluster_request_failed", "cluster_unavailable"}),
        ),
        internal_error_message="internal error",
    ),
)
CREATION: PreparedCreation = PreparedCreation(
    cluster=ClusterEntry(
        name="c1", network="net-a", environment="DEV", site="dc1", type="generic", api_url="https://c1:9443"
    ),
    request=DatabaseCreationRequest(
        database=NewDatabase(name="orders", memory_size=104857600),
        users=[DatabaseUserRequest(name="app", password="p1", acl_rule="+@all ~orders:*")],
    ),
)
REJECTED_BY_CLUSTER: StepError = StepError(
    code="cluster_rejected_request", message="user name is taken", remote_code="name_already_exists"
)
UNDO_FAILED: StepError = StepError(code="unreadable_cluster_response", message="relay is down")


def step(
    *,
    key: str,
    status: StepStatus,
    uid: int | None = None,
    error: StepError | None = None,
    compensation_error: StepError | None = None,
) -> StepRecord:
    result: JsonValue = None if uid is None else {"uid": uid, "name": key, "action_uid": None}
    return StepRecord(
        key=key,
        kind=StepKind.COMPENSATABLE,
        status=status,
        result=result,
        error=error,
        compensation_error=compensation_error,
    )


def outcome(*, status: SagaStatus, steps: list[StepRecord], stopped_at: str) -> Operation:
    return OUTCOME.of(
        trace_id="trace-1",
        creation=CREATION,
        record=SagaRecord(saga_id="trace-1", status=status, steps=steps, stopped_at=stopped_at),
    )


def test_a_rolled_back_creation_reports_the_cluster_error_of_the_step_that_stopped_it() -> None:
    operation: Operation = outcome(
        status=SagaStatus.ROLLED_BACK,
        steps=[
            step(key="database", status=StepStatus.COMPENSATED, uid=7, error=REJECTED_BY_CLUSTER),
            step(key="acl/app", status=StepStatus.PENDING),
        ],
        stopped_at="database",
    )

    assert (operation.error, operation.not_rolled_back) == (
        PublicError(
            code="cluster_request_failed",
            message="user name is taken",
            cluster_url="https://c1:9443",
            cluster_error_code="name_already_exists",
        ),
        [],
    )


def test_a_creation_that_needs_intervention_lists_what_was_not_rolled_back() -> None:
    operation: Operation = outcome(
        status=SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        steps=[
            step(key="database", status=StepStatus.DONE, uid=7),
            step(
                key="acl/app",
                status=StepStatus.COMPENSATION_FAILED,
                uid=11,
                error=REJECTED_BY_CLUSTER,
                compensation_error=UNDO_FAILED,
            ),
            step(key="role/app", status=StepStatus.COMPENSATED, uid=12),
            step(key="user/app", status=StepStatus.FAILED, error=REJECTED_BY_CLUSTER),
        ],
        stopped_at="user/app",
    )

    assert operation.not_rolled_back == [
        RemainingResource(
            cluster_url="https://c1:9443", resource_type="database", name="orders", uid=7, last_error=None
        ),
        RemainingResource(
            cluster_url="https://c1:9443",
            resource_type="acl",
            name="orders-app-acl",
            uid=11,
            last_error="cluster_unavailable: relay is down",
        ),
    ]
