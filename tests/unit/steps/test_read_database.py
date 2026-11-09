import pytest
from pydantic import JsonValue

from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.steps.read_database import (
    fields_not_holding,
    missing_database_values,
    required_field_names,
)


@pytest.fixture
def settings() -> DatabaseSettings:
    return load_settings().database


@pytest.fixture
def complete(settings: DatabaseSettings) -> dict[str, JsonValue]:
    values: dict[str, JsonValue] = {name: "set" for name in required_field_names(settings=settings)}
    values[settings.endpoints_field] = [{name: "set" for name in settings.endpoint_fields}]
    return values


def test_a_read_database_must_hold_every_creation_field_and_the_configured_extras(
    settings: DatabaseSettings,
) -> None:
    assert required_field_names(settings=settings) == [*NewDatabase.model_fields, *settings.required_fields]


def test_a_complete_database_misses_nothing(
    settings: DatabaseSettings, complete: dict[str, JsonValue]
) -> None:
    assert missing_database_values(values=complete, settings=settings) == []


def test_a_creation_field_without_a_value_is_missing(
    settings: DatabaseSettings, complete: dict[str, JsonValue]
) -> None:
    complete["memory_size"] = None

    assert missing_database_values(values=complete, settings=settings) == ["memory_size"]


def test_a_database_without_endpoints_is_incomplete(
    settings: DatabaseSettings, complete: dict[str, JsonValue]
) -> None:
    complete[settings.endpoints_field] = []

    assert missing_database_values(values=complete, settings=settings) == [settings.endpoints_field]


def test_an_endpoint_without_a_port_is_incomplete(
    settings: DatabaseSettings, complete: dict[str, JsonValue]
) -> None:
    complete[settings.endpoints_field] = [{"dns_name": "d", "addr": ["10.0.0.1"]}]

    assert missing_database_values(values=complete, settings=settings) == [
        f"{settings.endpoints_field}[0].port"
    ]


def test_an_endpoint_with_no_address_is_incomplete(
    settings: DatabaseSettings, complete: dict[str, JsonValue]
) -> None:
    complete[settings.endpoints_field] = [{"dns_name": "d", "port": 12000, "addr": []}]

    assert missing_database_values(values=complete, settings=settings) == [
        f"{settings.endpoints_field}[0].addr"
    ]


def test_permissions_set_earlier_must_be_on_the_database_in_any_order() -> None:
    held: dict[str, JsonValue] = {
        "roles_permissions": [{"role_uid": 2, "redis_acl_uid": 3}, {"role_uid": 4, "redis_acl_uid": 5}]
    }
    expected: dict[str, JsonValue] = {
        "roles_permissions": [{"role_uid": 4, "redis_acl_uid": 5}, {"role_uid": 2, "redis_acl_uid": 3}]
    }

    assert (
        fields_not_holding(
            values=held, expected=expected, order_insensitive_fields=frozenset({"roles_permissions"})
        )
        == []
    )


def test_a_missing_permission_is_reported() -> None:
    held: dict[str, JsonValue] = {"roles_permissions": []}
    expected: dict[str, JsonValue] = {"roles_permissions": [{"role_uid": 4, "redis_acl_uid": 5}]}

    assert fields_not_holding(values=held, expected=expected, order_insensitive_fields=frozenset()) == [
        "roles_permissions"
    ]
