from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError
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
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.return_value = SuccessfulClusterResponse(body=answer, cluster_state_id=None)
    settings: Settings = load_settings()
    return ResourceEndpoint(api=api, settings=settings.user, cluster_api=settings.cluster_api)


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

    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        endpoint.create(target=TARGET, body={"name": "app-user"})


def test_an_unreadable_answer_names_the_fields_without_their_values() -> None:
    endpoint: ResourceEndpoint = endpoint_answering(
        answer={"name": "db1", "authentication_redis_pass": "s3cret"}
    )

    with pytest.raises(expected_exception=UnreadableClusterResponseError) as unreadable:
        endpoint.create(target=TARGET, body={"name": "db1"})

    assert "s3cret" not in f"{unreadable.value.message} {unreadable.value.__cause__}"


def test_find_by_name_reports_an_unreadable_list_without_its_values() -> None:
    endpoint: ResourceEndpoint = endpoint_answering(
        answer=[{"name": "db1", "authentication_redis_pass": "s3cret"}]
    )

    with pytest.raises(expected_exception=UnreadableClusterResponseError) as unreadable:
        endpoint.find_by_name(target=TARGET, name="db1")

    assert "s3cret" not in f"{unreadable.value.message} {unreadable.value.__cause__}"


def test_the_database_list_asks_only_for_the_configured_fields() -> None:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.return_value = SuccessfulClusterResponse(body=[], cluster_state_id=None)
    settings: Settings = load_settings()

    ResourceEndpoint(api=api, settings=settings.database, cluster_api=settings.cluster_api).find_by_name(
        target=TARGET, name="orders"
    )

    assert api.send.call_args.kwargs["query"] == "fields=uid,name"
