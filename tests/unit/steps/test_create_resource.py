from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.edge.models import ClusterCredentials
from redis_enterprise_services.exceptions.cluster import ClusterActionTimeoutError, ClusterRequestError
from redis_enterprise_services.resources.action_completion import ActionCompletionWaiter
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.steps.create_resource import CreateResourceStep
from redis_enterprise_services.users.models import NewUser
from redis_enterprise_services.users.repository import UserRepository

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
SPEC: NewUser = NewUser(name="app-user", password="Aa1!password", role_uids=[5])
CREATED: CreatedResource = CreatedResource(uid=6, name="app-user", action_uid="c7d4bccf")
DELETE_ACTION_UID: str = "e85d7b88"


@pytest.fixture
def repository() -> MagicMock:
    repository: MagicMock = create_autospec(spec=UserRepository, instance=True)
    repository.create.return_value = CREATED
    repository.delete.return_value = DELETE_ACTION_UID
    return repository


@pytest.fixture
def waiter() -> MagicMock:
    return create_autospec(spec=ActionCompletionWaiter, instance=True)


@pytest.fixture
def step(repository: MagicMock, waiter: MagicMock) -> CreateResourceStep[NewUser]:
    return CreateResourceStep(repository=repository, waiter=waiter, target=TARGET, spec=SPEC)


def test_execute_keeps_the_created_resource(step: CreateResourceStep[NewUser]) -> None:
    step.execute()

    assert step.created == CREATED


def test_execute_waits_until_the_resource_is_created(
    waiter: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    step.execute()

    waiter.wait_created.assert_called_once_with(target=TARGET, resource=CREATED)


def test_compensate_deletes_the_created_resource(
    repository: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    step.execute()

    step.compensate()

    repository.delete.assert_called_once_with(target=TARGET, uid=CREATED.uid)


def test_compensate_waits_until_the_resource_is_deleted(
    waiter: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    step.execute()

    step.compensate()

    waiter.wait_deleted.assert_called_once_with(target=TARGET, uid=CREATED.uid, action_uid=DELETE_ACTION_UID)


def test_compensate_without_a_created_resource_deletes_nothing(
    repository: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    step.compensate()

    repository.delete.assert_not_called()


def test_a_resource_whose_creation_did_not_finish_is_still_compensated(
    repository: MagicMock, waiter: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    waiter.wait_created.side_effect = ClusterActionTimeoutError(message="action did not complete")
    with pytest.raises(expected_exception=ClusterActionTimeoutError):
        step.execute()

    step.compensate()

    repository.delete.assert_called_once_with(target=TARGET, uid=CREATED.uid)


def test_compensate_accepts_a_resource_that_is_already_gone(
    repository: MagicMock, step: CreateResourceStep[NewUser]
) -> None:
    repository.delete.side_effect = ClusterRequestError(
        message="cluster answered 404", cluster_status_code=404, error_code="user_not_exist"
    )
    step.execute()

    step.compensate()
