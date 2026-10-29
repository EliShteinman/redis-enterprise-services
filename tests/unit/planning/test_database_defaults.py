import pytest
from pydantic import JsonValue

from redis_enterprise_services.config.clusters_settings import ClusterEntry, Environment
from redis_enterprise_services.config.database_defaults_settings import (
    DatabaseDefaultsSettings,
    DefaultsOverride,
)
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults

DEFAULTS: DatabaseDefaults = DatabaseDefaults(
    settings=DatabaseDefaultsSettings(
        values={"replication": True, "data_persistence": "aof"},
        overrides=[DefaultsOverride(when={"environment": "DEV"}, values={"replication": False})],
    )
)
REQUESTED: NewDatabase = NewDatabase(name="orders", memory_size=104857600)


def cluster(*, environment: Environment) -> ClusterEntry:
    return ClusterEntry(
        name="c1",
        network="net-a",
        environment=environment,
        site="dc1",
        type="generic",
        api_url="https://c1:9443",
    )


def test_the_general_defaults_fill_what_the_request_left_out() -> None:
    database: NewDatabase = DEFAULTS.complete(cluster=cluster(environment="PROD"), requested=REQUESTED)

    assert (database.replication, database.data_persistence) == (True, "aof")


def test_an_override_applies_where_its_labels_match() -> None:
    assert DEFAULTS.complete(cluster=cluster(environment="DEV"), requested=REQUESTED).replication is False


def test_the_request_beats_every_default() -> None:
    requested: NewDatabase = NewDatabase(name="orders", memory_size=104857600, replication=True)

    assert DEFAULTS.complete(cluster=cluster(environment="DEV"), requested=requested).replication is True


@pytest.mark.parametrize(
    argnames=("values", "when"),
    argvalues=[
        pytest.param({"replication": "maybe"}, {"environment": "DEV"}, id="invalid value"),
        pytest.param({"name": "fixed"}, {"environment": "DEV"}, id="field outside the options"),
        pytest.param({"replication": False}, {"region": "eu"}, id="unknown label"),
    ],
)
def test_defaults_that_cannot_apply_stop_at_startup(
    values: dict[str, JsonValue], when: dict[str, str]
) -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        DatabaseDefaults(
            settings=DatabaseDefaultsSettings(
                values={}, overrides=[DefaultsOverride(when=when, values=values)]
            )
        )
