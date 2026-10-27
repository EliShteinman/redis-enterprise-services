from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.edge.models import ClusterCredentials, ClusterTarget
from redis_enterprise_services.exceptions.cluster import ClusterActionTimeoutError
from redis_enterprise_services.users.create import UserCreate
from redis_enterprise_services.users.models import CreatedUser, NewUser, User
from redis_enterprise_services.users.repository import UserRepository

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
NEW_USER: NewUser = NewUser(name="app-user", password=SecretStr("Aa1!password"), role_uids=[5])
CREATED: User = User(uid=6, name="app-user", role_uids=[5])
ACTION_UID: str = "c7d4bccf-9462-4924-8c8f-345bd94fe89c"


@pytest.fixture
def repository() -> MagicMock:
    repository: MagicMock = create_autospec(spec=UserRepository, instance=True)
    repository.create.return_value = CreatedUser(user=CREATED, action_uid=ACTION_UID)
    return repository


@pytest.fixture
def step(repository: MagicMock) -> UserCreate:
    return UserCreate(repository=repository, target=TARGET, user=NEW_USER)


def test_execute_keeps_the_created_user(step: UserCreate) -> None:
    step.execute()

    assert step.created == CREATED


def test_compensate_deletes_the_created_user(repository: MagicMock, step: UserCreate) -> None:
    step.execute()

    step.compensate()

    repository.delete.assert_called_once_with(target=TARGET, uid=CREATED.uid)


def test_compensate_without_a_created_user_deletes_nothing(repository: MagicMock, step: UserCreate) -> None:
    step.compensate()

    repository.delete.assert_not_called()


def test_a_user_whose_action_did_not_finish_is_still_compensated(
    repository: MagicMock, step: UserCreate
) -> None:
    repository.wait_for_action.side_effect = ClusterActionTimeoutError(message="action did not complete")
    with pytest.raises(expected_exception=ClusterActionTimeoutError):
        step.execute()

    step.compensate()

    repository.delete.assert_called_once_with(target=TARGET, uid=CREATED.uid)
