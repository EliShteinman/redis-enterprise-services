from unittest.mock import MagicMock, call, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_target_resolver import SharedCredentialsTargetResolver
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.databases.database_activation_waiter import DatabaseActivationWaiter
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsRepository
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.exceptions.cluster import UnrestorableFieldsError, UpdateOutcomeUnclearError
from redis_enterprise_services.steps.update_database import UpdateDatabaseInput, UpdateDatabaseStep

UID: int = 1
CREDENTIALS: ClusterCredentials = ClusterCredentials(username="admin", password=SecretStr("secret"))
ADDRESS: ClusterAddress = ClusterAddress(network="local", api_url="https://cluster.local:9443")
TARGET: ClusterTarget = ClusterTarget(
    network=ADDRESS.network, api_url=ADDRESS.api_url, credentials=CREDENTIALS
)
NEW_VALUES: dict[str, JsonValue] = {"memory_size": 200, "eviction_policy": "noeviction"}
OLD_VALUES: dict[str, JsonValue] = {"memory_size": 100, "eviction_policy": "volatile-lru"}
SNAPSHOT: DatabaseFieldsSnapshot = DatabaseFieldsSnapshot(values=OLD_VALUES, cluster_state_id=7)
UPDATED: DatabaseFieldsSnapshot = DatabaseFieldsSnapshot(values=NEW_VALUES, cluster_state_id=9)
STEP_INPUT: UpdateDatabaseInput = UpdateDatabaseInput(cluster=ADDRESS, uid=UID, values=NEW_VALUES)


def ignore_found(*, result: DatabaseFieldsSnapshot) -> None:
    pass


@pytest.fixture
def repository() -> MagicMock:
    repository: MagicMock = create_autospec(spec=DatabaseFieldsRepository, instance=True)
    repository.read.side_effect = [SNAPSHOT, UPDATED]
    return repository


@pytest.fixture
def activation_waiter() -> MagicMock:
    return create_autospec(spec=DatabaseActivationWaiter, instance=True)


@pytest.fixture
def step(repository: MagicMock, activation_waiter: MagicMock) -> UpdateDatabaseStep:
    return UpdateDatabaseStep(
        repository=repository,
        activation_waiter=activation_waiter,
        target_resolver=SharedCredentialsTargetResolver(credentials=CREDENTIALS),
        order_insensitive_fields=frozenset(),
    )


def execute_and_collect_kept(*, step: UpdateDatabaseStep) -> list[DatabaseFieldsSnapshot]:
    kept: list[DatabaseFieldsSnapshot] = []
    step.execute(step_input=STEP_INPUT, keep_result=lambda result: kept.append(result))
    return kept


def test_execute_keeps_only_the_fields_it_changes_from_the_whole_database(
    repository: MagicMock, step: UpdateDatabaseStep
) -> None:
    repository.read.side_effect = [
        DatabaseFieldsSnapshot(values={**OLD_VALUES, "port": 12000, "name": "orders"}, cluster_state_id=7)
    ]

    assert execute_and_collect_kept(step=step) == [SNAPSHOT]


def test_execute_hands_the_snapshot_to_the_saga(step: UpdateDatabaseStep) -> None:
    assert execute_and_collect_kept(step=step) == [SNAPSHOT]


def test_execute_puts_the_new_values_with_the_snapshot_state_id(
    repository: MagicMock, step: UpdateDatabaseStep
) -> None:
    execute_and_collect_kept(step=step)

    repository.update_fields_if_state_unchanged.assert_called_once_with(
        target=TARGET, uid=UID, values=NEW_VALUES, cluster_state_id=SNAPSHOT.cluster_state_id
    )


def test_execute_waits_for_active_after_the_put(
    repository: MagicMock, activation_waiter: MagicMock, step: UpdateDatabaseStep
) -> None:
    call_order: MagicMock = MagicMock()
    call_order.attach_mock(
        mock=repository.update_fields_if_state_unchanged, attribute="update_fields_if_state_unchanged"
    )
    call_order.attach_mock(mock=activation_waiter.wait_until_active, attribute="wait_until_active")

    execute_and_collect_kept(step=step)

    assert call_order.mock_calls == [
        call.update_fields_if_state_unchanged(
            target=TARGET, uid=UID, values=NEW_VALUES, cluster_state_id=SNAPSHOT.cluster_state_id
        ),
        call.wait_until_active(target=TARGET, uid=UID),
    ]


def test_execute_refuses_a_field_missing_from_the_snapshot(
    repository: MagicMock, step: UpdateDatabaseStep
) -> None:
    repository.read.side_effect = [DatabaseFieldsSnapshot(values={"memory_size": 100}, cluster_state_id=1)]

    with pytest.raises(expected_exception=UnrestorableFieldsError):
        execute_and_collect_kept(step=step)

    repository.update_fields_if_state_unchanged.assert_not_called()


def test_compensate_puts_the_snapshot_back_with_the_current_state_id(
    repository: MagicMock, step: UpdateDatabaseStep
) -> None:
    repository.read.side_effect = [UPDATED]

    step.compensate(step_input=STEP_INPUT, result=SNAPSHOT)

    repository.update_fields_if_state_unchanged.assert_called_once_with(
        target=TARGET, uid=UID, values=OLD_VALUES, cluster_state_id=UPDATED.cluster_state_id
    )


def test_find_outcome_returns_the_snapshot_when_the_new_values_are_in_place(
    repository: MagicMock, step: UpdateDatabaseStep
) -> None:
    repository.read.side_effect = [UPDATED]

    assert (
        step.find_outcome(step_input=STEP_INPUT, kept_result=SNAPSHOT, keep_result_if_none_kept=ignore_found)
        == SNAPSHOT
    )


def test_find_outcome_returns_none_when_the_old_values_are_still_there(
    repository: MagicMock, step: UpdateDatabaseStep
) -> None:
    repository.read.side_effect = [SNAPSHOT]

    assert (
        step.find_outcome(step_input=STEP_INPUT, kept_result=SNAPSHOT, keep_result_if_none_kept=ignore_found)
        is None
    )


def test_find_outcome_raises_when_the_database_holds_neither_the_old_nor_the_new_values(
    repository: MagicMock, step: UpdateDatabaseStep
) -> None:
    repository.read.side_effect = [
        DatabaseFieldsSnapshot(
            values={"memory_size": 150, "eviction_policy": "noeviction"}, cluster_state_id=8
        )
    ]

    with pytest.raises(expected_exception=UpdateOutcomeUnclearError):
        step.find_outcome(step_input=STEP_INPUT, kept_result=SNAPSHOT, keep_result_if_none_kept=ignore_found)


def test_find_outcome_without_a_kept_snapshot_asks_the_cluster_nothing(
    repository: MagicMock, step: UpdateDatabaseStep
) -> None:
    assert (
        step.find_outcome(step_input=STEP_INPUT, kept_result=None, keep_result_if_none_kept=ignore_found)
        is None
    )

    repository.read.assert_not_called()


def test_find_outcome_waits_for_active_before_reporting_the_update_done(
    repository: MagicMock, activation_waiter: MagicMock, step: UpdateDatabaseStep
) -> None:
    repository.read.side_effect = [UPDATED]

    step.find_outcome(step_input=STEP_INPUT, kept_result=SNAPSHOT, keep_result_if_none_kept=ignore_found)

    activation_waiter.wait_until_active.assert_called_once_with(target=TARGET, uid=UID)


def test_compensate_does_not_restore_over_a_change_made_after_the_update(
    repository: MagicMock, step: UpdateDatabaseStep
) -> None:
    repository.read.side_effect = [
        DatabaseFieldsSnapshot(
            values={"memory_size": 150, "eviction_policy": "noeviction"}, cluster_state_id=8
        )
    ]

    with pytest.raises(expected_exception=UpdateOutcomeUnclearError):
        step.compensate(step_input=STEP_INPUT, result=SNAPSHOT)


def test_compensate_skips_the_put_when_the_old_values_are_still_there(
    repository: MagicMock, step: UpdateDatabaseStep
) -> None:
    repository.read.side_effect = [SNAPSHOT]

    step.compensate(step_input=STEP_INPUT, result=SNAPSHOT)

    repository.update_fields_if_state_unchanged.assert_not_called()
