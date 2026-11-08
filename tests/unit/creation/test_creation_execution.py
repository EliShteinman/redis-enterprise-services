from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.config.cluster_inventory import ClusterEntry
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.planning import NameTakenError
from redis_enterprise_services.exceptions.saga import ResourcesLockedError
from redis_enterprise_services.operations.database_result import DatabaseResult, DatabaseUserResult
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.planning.availability.chosen_cluster_scope import ChosenClusterScope
from redis_enterprise_services.planning.availability.creation_names import CreationNames
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.database_creation_request import (
    DatabaseCreationRequest,
    DatabaseUserRequest,
)
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.planning.user_resource_names import UserResourceNames
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordReader
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.engine.saga_executor import SagaExecutor

CREATION: PreparedCreation = PreparedCreation(
    cluster=ClusterEntry(
        name="c1", network="net-a", environment="DEV", site="dc1", type="generic", api_url="https://c1:9443"
    ),
    spec=DatabaseCreationRequest(
        database=NewDatabase(name="orders", memory_size=104857600),
        users=[DatabaseUserRequest(name="app", password="p1", acl_rule="+@all ~orders:*")],
    ),
)
USER_RESOURCES: UserResourcesSettings = UserResourcesSettings(
    acl_name_template="{database}-{user}-acl",
    role_name_template="{database}-{user}-role",
    role_management="db_viewer",
)
PUBLIC_ERRORS: PublicErrors = PublicErrors(
    settings=OperationSettings(
        public_code_by_error_code={"name_taken": "name_taken"}, cluster_caused_public_codes=frozenset()
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


def saga_record(*, status: SagaStatus) -> SagaRecord:
    return SagaRecord(
        saga_id="trace-1",
        status=status,
        steps=[
            StepRecord(
                key=key,
                kind=StepKind.COMPENSATABLE,
                status=StepStatus.DONE,
                result={"uid": uid, "name": key, "action_uid": None},
            )
            for key, uid in UID_BY_STEP_KEY.items()
        ],
    )


class ExecutionHarness:
    def __init__(self) -> None:
        self.availability: MagicMock = create_autospec(spec=NameAvailability, instance=True)
        self.executor: MagicMock = create_autospec(spec=SagaExecutor, instance=True)
        self.store: MagicMock = create_autospec(spec=OperationStore, instance=True)
        self.planner: MagicMock = create_autospec(spec=SingleSiteCreationPlanner, instance=True)
        self.records: MagicMock = create_autospec(spec=SagaRecordReader, instance=True)
        self.records.find.return_value = None
        self.execution: CreationExecution = CreationExecution(
            scope=ChosenClusterScope(),
            availability=self.availability,
            creation_names=create_autospec(spec=CreationNames, instance=True),
            planner=self.planner,
            executor=self.executor,
            outcome=CreationOutcomeTranslator(
                resource_names=UserResourceNames(settings=USER_RESOURCES), public_errors=PUBLIC_ERRORS
            ),
            public_errors=PUBLIC_ERRORS,
            record_reader=self.records,
            store=self.store,
        )

    def run(self) -> Operation:
        return self.execution.run(trace_id="trace-1", creation=CREATION)


def test_a_created_database_returns_the_uids_of_each_user() -> None:
    creation: ExecutionHarness = ExecutionHarness()
    creation.executor.run.return_value = saga_record(status=SagaStatus.SUCCEEDED)

    database: DatabaseResult | None = creation.run().database

    assert database is not None
    assert (database.db_id, database.clusters[0].users) == (
        7,
        [DatabaseUserResult(name="app", user_uid=13, role_uid=12, acl_uid=11)],
    )


@pytest.mark.parametrize(
    argnames="status", argvalues=[SagaStatus.ROLLED_BACK, SagaStatus.REQUIRES_MANUAL_INTERVENTION]
)
def test_a_failed_saga_ends_with_its_status_and_no_database(status: SagaStatus) -> None:
    creation: ExecutionHarness = ExecutionHarness()
    creation.executor.run.return_value = saga_record(status=status)

    operation: Operation = creation.run()

    assert (operation.status.value, operation.database) == (status.value, None)


def test_taken_names_reject_the_creation_before_the_saga_runs() -> None:
    creation: ExecutionHarness = ExecutionHarness()
    creation.executor.run.side_effect = NameTakenError(message="database orders exists on c1")

    operation: Operation = creation.run()

    assert (operation.status, operation.error and operation.error.code) == (
        OperationStatus.REJECTED,
        "name_taken",
    )


def test_a_project_error_after_the_saga_started_is_not_reported_as_rejected() -> None:
    creation: ExecutionHarness = ExecutionHarness()
    creation.executor.run.side_effect = NameTakenError(message="raised after the first step")
    creation.records.find.return_value = saga_record(status=SagaStatus.REQUIRES_MANUAL_INTERVENTION)

    assert creation.run().status is OperationStatus.REQUIRES_MANUAL_INTERVENTION


def test_a_record_still_stored_as_running_is_reported_as_manual_intervention() -> None:
    creation: ExecutionHarness = ExecutionHarness()
    creation.executor.run.side_effect = RuntimeError("bug while finishing")
    creation.records.find.return_value = saga_record(status=SagaStatus.RUNNING)

    assert creation.run().status is OperationStatus.REQUIRES_MANUAL_INTERVENTION


@pytest.mark.parametrize(
    argnames="executor_result",
    argvalues=[saga_record(status=SagaStatus.SUCCEEDED), ResourcesLockedError(message="orders is locked")],
)
def test_the_final_operation_is_stored(executor_result: SagaRecord | RedisEnterpriseServicesError) -> None:
    creation: ExecutionHarness = ExecutionHarness()
    creation.executor.run.side_effect = [executor_result]

    operation: Operation = creation.run()

    creation.store.save.assert_called_once_with(operation=operation)


@pytest.mark.parametrize(
    argnames=("failing", "status"),
    argvalues=[
        ("planner", OperationStatus.REJECTED),
        ("executor", OperationStatus.REQUIRES_MANUAL_INTERVENTION),
    ],
)
def test_an_unexpected_error_still_ends_the_operation(failing: str, status: OperationStatus) -> None:
    creation: ExecutionHarness = ExecutionHarness()
    creation.planner.plan.side_effect = RuntimeError("bug") if failing == "planner" else None
    creation.executor.run.side_effect = RuntimeError("bug") if failing == "executor" else None
    creation.records.find.return_value = (
        saga_record(status=SagaStatus.REQUIRES_MANUAL_INTERVENTION) if failing == "executor" else None
    )

    operation: Operation = creation.run()

    assert (operation.status, operation.error and operation.error.code) == (status, "internal_error")


def test_a_saga_stopped_by_an_unexpected_error_lists_what_it_left() -> None:
    creation: ExecutionHarness = ExecutionHarness()
    creation.executor.run.side_effect = RuntimeError("bug")
    creation.records.find.return_value = saga_record(status=SagaStatus.REQUIRES_MANUAL_INTERVENTION)

    operation: Operation = creation.run()

    assert operation.not_rolled_back is not None
    assert [left.resource_type for left in operation.not_rolled_back] == [
        "database",
        "acl",
        "role",
        "user",
        "permissions",
    ]


def test_the_names_are_checked_before_the_saga_starts() -> None:
    creation: ExecutionHarness = ExecutionHarness()
    creation.executor.run.return_value = saga_record(status=SagaStatus.SUCCEEDED)

    creation.run()
    creation.executor.run.call_args.kwargs["check_before_start"]()

    assert creation.availability.ensure_free.called
