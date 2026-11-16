from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.database_tag import DatabaseTag
from redis_enterprise_services.databases.database_creation_body_builder import DatabaseCreationBodyBuilder
from redis_enterprise_services.databases.new_database import NewDatabase

CLUSTER_1: ClusterAddress = ClusterAddress(network="net-a", api_url="https://c1:9443")
CLUSTER_2: ClusterAddress = ClusterAddress(network="net-a", api_url="https://c2:9443")
BUILDER: DatabaseCreationBodyBuilder = DatabaseCreationBodyBuilder(
    default_user_password_by_api_url={
        CLUSTER_1.api_url: SecretStr("c1-s3cret"),
        CLUSTER_2.api_url: SecretStr("c2-s3cret"),
    },
    default_tags=[DatabaseTag(key="team", value="core")],
)
DATABASE: NewDatabase = NewDatabase(name="orders", memory_size=104857600, data_persistence="aof")


def test_the_creation_body_has_the_default_user_secret_the_default_tags_and_only_set_fields() -> None:
    body: dict[str, JsonValue] = BUILDER.creation_body(spec=DATABASE, cluster=CLUSTER_1)

    assert body == {
        "name": "orders",
        "memory_size": 104857600,
        "data_persistence": "aof",
        "default_user": True,
        "tags": [{"key": "team", "value": "core"}],
        "authentication_redis_pass": "c1-s3cret",
    }


def test_the_default_user_password_is_the_one_of_the_cluster_the_database_is_created_on() -> None:
    body: dict[str, JsonValue] = BUILDER.creation_body(spec=DATABASE, cluster=CLUSTER_2)

    assert {"authentication_redis_pass": "c2-s3cret"}.items() <= body.items()
