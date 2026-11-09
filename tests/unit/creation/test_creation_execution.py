from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
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
        users=[DatabaseUserSpec(name="app", password="p1", acl_rule="+@all ~orders:*")],
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


def saga_record_with_every_step_done(*, status: SagaStatus) -> SagaRecord:
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
        self.name_availability: MagicMock = create_autospec(spec=NameAvailability, instance=True)
        self.saga_executor: MagicMock = create_autospec(spec=SagaExecutor, instance=True)
        self.operation_store: MagicMock = create_autospec(spec=OperationStore, instance=True)
        self.planner: MagicMock = create_autospec(spec=SingleSiteCreationPlanner, instance=True)
        self.saga_record_reader: MagicMock = create_autospec(spec=SagaRecordReader, instance=True)
        self.saga_record_reader.find.return_value = None
        self.execution: CreationExecution = CreationExecution(
            name_check_scope=ChosenClusterScope(),
            name_availability=self.name_availability,
            creation_naming=create_autospec(spec=CreationNaming, instance=True),
            planner=self.planner,
            saga_executor=self.saga_executor,
            outcome_translator=CreationOutcomeTranslator(
                resource_naming=UserResourceNaming(settings=USER_RESOURCES), public_errors=PUBLIC_ERRORS
            ),
            public_errors=PUBLIC_ERRORS,
            saga_record_reader=self.saga_record_reader,
            operation_store=self.operation_store,
        )

    def run_and_save(self) -> Operation:
        return self.execution.run_and_save(trace_id="trace-1", prepared_creation=PREPARED_CREATION)


def test_a_created_database_returns_the_uids_of_each_user() -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.return_value = saga_record_with_every_step_done(status=SagaStatus.SUCCEEDED)

    database: DatabaseResult | None = harness.run_and_save().database

    assert database is not None
    assert (database.db_id, database.clusters[0].users) == (
        7,
        [DatabaseUserResult(name="app", user_uid=13, role_uid=12, acl_uid=11)],
    )


@pytest.mark.parametrize(
    argnames="status", argvalues=[SagaStatus.ROLLED_BACK, SagaStatus.REQUIRES_MANUAL_INTERVENTION]
)
def test_a_failed_saga_ends_with_its_status_and_no_database(status: SagaStatus) -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.return_value = saga_record_with_every_step_done(status=status)

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


def unreadable_record(*, saga_id: str) -> SagaRecord:
    return SagaRecord.model_validate_json(json_data="{}")


def test_a_record_that_cannot_be_read_after_a_saga_error_is_reported_as_manual_intervention() -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.saga_executor.run.side_effect = RuntimeError("bug while finishing")
    harness.saga_record_reader.find.side_effect = unreadable_record

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


@pytest.mark.parametrize(
    argnames=("failing_collaborator", "status"),
    argvalues=[
        ("planner", OperationStatus.REJECTED),
        ("executor", OperationStatus.REQUIRES_MANUAL_INTERVENTION),
    ],
)
def test_an_unexpected_error_still_ends_the_operation(
    failing_collaborator: str, status: OperationStatus
) -> None:
    harness: ExecutionHarness = ExecutionHarness()
    harness.planner.plan.side_effect = RuntimeError("bug") if failing_collaborator == "planner" else None
    harness.saga_executor.run.side_effect = (
        RuntimeError("bug") if failing_collaborator == "executor" else None
    )
    harness.saga_record_reader.find.return_value = (
        saga_record_with_every_step_done(status=SagaStatus.REQUIRES_MANUAL_INTERVENTION)
        if failing_collaborator == "executor"
        else None
    )

    operation: Operation = harness.run_and_save()

    assert (operation.status, operation.error and operation.error.code) == (status, "internal_error")


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

    assert harness.name_availability.ensure_free.called
