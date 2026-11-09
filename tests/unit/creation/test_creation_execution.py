from unittest.mock import ANY, MagicMock, create_autospec

import pytest
from pydantic import JsonValue

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.planning import NameTakenError
from redis_enterprise_services.exceptions.saga import ResourcesLockedError, UnreadableSagaRecordError
from redis_enterprise_services.operations.database_result import DatabasePermissionResult, DatabaseResult
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.planning.availability.chosen_cluster_scope import ChosenClusterScope
from redis_enterprise_services.planning.availability.creation_names_check import CreationNamesCheck
from redis_enterprise_services.planning.availability.creation_naming import CreationNaming
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.database_spec import (
    DatabaseSpec,
    DatabaseUserSpec,
)
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordReader
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.engine.saga_executor import SagaExecutor

PREPARED_CREATION: PreparedCreation = PreparedCreation(
    cluster=ConfiguredCluster(
        name="c1", network="net-a", environment="DEV", site="dc1", type="generic", api_url="https://c1:9443"
    ),
    spec=DatabaseSpec(
        database=NewDatabase(name="orders", memory_size=104857600),
        users=[DatabaseUserSpec(name="app", password="p1-passw0rd", acl_rule="+@all ~orders:*")],
    ),
)
USER_RESOURCES: UserResourcesSettings = UserResourcesSettings(
    acl_name_template="{database}-{user}-acl",
    role_name_template="{database}-{user}-role",
    role_management="db_viewer",
)
PUBLIC_ERRORS: PublicErrors = PublicErrors(
    settings=OperationSettings(
        public_code_by_internal_code={"name_taken": "name_taken"},
        public_codes_with_cluster_details=frozenset(),
    ),
    internal_error_message="internal error",
)
UID_BY_STEP_KEY: dict[str, int] = {
    "database": 7,
    "acl/app": 11,
    "role/app": 12,
    "user/app": 13,
    "permissions": 7,
}
FIELDS_BY_STEP_KEY: dict[str, dict[str, JsonValue]] = {
    "acl/app": {"uid": 11, "name": "orders-app-acl", "acl": "+@all ~orders:*"},
    "user/app": {"uid": 13, "name": "app", "role_uids": [12]},
}
ENDPOINT: dict[str, JsonValue] = {"dns_name": "redis-12000.c1", "port": 12000, "addr": ["10.0.0.5"]}
READ_BACK_VALUES: dict[str, JsonValue] = {
    **{name: f"stored {name}" for name in NewDatabase.model_fields},
    "name": "orders",
    "memory_size": 104857700,
    "uid": 7,
    "status": "active",
    "endpoints": [ENDPOINT],
}


def step_result(*, key: str, uid: int) -> dict[str, JsonValue]:
    fields: dict[str, JsonValue] = FIELDS_BY_STEP_KEY.get(key, {})
    return {"uid": uid, "name": fields.get("name", key), "action_uid": None, "fields": fields}


def saga_record_with_every_step_done(*, status: SagaStatus) -> SagaRecord:
    return saga_record_with_steps(status=status, step_status=StepStatus.DONE)


def saga_record_with_steps(*, status: SagaStatus, step_status: StepStatus) -> SagaRecord:
    return SagaRecord(
        saga_id="trace-1",
        status=status,
        steps=[
            *(
                StepRecord(
                    key=key,
                    kind=StepKind.COMPENSATABLE,
                    status=step_status,
                    result=step_result(key=key, uid=uid),
                )
                for key, uid in UID_BY_STEP_KEY.items()
            ),
            StepRecord(
                key="read-database",
                kind=StepKind.COMPENSATABLE,
                status=step_status,
                result={"values": READ_BACK_VALUES, "cluster_state_id": 3},
            ),
        ],
    )


class ExecutionHarness:
    def __init__(self) -> None:
        self.name_availability: MagicMock = create_autospec(spec=NameAvailability, instance=True)
        self.saga_executor: MagicMock = create_autospec(spec=SagaExecutor, instance=True)
        self.operation_store: MagicMock = create_autospec(spec=OperationStore, instance=True)
        self.planner: MagicMock = create_autospec(spec=SingleSiteCreationPlanner, instance=True)
        self.saga_record_reader: MagicMock = create_autospec(spec=SagaRecordReader, instance=True)
        self.saga_record_reader.find.return_value = None
        self.execution: CreationExecution = CreationExecution(
            names_check=CreationNamesCheck(
                name_check_scope=ChosenClusterScope(),
                name_availability=self.name_availability,
                creation_naming=create_autospec(spec=CreationNaming, instance=True),
            ),
            planner=self.planner,
            saga_executor=self.saga_executor,
            outcome_translator=CreationOutcomeTranslator(
                resource_naming=UserResourceNaming(settings=USER_RESOURCES),
                public_errors=PUBLIC_ERRORS,
                database_settings=load_settings().database,
            ),
            public_errors=PUBLIC_ERRORS,
            saga_record_reader=self.saga_record_reader,
            operation_store=self.operation_store,
        )

    def run_and_save(self) -> Operation:
        return self.execution.run_and_save(trace_id="trace-1", prepared_creation=PREPARED_CREATION)


@pytest.fixture
def created() -> DatabaseResult:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.return_value = saga_record_with_every_step_done(status=SagaStatus.SUCCEEDED)
    database: DatabaseResult | None = harness.run_and_save().database
    assert database is not None
    return database


def test_the_top_of_the_tree_comes_from_the_read_back_not_the_request(created: DatabaseResult) -> None:
    assert (created.name, created.memory_size) == ("orders", 104857700)


def test_a_created_database_returns_the_endpoints_the_cluster_reported(created: DatabaseResult) -> None:
    assert created.clusters[0].access.model_dump()["endpoints"] == [ENDPOINT]


def test_a_created_database_returns_every_creation_field_as_the_cluster_stored_it(
    created: DatabaseResult,
) -> None:
    assert created.clusters[0].db.settings == {
        name: READ_BACK_VALUES[name] for name in NewDatabase.model_fields
    }


def test_each_user_comes_back_with_its_acl_as_one_permission(created: DatabaseResult) -> None:
    assert created.clusters[0].db.permissions == [
        DatabasePermissionResult(
            user_uid=13, user_name="app", user_password="p1-passw0rd", acl_uid=11, acl_rule="+@all ~orders:*"
        )
    ]


@pytest.mark.parametrize(
    argnames=("status", "step_status"),
    argvalues=[
        (SagaStatus.ROLLED_BACK, StepStatus.COMPENSATED),
        (SagaStatus.REQUIRES_MANUAL_INTERVENTION, StepStatus.COMPENSATION_FAILED),
    ],
)
def test_a_failed_saga_ends_with_its_status_and_no_database(
    status: SagaStatus, step_status: StepStatus
) -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.return_value = saga_record_with_steps(status=status, step_status=step_status)

    operation: Operation = harness.run_and_save()

    assert (operation.status.value, operation.database) == (status.value, None)


def test_taken_names_reject_the_creation_before_the_saga_runs() -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.side_effect = NameTakenError(message="database orders exists on c1")

    operation: Operation = harness.run_and_save()

    assert (operation.status, operation.error and operation.error.code) == (
        OperationStatus.REJECTED,
        "name_taken",
    )


def test_a_project_error_after_the_saga_started_is_not_reported_as_rejected() -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.side_effect = NameTakenError(message="raised after the first step")
    harness.saga_record_reader.find.return_value = saga_record_with_every_step_done(
        status=SagaStatus.REQUIRES_MANUAL_INTERVENTION
    )

    assert harness.run_and_save().status is OperationStatus.REQUIRES_MANUAL_INTERVENTION


def test_a_record_still_stored_as_running_is_reported_as_manual_intervention() -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.side_effect = RuntimeError("bug while finishing")
    harness.saga_record_reader.find.return_value = saga_record_with_every_step_done(status=SagaStatus.RUNNING)

    assert harness.run_and_save().status is OperationStatus.REQUIRES_MANUAL_INTERVENTION


def test_a_record_that_cannot_be_read_after_a_saga_error_is_reported_as_manual_intervention() -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.side_effect = RuntimeError("bug while finishing")
    harness.saga_record_reader.find.side_effect = UnreadableSagaRecordError(message="unreadable")

    assert harness.run_and_save().status is OperationStatus.REQUIRES_MANUAL_INTERVENTION


@pytest.mark.parametrize(
    argnames="executor_result",
    argvalues=[
        saga_record_with_every_step_done(status=SagaStatus.SUCCEEDED),
        ResourcesLockedError(message="orders is locked"),
    ],
)
def test_the_final_operation_is_stored(executor_result: SagaRecord | RedisEnterpriseServicesError) -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.side_effect = [executor_result]

    operation: Operation = harness.run_and_save()

    harness.operation_store.save.assert_called_once_with(operation=operation)


def test_an_unexpected_error_before_the_saga_starts_rejects_the_operation() -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.planner.plan.side_effect = RuntimeError("bug")

    operation: Operation = harness.run_and_save()

    assert (operation.status, operation.error and operation.error.code) == (
        OperationStatus.REJECTED,
        "internal_error",
    )


def test_a_result_that_cannot_be_translated_needs_manual_intervention() -> None:
    harness: ExecutionHarness = ExecutionHarness()
    record: SagaRecord = saga_record_with_every_step_done(status=SagaStatus.SUCCEEDED)
    harness.saga_executor.run.return_value = record.model_copy(
        update={"steps": [step for step in record.steps if step.key != "user/app"]}
    )

    operation: Operation = harness.run_and_save()

    assert (operation.status, operation.error and operation.error.code, operation.not_rolled_back) == (
        OperationStatus.REQUIRES_MANUAL_INTERVENTION,
        "internal_error",
        None,
    )


def test_a_saga_stopped_by_an_unexpected_error_lists_what_was_not_rolled_back() -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.side_effect = RuntimeError("bug")
    harness.saga_record_reader.find.return_value = saga_record_with_every_step_done(
        status=SagaStatus.REQUIRES_MANUAL_INTERVENTION
    )

    operation: Operation = harness.run_and_save()

    assert operation.not_rolled_back is not None
    assert [remaining.resource_type for remaining in operation.not_rolled_back] == [
        "database",
        "acl",
        "role",
        "user",
        "permissions",
    ]


def test_the_check_before_start_looks_for_taken_names() -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.return_value = saga_record_with_every_step_done(status=SagaStatus.SUCCEEDED)

    harness.run_and_save()
    harness.saga_executor.run.call_args.kwargs["check_before_start"]()

    harness.name_availability.ensure_free.assert_called_once_with(
        clusters=[PREPARED_CREATION.cluster], requested_names=ANY
    )
