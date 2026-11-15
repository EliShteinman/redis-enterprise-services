from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.crdbs.models import Crdb
from redis_enterprise_services.crdbs.rest_crdb_repository import RestCrdbRepository
from redis_enterprise_services.databases.database_creation_body_builder import DatabaseCreationBodyBuilder
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster-a:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


def repository_answering(*, body: JsonValue) -> RestCrdbRepository:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.return_value = SuccessfulClusterResponse(body=body, cluster_state_id=None)
    return RestCrdbRepository(
        cluster_api_caller=api,
        database_body_builder=DatabaseCreationBodyBuilder(
            default_user_password=SecretStr("unused"), default_tags=[]
        ),
        settings=load_settings().crdb,
    )


def test_the_crdb_list_is_read_from_its_wrapping_field() -> None:
    listed: list[Crdb] = repository_answering(
        body={"crdbs": [{"guid": "g", "name": "orders", "default_db_config": {}, "instances": []}]}
    ).list_crdbs(target=TARGET)

    assert [crdb.name for crdb in listed] == ["orders"]


@pytest.mark.parametrize(argnames="body", argvalues=[[], {"other": []}, {"crdbs": [{"name": 1}]}])
def test_a_crdb_list_that_cannot_be_read_is_an_unreadable_answer(body: JsonValue) -> None:
    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        repository_answering(body=body).list_crdbs(target=TARGET)


def test_the_crdb_names_are_read_even_when_a_crdb_has_an_unexpected_shape() -> None:
    names: set[str] = repository_answering(
        body={"crdbs": [{"name": "orders", "instances": "odd"}]}
    ).list_crdb_names(target=TARGET)

    assert names == {"orders"}


def test_a_crdb_whose_instance_url_is_not_a_cluster_address_is_an_unreadable_answer() -> None:
    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        repository_answering(
            body={
                "guid": "g",
                "name": "orders",
                "default_db_config": {},
                "instances": [{"id": 1, "cluster": {"url": "cluster-a:9443"}}],
            }
        ).read(target=TARGET, guid="g")


def test_a_task_started_under_another_id_is_an_unreadable_answer() -> None:
    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        repository_answering(body={"id": "another", "status": "queued"}).start_deletion(
            target=TARGET, guid="g", task_id="ours"
        )
