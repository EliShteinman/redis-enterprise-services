from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.crdbs.creation_body import CrdbCreationBody, crdb_creation_body
from redis_enterprise_services.crdbs.models import Crdb

CREDENTIALS: ClusterCredentials = ClusterCredentials(username="admin", password=SecretStr("secret"))
SETTINGS: CrdbCreationSettings = CrdbCreationSettings(
    causal_consistency=False, encryption=False, compression=3
)
MEMBERS: list[ClusterTarget] = [
    ClusterTarget(network="net-a", api_url="https://cluster-a.net-a:9443", credentials=CREDENTIALS),
    ClusterTarget(network="net-a", api_url="https://cluster-b.net-a:9443", credentials=CREDENTIALS),
]


def test_each_member_is_an_instance_named_by_the_host_of_its_api_url() -> None:
    body: CrdbCreationBody = crdb_creation_body(
        name="orders", default_db_config={}, members=MEMBERS, settings=SETTINGS
    )

    assert [instance.cluster.name for instance in body.instances] == ["cluster-a.net-a", "cluster-b.net-a"]


def test_the_database_settings_go_whole_into_default_db_config() -> None:
    settings: dict[str, JsonValue] = {"name": "orders", "memory_size": 1, "replication": False}

    body: CrdbCreationBody = crdb_creation_body(
        name="orders", default_db_config=settings, members=MEMBERS, settings=SETTINGS
    )

    assert body.default_db_config == settings


def test_the_local_instance_is_found_by_the_cluster_api_url() -> None:
    crdb: Crdb = Crdb.model_validate(
        obj={
            "guid": "g",
            "name": "orders",
            "default_db_config": {},
            "instances": [
                {"id": 1, "cluster": {"url": "https://cluster-a.net-a:9443"}, "db_uid": "7"},
                {"id": 2, "cluster": {"url": "https://cluster-b.net-a:9443"}},
            ],
        }
    )

    assert crdb.instance_on(api_url="https://cluster-a.net-a:9443") == crdb.instances[0]


def test_every_instance_carries_the_configured_compression_explicitly() -> None:
    body: CrdbCreationBody = crdb_creation_body(
        name="orders", default_db_config={}, members=MEMBERS, settings=SETTINGS
    )

    assert [instance.compression for instance in body.instances] == [3, 3]
