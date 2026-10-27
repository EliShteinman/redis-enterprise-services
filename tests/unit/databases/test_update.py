from unittest.mock import MagicMock, call, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.credentials import SharedCredentialsProvider
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.databases.active_waiter import DatabaseActiveWaiter
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.databases.repository import DatabaseRepository
from redis_enterprise_services.databases.update import DatabaseUpdate, DatabaseUpdateInput
from redis_enterprise_services.edge.models import ClusterCredentials
from redis_enterprise_services.exceptions.cluster import UnrestorableFieldsError

UID: int = 1
CREDENTIALS: ClusterCredentials = ClusterCredentials(username="admin", password=SecretStr("secret"))
ADDRESS: ClusterAddress = ClusterAddress(network="local", api_url="https://cluster.local:9443")
TARGET: ClusterTarget = ClusterTarget(
    network=ADDRESS.network, api_url=ADDRESS.api_url, credentials=CREDENTIALS
)
NEW_VALUES: dict[str, JsonValue] = {"memory_size": 200, "eviction_policy": "noeviction"}
OLD_VALUES: dict[str, JsonValue] = {"memory_size": 100, "eviction_policy": "volatile-lru"}
SNAPSHOT: DatabaseFields = DatabaseFields(values=OLD_VALUES, cluster_state_id=7)
CURRENT: DatabaseFields = DatabaseFields(values=NEW_VALUES, cluster_state_id=9)
STEP_INPUT: DatabaseUpdateInput = DatabaseUpdateInput(cluster=ADDRESS, uid=UID, values=NEW_VALUES)


@pytest.fixture
def repository() -> MagicMock:
    repository: MagicMock = create_autospec(spec=DatabaseRepository, instance=True)
    repository.get_fields.side_effect = [SNAPSHOT, CURRENT]
    return repository


@pytest.fixture
def active_waiter() -> MagicMock:
    return create_autospec(spec=DatabaseActiveWaiter, instance=True)


@pytest.fixture
def update(repository: MagicMock, active_waiter: MagicMock) -> DatabaseUpdate:
    return DatabaseUpdate(
        repository=repository,
        active_waiter=active_waiter,
        credentials=SharedCredentialsProvider(credentials=CREDENTIALS),
    )


def run(*, update: DatabaseUpdate) -> list[DatabaseFields]:
    kept: list[DatabaseFields] = []
    update.execute(step_input=STEP_INPUT, keep_result=kept.append)
    return kept


def test_execute_snapshots_only_the_fields_it_changes(repository: MagicMock, update: DatabaseUpdate) -> None:
    run(update=update)

    repository.get_fields.assert_called_once_with(target=TARGET, uid=UID, fields=list(NEW_VALUES))


def test_execute_hands_the_snapshot_to_the_saga(update: DatabaseUpdate) -> None:
    assert run(update=update) == [SNAPSHOT]


def test_execute_puts_the_new_values_with_the_snapshot_state_id(
    repository: MagicMock, update: DatabaseUpdate
) -> None:
    run(update=update)

    repository.update.assert_called_once_with(
        target=TARGET, uid=UID, values=NEW_VALUES, cluster_state_id=SNAPSHOT.cluster_state_id
    )


def test_execute_waits_for_active_after_the_put(
    repository: MagicMock, active_waiter: MagicMock, update: DatabaseUpdate
) -> None:
    steps: MagicMock = MagicMock()
    steps.attach_mock(mock=repository.update, attribute="update")
    steps.attach_mock(mock=active_waiter.wait, attribute="wait")

    run(update=update)

    assert steps.mock_calls == [
        call.update(target=TARGET, uid=UID, values=NEW_VALUES, cluster_state_id=SNAPSHOT.cluster_state_id),
        call.wait(target=TARGET, uid=UID),
    ]


def test_execute_refuses_a_field_missing_from_the_snapshot(
    repository: MagicMock, update: DatabaseUpdate
) -> None:
    repository.get_fields.side_effect = [DatabaseFields(values={"memory_size": 100}, cluster_state_id=1)]

    with pytest.raises(expected_exception=UnrestorableFieldsError):
        run(update=update)

    repository.update.assert_not_called()


def test_compensate_puts_the_snapshot_back_with_the_current_state_id(
    repository: MagicMock, update: DatabaseUpdate
) -> None:
    repository.get_fields.side_effect = [CURRENT]

    update.compensate(step_input=STEP_INPUT, result=SNAPSHOT)

    repository.update.assert_called_once_with(
        target=TARGET, uid=UID, values=OLD_VALUES, cluster_state_id=CURRENT.cluster_state_id
    )


def test_find_outcome_keeps_the_snapshot_when_the_new_values_are_in_place(
    repository: MagicMock, update: DatabaseUpdate
) -> None:
    repository.get_fields.side_effect = [CURRENT]

    assert update.find_outcome(step_input=STEP_INPUT, kept=SNAPSHOT) == SNAPSHOT


def test_find_outcome_returns_none_when_the_old_values_are_still_there(
    repository: MagicMock, update: DatabaseUpdate
) -> None:
    repository.get_fields.side_effect = [SNAPSHOT]

    assert update.find_outcome(step_input=STEP_INPUT, kept=SNAPSHOT) is None


def test_find_outcome_without_a_kept_snapshot_asks_the_cluster_nothing(
    repository: MagicMock, update: DatabaseUpdate
) -> None:
    assert update.find_outcome(step_input=STEP_INPUT, kept=None) is None

    repository.get_fields.assert_not_called()


def test_find_outcome_waits_for_active_before_reporting_the_update_done(
    repository: MagicMock, active_waiter: MagicMock, update: DatabaseUpdate
) -> None:
    repository.get_fields.side_effect = [CURRENT]

    update.find_outcome(step_input=STEP_INPUT, kept=SNAPSHOT)

    active_waiter.wait.assert_called_once_with(target=TARGET, uid=UID)
