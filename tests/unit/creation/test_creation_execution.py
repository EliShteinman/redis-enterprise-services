from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.config.decomposition_settings import DecompositionSettings
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_outcome import CreationOutcome
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.planning import NameTakenError
from redis_enterprise_services.exceptions.saga import DatabaseLockedError
from redis_enterprise_services.operations.database_result import DatabaseResult, DatabaseUserResult
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.planning.availability.chosen_cluster_scope import ChosenClusterScope
from redis_enterprise_services.planning.availability.creation_names import CreationNames
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.database_request import DatabaseRequest, DatabaseUserRequest
from redis_enterprise_services.planning.resource_names import ResourceNames
from redis_enterprise_services.planning.single_site_creation import SingleSiteCreationPlanner
from redis_enterprise_services.saga.contract.kind import StepKind
from redis_enterprise_services.saga.contract.models import SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.state import SagaRecordReader
from redis_enterprise_services.saga.engine.executor import SagaExecutor

CREATION: PreparedCreation = PreparedCreation(
    cluster=ClusterEntry(
        name="c1", network="net-a", environment="DEV", site="dc1", type="generic", api_url="https://c1:9443"
    ),
    request=DatabaseRequest(
        database=NewDatabase(name="orders", memory_size=104857600),
        users=[DatabaseUserRequest(name="app", password="p1", acl="+@all ~orders:*")],
    ),
)
DECOMPOSITION: DecompositionSettings = DecompositionSettings(
    acl_name="{database}-{user}-acl", role_name="{database}-{user}-role", role_management="db_viewer"
)
ERRORS: PublicErrors = PublicErrors(
    settings=OperationSettings(
        public_error_codes={"name_taken": "name_taken"}, cluster_error_codes=frozenset()
    ),
    internal_error_message="internal error",
)
UIDS: dict[str, int] = {"database": 7, "acl/app": 11, "role/app": 12, "user/app": 13, "permissions": 7}


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
            for key, uid in UIDS.items()
        ],
    )


class Creation:
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
            names=create_autospec(spec=CreationNames, instance=True),
            planner=self.planner,
            executor=self.executor,
            outcome=CreationOutcome(names=ResourceNames(settings=DECOMPOSITION), errors=ERRORS),
            errors=ERRORS,
            records=self.records,
            store=self.store,
        )

    def run(self) -> Operation:
        return self.execution.run(trace_id="trace-1", creation=CREATION)


def test_a_created_database_returns_the_uids_of_each_user() -> None:
    creation: Creation = Creation()
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
    creation: Creation = Creation()
    creation.executor.run.return_value = saga_record(status=status)

    operation: Operation = creation.run()

    assert (operation.status.value, operation.database) == (status.value, None)


def test_taken_names_reject_the_creation_before_the_saga_runs() -> None:
    creation: Creation = Creation()
    creation.executor.run.side_effect = NameTakenError(message="database orders exists on c1")

    operation: Operation = creation.run()

    assert (operation.status, operation.error and operation.error.code) == (
        OperationStatus.REJECTED,
        "name_taken",
    )


@pytest.mark.parametrize(
    argnames="outcome",
    argvalues=[saga_record(status=SagaStatus.SUCCEEDED), DatabaseLockedError(message="orders is locked")],
)
def test_the_final_operation_is_stored(outcome: SagaRecord | RedisEnterpriseServicesError) -> None:
    creation: Creation = Creation()
    creation.executor.run.side_effect = [outcome]

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
    creation: Creation = Creation()
    creation.planner.plan.side_effect = RuntimeError("bug") if failing == "planner" else None
    creation.executor.run.side_effect = RuntimeError("bug") if failing == "executor" else None
    creation.records.find.return_value = (
        saga_record(status=SagaStatus.REQUIRES_MANUAL_INTERVENTION) if failing == "executor" else None
    )

    operation: Operation = creation.run()

    assert (operation.status, operation.error and operation.error.code) == (status, "internal_error")


def test_a_saga_stopped_by_an_unexpected_error_lists_what_it_left() -> None:
    creation: Creation = Creation()
    creation.executor.run.side_effect = RuntimeError("bug")
    creation.records.find.return_value = saga_record(status=SagaStatus.REQUIRES_MANUAL_INTERVENTION)

    operation: Operation = creation.run()

    assert operation.not_rolled_back is not None
    assert [left.type for left in operation.not_rolled_back] == [
        "database",
        "acl",
        "role",
        "user",
        "permissions",
    ]


def test_the_names_are_checked_before_the_saga_starts() -> None:
    creation: Creation = Creation()
    creation.executor.run.return_value = saga_record(status=SagaStatus.SUCCEEDED)

    creation.run()
    creation.executor.run.call_args.kwargs["before_start"]()

    assert creation.availability.ensure_free.called
