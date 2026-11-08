from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.resources.rest_resource_endpoint import RestResourceEndpoint

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
USERS: list[JsonValue] = [
    {"uid": 1, "name": "Administrator", "role_uids": [1], "email": "admin@redis.local"},
    {"uid": 6, "name": "app-user", "role_uids": [5], "email": ""},
]


def endpoint_answering(*, answer: JsonValue) -> RestResourceEndpoint:
    cluster_api_caller: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    cluster_api_caller.send.return_value = SuccessfulClusterResponse(body=answer, cluster_state_id=None)
    settings: Settings = load_settings()
    return RestResourceEndpoint(
        cluster_api_caller=cluster_api_caller,
        settings=settings.user,
        cluster_api_settings=settings.cluster_api,
    )


@pytest.fixture
def endpoint() -> RestResourceEndpoint:
    return endpoint_answering(answer=USERS)


def test_find_by_name_returns_the_resource_with_that_name(endpoint: RestResourceEndpoint) -> None:
    assert endpoint.find_by_name(target=TARGET, name="app-user") == [NamedResource(uid=6, name="app-user")]


@pytest.mark.parametrize(argnames="name", argvalues=["no-such-user", "APP-USER"])
def test_find_by_name_returns_nothing_without_an_exact_match(
    endpoint: RestResourceEndpoint, name: str
) -> None:
    assert endpoint.find_by_name(target=TARGET, name=name) == []


def test_create_reads_the_uid_name_and_action_uid_of_the_answer() -> None:
    endpoint: RestResourceEndpoint = endpoint_answering(
        answer={"uid": 6, "name": "app-user", "role_uids": [5], "action_uid": "c7d4bccf"}
    )

    created: CreatedResource = endpoint.start_creation(target=TARGET, body={"name": "app-user"})

    assert created == CreatedResource(uid=6, name="app-user", action_uid="c7d4bccf")


def test_create_raises_unreadable_response_for_an_answer_without_a_uid() -> None:
    endpoint: RestResourceEndpoint = endpoint_answering(answer={"name": "app-user"})

    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        endpoint.start_creation(target=TARGET, body={"name": "app-user"})


def test_an_unreadable_answer_names_the_fields_without_their_values() -> None:
    endpoint: RestResourceEndpoint = endpoint_answering(
        answer={"name": "db1", "authentication_redis_pass": "s3cret"}
    )

    with pytest.raises(expected_exception=UnreadableClusterResponseError) as unreadable:
        endpoint.start_creation(target=TARGET, body={"name": "db1"})

    assert "s3cret" not in f"{unreadable.value.message} {unreadable.value.__cause__}"


def test_find_by_name_reports_an_unreadable_list_without_its_values() -> None:
    endpoint: RestResourceEndpoint = endpoint_answering(
        answer=[{"name": "db1", "authentication_redis_pass": "s3cret"}]
    )

    with pytest.raises(expected_exception=UnreadableClusterResponseError) as unreadable:
        endpoint.find_by_name(target=TARGET, name="db1")

    assert "s3cret" not in f"{unreadable.value.message} {unreadable.value.__cause__}"


def test_the_database_list_asks_only_for_the_configured_fields() -> None:
    cluster_api_caller: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    cluster_api_caller.send.return_value = SuccessfulClusterResponse(body=[], cluster_state_id=None)
    settings: Settings = load_settings()

    RestResourceEndpoint(
        cluster_api_caller=cluster_api_caller,
        settings=settings.database,
        cluster_api_settings=settings.cluster_api,
    ).find_by_name(target=TARGET, name="orders")

    assert cluster_api_caller.send.call_args.kwargs["query_string"] == "fields=uid,name"
