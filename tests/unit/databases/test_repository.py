from unittest.mock import create_autospec

from pydantic import JsonValue, SecretStr

from redis_enterprise_services.config.database_tag import DatabaseTag
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.databases.repository import DatabaseRepository
from redis_enterprise_services.resources.resource_calls import ResourceCalls


def test_the_creation_body_has_the_default_user_secret_the_default_tags_and_only_set_fields() -> None:
    repository: DatabaseRepository = DatabaseRepository(
        endpoint=create_autospec(spec=ResourceCalls, instance=True),
        default_user_password=SecretStr("s3cret"),
        default_tags=[DatabaseTag(key="team", value="core")],
    )

    body: dict[str, JsonValue] = repository.creation_body(
        spec=NewDatabase(name="orders", memory_size=104857600, data_persistence="aof")
    )

    assert body == {
        "name": "orders",
        "memory_size": 104857600,
        "data_persistence": "aof",
        "default_user": True,
        "tags": [{"key": "team", "value": "core"}],
        "authentication_redis_pass": "s3cret",
    }
