from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbSettings
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.crdbs.models import Crdb
from redis_enterprise_services.crdbs.rest_crdb_repository import RestCrdbRepository
from redis_enterprise_services.databases.database_creation_body_builder import DatabaseCreationBodyBuilder
from redis_enterprise_services.exceptions.cluster import (
    CrdbTaskIdMismatchError,
    UnreadableClusterResponseError,
)

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster-a:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


@pytest.fixture
def crdb_settings(config_dir: Path) -> CrdbSettings:
    return load_settings(config_dir=config_dir).crdb


def repository_answering(*, body: JsonValue, settings: CrdbSettings) -> RestCrdbRepository:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.return_value = SuccessfulClusterResponse(body=body, cluster_state_id=None)
    return RestCrdbRepository(
        cluster_api_caller=api,
        database_body_builder=DatabaseCreationBodyBuilder(
            default_user_password_by_api_url={TARGET.api_url: SecretStr("unused")}, default_tags=[]
        ),
        settings=settings,
    )


def test_the_crdb_list_is_read_from_its_wrapping_field(crdb_settings: CrdbSettings) -> None:
    listed: list[Crdb] = repository_answering(
        body={"crdbs": [{"guid": "g", "name": "orders", "default_db_config": {}, "instances": []}]},
        settings=crdb_settings,
    ).list_crdbs(target=TARGET)

    assert [crdb.name for crdb in listed] == ["orders"]


@pytest.mark.parametrize(argnames="body", argvalues=[[], {"other": []}, {"crdbs": [{"name": 1}]}])
def test_a_crdb_list_that_cannot_be_read_is_an_unreadable_answer(
    body: JsonValue, crdb_settings: CrdbSettings
) -> None:
    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        repository_answering(body=body, settings=crdb_settings).list_crdbs(target=TARGET)


def test_the_crdb_names_are_read_even_when_a_crdb_has_an_unexpected_shape(
    crdb_settings: CrdbSettings,
) -> None:
    names: set[str] = repository_answering(
        body={"crdbs": [{"name": "orders", "instances": "odd"}]}, settings=crdb_settings
    ).list_crdb_names(target=TARGET)

    assert names == {"orders"}


def test_a_crdb_whose_instance_url_is_not_a_cluster_address_is_an_unreadable_answer(
    crdb_settings: CrdbSettings,
) -> None:
    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        repository_answering(
            body={
                "guid": "g",
                "name": "orders",
                "default_db_config": {},
                "instances": [{"id": 1, "cluster": {"url": "cluster-a:9443"}}],
            },
            settings=crdb_settings,
        ).read(target=TARGET, guid="g")


def test_a_task_started_under_another_id_is_a_task_id_mismatch(crdb_settings: CrdbSettings) -> None:
    with pytest.raises(expected_exception=CrdbTaskIdMismatchError):
        repository_answering(
            body={"id": "another", "status": "queued"}, settings=crdb_settings
        ).start_deletion(target=TARGET, guid="g", task_id="ours")


def test_a_task_started_under_our_id_in_upper_case_is_accepted(crdb_settings: CrdbSettings) -> None:
    repository_answering(
        body={"id": "16A0C036-6D3A-4AD0-9352-A56108EA8138", "status": "queued"}, settings=crdb_settings
    ).start_deletion(target=TARGET, guid="g", task_id="16a0c036-6d3a-4ad0-9352-a56108ea8138")
