from unittest.mock import create_autospec

from pydantic import JsonValue, SecretStr

from redis_enterprise_services.databases.lifecycle import DatabaseLifecycle
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.resources.resource_calls import ResourceCalls


def test_the_creation_body_turns_the_default_user_on_with_the_secret_and_sends_only_set_fields() -> None:
    lifecycle: DatabaseLifecycle = DatabaseLifecycle(
        endpoint=create_autospec(spec=ResourceCalls, instance=True), default_user_password=SecretStr("s3cret")
    )

    body: dict[str, JsonValue] = lifecycle.creation_body(
        spec=NewDatabase(name="orders", memory_size=104857600, data_persistence="aof")
    )

    assert body == {
        "name": "orders",
        "memory_size": 104857600,
        "data_persistence": "aof",
        "default_user": True,
        "authentication_redis_pass": "s3cret",
    }
