from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.edge.models import ClusterCredentials, ClusterResponse
from redis_enterprise_services.users.models import User
from redis_enterprise_services.users.repository import UserRepository

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
USERS: list[JsonValue] = [
    {"uid": 1, "name": "Administrator", "role_uids": [1], "email": "admin@redis.local"},
    {"uid": 6, "name": "app-user", "role_uids": [5], "email": ""},
]


@pytest.fixture
def repository() -> UserRepository:
    api: MagicMock = create_autospec(spec=ClusterApi, instance=True)
    api.send.return_value = ClusterResponse(status_code=200, headers={}, body=USERS, cluster_state_id=None)
    settings: Settings = load_settings()
    return UserRepository(api=api, settings=settings.user, cluster=settings.cluster)


def test_find_by_name_returns_the_user_with_that_name(repository: UserRepository) -> None:
    assert repository.find_by_name(target=TARGET, name="app-user") == User(
        uid=6, name="app-user", role_uids=[5]
    )


@pytest.mark.parametrize(argnames="name", argvalues=["no-such-user", "APP-USER"])
def test_find_by_name_returns_none_without_an_exact_match(repository: UserRepository, name: str) -> None:
    assert repository.find_by_name(target=TARGET, name=name) is None
