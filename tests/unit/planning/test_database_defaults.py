import pytest
from pydantic import JsonValue

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster, Environment
from redis_enterprise_services.config.database_defaults_settings import (
    DatabaseDefaultsSettings,
    DefaultsOverride,
    OverrideClusterSelector,
)
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.database_defaults import (
    DatabaseDefaults,
    cluster_labels,
    database_defaults_from,
)

DEFAULTS: DatabaseDefaults = DatabaseDefaults(
    settings=DatabaseDefaultsSettings(
        values={"replication": True, "data_persistence": "aof"},
        overrides=[
            DefaultsOverride(when=OverrideClusterSelector(environment="DEV"), values={"replication": False})
        ],
    )
)
REQUESTED: NewDatabase = NewDatabase(name="orders", memory_size=104857600)


def cluster(*, environment: Environment) -> ConfiguredCluster:
    return ConfiguredCluster(
        name="c1",
        network="net-a",
        environment=environment,
        site="dc1",
        type="generic",
        api_url="https://c1:9443",
    )


def test_the_general_defaults_fill_what_the_request_left_out() -> None:
    database: NewDatabase = DEFAULTS.fill_in(cluster=cluster(environment="PROD"), requested=REQUESTED)

    assert (database.replication, database.data_persistence) == (True, "aof")


def test_an_override_applies_where_its_labels_match() -> None:
    assert DEFAULTS.fill_in(cluster=cluster(environment="DEV"), requested=REQUESTED).replication is False


def test_the_request_beats_every_default() -> None:
    requested: NewDatabase = NewDatabase(name="orders", memory_size=104857600, replication=True)

    assert DEFAULTS.fill_in(cluster=cluster(environment="DEV"), requested=requested).replication is True


def test_a_later_override_beats_an_earlier_one() -> None:
    defaults: DatabaseDefaults = DatabaseDefaults(
        settings=DatabaseDefaultsSettings(
            values={},
            overrides=[
                DefaultsOverride(
                    when=OverrideClusterSelector(environment="DEV"), values={"shards_placement": "dense"}
                ),
                DefaultsOverride(
                    when=OverrideClusterSelector(site="dc1"), values={"shards_placement": "sparse"}
                ),
            ],
        )
    )

    assert (
        defaults.fill_in(cluster=cluster(environment="DEV"), requested=REQUESTED).shards_placement == "sparse"
    )


def test_an_override_applies_only_when_all_its_labels_match() -> None:
    defaults: DatabaseDefaults = DatabaseDefaults(
        settings=DatabaseDefaultsSettings(
            values={"replication": True},
            overrides=[
                DefaultsOverride(
                    when=OverrideClusterSelector(environment="DEV", site="dc2"), values={"replication": False}
                )
            ],
        )
    )

    assert defaults.fill_in(cluster=cluster(environment="DEV"), requested=REQUESTED).replication is True


def test_a_field_sent_as_null_keeps_the_default() -> None:
    requested: NewDatabase = NewDatabase(name="orders", memory_size=104857600, replication=None)

    assert DEFAULTS.fill_in(cluster=cluster(environment="DEV"), requested=requested).replication is False


@pytest.mark.parametrize(
    argnames="values",
    argvalues=[
        pytest.param({"replication": "maybe"}, id="invalid value"),
        pytest.param({"name": "fixed"}, id="field outside the options"),
    ],
)
def test_defaults_that_are_not_valid_stop_at_startup(values: dict[str, JsonValue]) -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        database_defaults_from(
            settings=DatabaseDefaultsSettings(
                values={},
                overrides=[DefaultsOverride(when=OverrideClusterSelector(environment="DEV"), values=values)],
            )
        )


def test_every_override_selector_field_is_a_cluster_label() -> None:
    assert set(OverrideClusterSelector.model_fields) == set(
        cluster_labels(cluster=cluster(environment="DEV"))
    )
