from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError
from redis_enterprise_services.resources.models import ClusterObject, CreatedResource, DeletionStarted
from redis_enterprise_services.resources.rest_resource_endpoint import RestResourceEndpoint

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


def endpoint_answering(*, answer: JsonValue) -> RestResourceEndpoint:
    cluster_api_caller: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    cluster_api_caller.send.return_value = SuccessfulClusterResponse(body=answer, cluster_state_id=None)
    settings: Settings = load_settings()
    return RestResourceEndpoint(
        cluster_api_caller=cluster_api_caller,
        settings=settings.user,
        cluster_api_settings=settings.cluster_api,
    )


ANSWER: dict[str, JsonValue] = {"uid": 6, "name": "app-user", "role_uids": [5], "action_uid": "c7d4bccf"}


def test_start_creation_keeps_the_whole_answer() -> None:
    endpoint: RestResourceEndpoint = endpoint_answering(answer=ANSWER)

    created: CreatedResource = endpoint.start_creation(target=TARGET, creation_body={"name": "app-user"})

    assert created == CreatedResource(uid=6, name="app-user", action_uid="c7d4bccf", fields=ANSWER)


def test_an_unreadable_answer_names_the_fields_without_their_values() -> None:
    endpoint: RestResourceEndpoint = endpoint_answering(
        answer={"name": "db1", "authentication_redis_pass": "s3cret"}
    )

    with pytest.raises(expected_exception=UnreadableClusterResponseError) as unreadable:
        endpoint.start_creation(target=TARGET, creation_body={"name": "db1"})

    assert "s3cret" not in f"{unreadable.value.message} {unreadable.value.__cause__}"


def test_a_list_returns_every_object_in_full() -> None:
    database: dict[str, JsonValue] = {"uid": 1, "name": "orders", "status": "active", "port": 12000}
    endpoint: RestResourceEndpoint = endpoint_answering(answer=[database])

    assert endpoint.list_objects(target=TARGET) == [ClusterObject(uid=1, name="orders", fields=database)]


def test_a_deletion_returns_the_whole_answer() -> None:
    endpoint: RestResourceEndpoint = endpoint_answering(answer={"action_uid": "c7d4bccf"})

    assert endpoint.start_deletion(target=TARGET, uid=6) == DeletionStarted(
        action_uid="c7d4bccf", fields={"action_uid": "c7d4bccf"}
    )
