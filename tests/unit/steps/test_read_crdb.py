from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_target_resolver import ConfiguredCredentialsTargetResolver
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.crdbs.models import Crdb
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.exceptions.cluster import IncompleteClusterObjectError
from redis_enterprise_services.steps.read_crdb import CrdbConfigSnapshot, ReadCrdbInput, ReadCrdbStep

SENT: dict[str, JsonValue] = {
    "name": "orders",
    "replication": False,
    "tags": [{"key": "owner", "value": "team-a"}],
    "authentication_redis_pass": "secret-pass",
}


SENT_SETTINGS: CrdbCreationSettings = CrdbCreationSettings(
    causal_consistency=False, encryption=False, compression=3
)
STORED_SETTINGS: dict[str, JsonValue] = {"causal_consistency": False, "encryption": False, "compression": 3}


def crdb_with(*, default_db_config: dict[str, JsonValue], settings: dict[str, JsonValue]) -> Crdb:
    return Crdb.model_validate(
        obj={
            "guid": "g",
            "name": "orders",
            "default_db_config": default_db_config,
            "causal_consistency": settings["causal_consistency"],
            "encryption": settings["encryption"],
            "instances": [
                {
                    "id": 1,
                    "cluster": {"url": "https://cluster-a:9443"},
                    "compression": settings["compression"],
                }
            ],
        }
    )


def read_with(
    *, stored: dict[str, JsonValue], settings: dict[str, JsonValue] = STORED_SETTINGS
) -> CrdbConfigSnapshot:
    repository: MagicMock = create_autospec(spec=CrdbRepository, instance=True)
    repository.read.return_value = crdb_with(default_db_config=stored, settings=settings)
    kept: list[CrdbConfigSnapshot] = []
    ReadCrdbStep(
        repository=repository,
        target_resolver=ConfiguredCredentialsTargetResolver(
            credentials_by_api_url={
                "https://cluster-a:9443": ClusterCredentials(username="admin", password=SecretStr("secret"))
            },
        ),
        secret_fields=frozenset({"authentication_redis_pass"}),
        order_insensitive_fields=frozenset(),
        cluster_added_item_fields=frozenset({"isSystem"}),
    ).execute(
        step_input=ReadCrdbInput(
            coordinator=ClusterAddress(network="net-a", api_url="https://cluster-a:9443"),
            guid="g",
            expected_config=SENT,
            expected_settings=SENT_SETTINGS,
        ),
        keep_result=lambda result: kept.append(result),
    )
    return kept[0]


def test_tags_the_cluster_marked_as_not_system_still_match_what_was_sent() -> None:
    stored: dict[str, JsonValue] = {
        **SENT,
        "tags": [{"isSystem": False, "key": "owner", "value": "team-a"}],
        "port": 12000,
    }

    assert read_with(stored=stored).default_db_config["tags"] == stored["tags"]


def test_the_crdb_settings_are_kept_without_secrets() -> None:
    assert "authentication_redis_pass" not in read_with(stored={**SENT, "port": 12000}).default_db_config


def test_a_sent_field_the_crdb_does_not_hold_is_an_incomplete_crdb() -> None:
    with pytest.raises(expected_exception=IncompleteClusterObjectError):
        read_with(stored={key: value for key, value in SENT.items() if key != "replication"})


@pytest.mark.parametrize(
    argnames="changed",
    argvalues=[{"causal_consistency": True}, {"encryption": None}, {"compression": 6}],
)
def test_a_sync_setting_the_crdb_does_not_hold_as_sent_is_an_incomplete_crdb(
    changed: dict[str, JsonValue],
) -> None:
    with pytest.raises(expected_exception=IncompleteClusterObjectError):
        read_with(stored=SENT, settings={**STORED_SETTINGS, **changed})
