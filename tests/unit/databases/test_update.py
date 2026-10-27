from unittest.mock import MagicMock, call, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.databases.repository import DatabaseRepository
from redis_enterprise_services.databases.update import DatabaseUpdate
from redis_enterprise_services.edge.models import ClusterCredentials, ClusterTarget
from redis_enterprise_services.exceptions.cluster import UnrestorableFieldsError

UID: int = 1
TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
NEW_VALUES: dict[str, JsonValue] = {"memory_size": 200, "eviction_policy": "noeviction"}
OLD_VALUES: dict[str, JsonValue] = {"memory_size": 100, "eviction_policy": "volatile-lru"}
SNAPSHOT_STATE_ID: int = 7
CURRENT_STATE_ID: int = 9


@pytest.fixture
def repository() -> MagicMock:
    repository: MagicMock = create_autospec(spec=DatabaseRepository, instance=True)
    repository.get_fields.side_effect = [
        DatabaseFields(values=OLD_VALUES, cluster_state_id=SNAPSHOT_STATE_ID),
        DatabaseFields(values=NEW_VALUES, cluster_state_id=CURRENT_STATE_ID),
    ]
    return repository


@pytest.fixture
def update(repository: MagicMock) -> DatabaseUpdate:
    return DatabaseUpdate(repository=repository, target=TARGET, uid=UID, values=NEW_VALUES)


def test_execute_snapshots_only_the_fields_it_changes(repository: MagicMock, update: DatabaseUpdate) -> None:
    update.execute()

    repository.get_fields.assert_called_once_with(target=TARGET, uid=UID, fields=list(NEW_VALUES))


def test_execute_puts_the_new_values_with_the_snapshot_state_id(
    repository: MagicMock, update: DatabaseUpdate
) -> None:
    update.execute()

    repository.update.assert_called_once_with(
        target=TARGET, uid=UID, values=NEW_VALUES, cluster_state_id=SNAPSHOT_STATE_ID
    )


def test_execute_waits_for_active_after_the_put(repository: MagicMock, update: DatabaseUpdate) -> None:
    update.execute()

    assert repository.mock_calls[-2:] == [
        call.update(target=TARGET, uid=UID, values=NEW_VALUES, cluster_state_id=SNAPSHOT_STATE_ID),
        call.wait_until_active(target=TARGET, uid=UID),
    ]


def test_execute_refuses_a_field_missing_from_the_snapshot(repository: MagicMock) -> None:
    repository.get_fields.side_effect = [DatabaseFields(values={"memory_size": 100}, cluster_state_id=1)]
    update: DatabaseUpdate = DatabaseUpdate(repository=repository, target=TARGET, uid=UID, values=NEW_VALUES)

    with pytest.raises(expected_exception=UnrestorableFieldsError):
        update.execute()

    repository.update.assert_not_called()


def test_compensate_puts_the_snapshot_back_with_the_current_state_id(
    repository: MagicMock, update: DatabaseUpdate
) -> None:
    update.execute()
    repository.update.reset_mock()

    update.compensate()

    repository.update.assert_called_once_with(
        target=TARGET, uid=UID, values=OLD_VALUES, cluster_state_id=CURRENT_STATE_ID
    )


def test_compensate_without_a_snapshot_changes_nothing(repository: MagicMock, update: DatabaseUpdate) -> None:
    update.compensate()

    repository.update.assert_not_called()
