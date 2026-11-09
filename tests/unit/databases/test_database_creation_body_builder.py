from pydantic import JsonValue, SecretStr

from redis_enterprise_services.config.database_tag import DatabaseTag
from redis_enterprise_services.databases.database_creation_body_builder import DatabaseCreationBodyBuilder
from redis_enterprise_services.databases.new_database import NewDatabase


def test_the_creation_body_has_the_default_user_secret_the_default_tags_and_only_set_fields() -> None:
    body: dict[str, JsonValue] = DatabaseCreationBodyBuilder(
        default_user_password=SecretStr("s3cret"), default_tags=[DatabaseTag(key="team", value="core")]
    ).creation_body(spec=NewDatabase(name="orders", memory_size=104857600, data_persistence="aof"))

    assert body == {
        "name": "orders",
        "memory_size": 104857600,
        "data_persistence": "aof",
        "default_user": True,
        "tags": [{"key": "team", "value": "core"}],
        "authentication_redis_pass": "s3cret",
    }
