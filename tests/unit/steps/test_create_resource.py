from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.credentials import SharedCredentialsProvider
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.connection.models import ClusterCredentials
from redis_enterprise_services.exceptions.cluster import (
    AmbiguousResourceError,
    ClusterActionFailedError,
    ClusterActionTimeoutError,
    ClusterRequestError,
)
from redis_enterprise_services.resources.completion import CompletionWaiter
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput, NamedResource
from redis_enterprise_services.resources.repository import ResourceRepository
from redis_enterprise_services.steps.create_resource import CreateResourceStep
from redis_enterprise_services.users.models import NewUser

CREDENTIALS: ClusterCredentials = ClusterCredentials(username="admin", password=SecretStr("secret"))
ADDRESS: ClusterAddress = ClusterAddress(network="local", api_url="https://cluster.local:9443")
TARGET: ClusterTarget = ClusterTarget(
    network=ADDRESS.network, api_url=ADDRESS.api_url, credentials=CREDENTIALS
)
SPEC: NewUser = NewUser(name="app-user", password="Aa1!password", role_uids=[5])
STEP_INPUT: CreateResourceInput[NewUser] = CreateResourceInput(cluster=ADDRESS, spec=SPEC)
CREATED: CreatedResource = CreatedResource(uid=6, name="app-user", action_uid="c7d4bccf")
DELETE_ACTION_UID: str = "e85d7b88"


def ignore_found(*, result: CreatedResource) -> None:
    pass


@pytest.fixture
def repository() -> MagicMock:
    repository: MagicMock = create_autospec(spec=ResourceRepository, instance=True)
    repository.create.return_value = CREATED
    repository.delete.return_value = DELETE_ACTION_UID
    return repository


@pytest.fixture
def waiter() -> MagicMock:
    return create_autospec(spec=CompletionWaiter, instance=True)


@pytest.fixture
def step(repository: MagicMock, waiter: MagicMock) -> CreateResourceStep[NewUser]:
    return CreateResourceStep(
        repository=repository, waiter=waiter, credentials=SharedCredentialsProvider(credentials=CREDENTIALS)
    )


def test_execute_hands_the_created_resource_to_the_saga(step: CreateResourceStep[NewUser]) -> None:
    kept: list[CreatedResource] = []

    step.execute(step_input=STEP_INPUT, keep_result=lambda result: kept.append(result))

    assert kept == [CREATED]


def test_execute_waits_until_the_resource_is_created(
    waiter: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    step.execute(step_input=STEP_INPUT, keep_result=lambda result: None)

    waiter.wait_created.assert_called_once_with(target=TARGET, resource=CREATED)


def test_the_saga_has_the_resource_even_when_waiting_for_it_fails(
    waiter: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    waiter.wait_created.side_effect = ClusterActionTimeoutError(message="action did not complete")
    kept: list[CreatedResource] = []

    with pytest.raises(expected_exception=ClusterActionTimeoutError):
        step.execute(step_input=STEP_INPUT, keep_result=lambda result: kept.append(result))

    assert kept == [CREATED]


def test_compensate_deletes_the_given_resource(
    repository: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    step.compensate(step_input=STEP_INPUT, result=CREATED)

    repository.delete.assert_called_once_with(target=TARGET, uid=CREATED.uid)


def test_compensate_waits_until_the_resource_is_deleted(
    waiter: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    step.compensate(step_input=STEP_INPUT, result=CREATED)

    waiter.wait_deleted.assert_called_once_with(target=TARGET, uid=CREATED.uid, action_uid=DELETE_ACTION_UID)


def test_compensate_accepts_a_resource_that_is_already_gone(
    repository: MagicMock, waiter: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    repository.delete.side_effect = ClusterRequestError(
        message="cluster answered 404", cluster_status_code=404, error_code="user_not_exist"
    )

    step.compensate(step_input=STEP_INPUT, result=CREATED)

    waiter.wait_deleted.assert_not_called()


def test_compensate_raises_any_other_cluster_error(
    repository: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    repository.delete.side_effect = ClusterRequestError(
        message="cluster answered 406", cluster_status_code=406, error_code="role_in_use"
    )

    with pytest.raises(expected_exception=ClusterRequestError):
        step.compensate(step_input=STEP_INPUT, result=CREATED)


def test_find_outcome_finds_the_resource_by_the_spec_name(
    repository: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    repository.find_by_name.return_value = [NamedResource(uid=6, name="app-user")]

    found: CreatedResource | None = step.find_outcome(
        step_input=STEP_INPUT, kept=None, keep_found=ignore_found
    )

    assert found == CreatedResource(uid=6, name="app-user", action_uid=None)


def test_find_outcome_keeps_the_resource_found_by_name_even_when_its_creation_failed(
    repository: MagicMock, waiter: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    repository.find_by_name.return_value = [NamedResource(uid=6, name="app-user")]
    waiter.wait_created.side_effect = ClusterActionFailedError(message="creation failed")
    kept: list[CreatedResource] = []

    with pytest.raises(expected_exception=ClusterActionFailedError):
        step.find_outcome(step_input=STEP_INPUT, kept=None, keep_found=lambda result: kept.append(result))

    assert kept == [CreatedResource(uid=6, name="app-user", action_uid=None)]


def test_find_outcome_returns_none_when_the_resource_does_not_exist(
    repository: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    repository.find_by_name.return_value = []

    assert step.find_outcome(step_input=STEP_INPUT, kept=None, keep_found=ignore_found) is None


def test_find_outcome_refuses_more_than_one_resource_with_the_name(
    repository: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    repository.find_by_name.return_value = [
        NamedResource(uid=6, name="app-user"),
        NamedResource(uid=9, name="app-user"),
    ]

    with pytest.raises(expected_exception=AmbiguousResourceError):
        step.find_outcome(step_input=STEP_INPUT, kept=None, keep_found=ignore_found)


def test_find_outcome_trusts_what_was_kept_without_searching(
    repository: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    assert step.find_outcome(step_input=STEP_INPUT, kept=CREATED, keep_found=ignore_found) == CREATED

    repository.find_by_name.assert_not_called()


def test_find_outcome_waits_until_the_found_resource_is_created(
    waiter: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    step.find_outcome(step_input=STEP_INPUT, kept=CREATED, keep_found=ignore_found)

    waiter.wait_created.assert_called_once_with(target=TARGET, resource=CREATED)
