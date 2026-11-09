import pytest
from pydantic import JsonValue

from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.steps.read_database import missing_database_values, read_field_names


@pytest.fixture
def settings() -> DatabaseSettings:
    return load_settings().database


@pytest.fixture
def complete(settings: DatabaseSettings) -> dict[str, JsonValue]:
    values: dict[str, JsonValue] = {name: "set" for name in read_field_names(settings=settings)}
    values[settings.endpoints_field] = [{name: "set" for name in settings.endpoint_fields}]
    return values


def test_the_read_asks_for_every_creation_field_and_the_configured_extras(settings: DatabaseSettings) -> None:
    assert read_field_names(settings=settings) == [*NewDatabase.model_fields, *settings.read_fields]


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
