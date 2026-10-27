from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.edge.models import ClusterCredentials, ClusterResponse
from redis_enterprise_services.exceptions.cluster import UnreadableAnswerError
from redis_enterprise_services.resources.endpoint import ResourceEndpoint
from redis_enterprise_services.resources.models import CreatedResource, NamedResource

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
USERS: list[JsonValue] = [
    {"uid": 1, "name": "Administrator", "role_uids": [1], "email": "admin@redis.local"},
    {"uid": 6, "name": "app-user", "role_uids": [5], "email": ""},
]


def endpoint_answering(*, answer: JsonValue) -> ResourceEndpoint:
    api: MagicMock = create_autospec(spec=ClusterApi, instance=True)
    api.send.return_value = ClusterResponse(status_code=200, headers={}, body=answer, cluster_state_id=None)
    settings: Settings = load_settings()
    return ResourceEndpoint(api=api, settings=settings.user, cluster=settings.cluster)


@pytest.fixture
def endpoint() -> ResourceEndpoint:
    return endpoint_answering(answer=USERS)


def test_find_by_name_returns_the_resource_with_that_name(endpoint: ResourceEndpoint) -> None:
    assert endpoint.find_by_name(target=TARGET, name="app-user") == [NamedResource(uid=6, name="app-user")]


@pytest.mark.parametrize(argnames="name", argvalues=["no-such-user", "APP-USER"])
def test_find_by_name_returns_nothing_without_an_exact_match(endpoint: ResourceEndpoint, name: str) -> None:
    assert endpoint.find_by_name(target=TARGET, name=name) == []


def test_create_reads_the_uid_name_and_action_uid_of_the_answer() -> None:
    endpoint: ResourceEndpoint = endpoint_answering(
        answer={"uid": 6, "name": "app-user", "role_uids": [5], "action_uid": "c7d4bccf"}
    )

    created: CreatedResource = endpoint.create(target=TARGET, body={"name": "app-user"})

    assert created == CreatedResource(uid=6, name="app-user", action_uid="c7d4bccf")


def test_create_reports_an_unreadable_answer_as_its_own_error() -> None:
    endpoint: ResourceEndpoint = endpoint_answering(answer={"name": "app-user"})

    with pytest.raises(expected_exception=UnreadableAnswerError):
        endpoint.create(target=TARGET, body={"name": "app-user"})


def test_an_unreadable_answer_names_the_fields_without_their_values() -> None:
    endpoint: ResourceEndpoint = endpoint_answering(
        answer={"name": "db1", "authentication_redis_pass": "s3cret"}
    )

    with pytest.raises(expected_exception=UnreadableAnswerError) as unreadable:
        endpoint.create(target=TARGET, body={"name": "db1"})

    assert "s3cret" not in f"{unreadable.value.message} {unreadable.value.__cause__}"


def test_find_by_name_reports_an_unreadable_list_without_its_values() -> None:
    endpoint: ResourceEndpoint = endpoint_answering(
        answer=[{"name": "db1", "authentication_redis_pass": "s3cret"}]
    )

    with pytest.raises(expected_exception=UnreadableAnswerError) as unreadable:
        endpoint.find_by_name(target=TARGET, name="db1")

    assert "s3cret" not in f"{unreadable.value.message} {unreadable.value.__cause__}"
