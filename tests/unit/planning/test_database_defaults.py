import pytest
from pydantic import JsonValue

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster, Environment
from redis_enterprise_services.config.database_defaults_settings import (
    DatabaseDefaultsSettings,
    DefaultsOverride,
    OverrideSelector,
)
from redis_enterprise_services.databases.new_database import NewDatabase, SnapshotRule
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.database_defaults import (
    DatabaseDefaults,
    database_defaults_from,
    placement_labels,
)

PERSISTENCE_VALUES: dict[str, dict[str, JsonValue]] = {
    "aof": {"aof_policy": "appendfsync-every-sec"},
    "snapshot": {"snapshot_policy": [{"secs": 3600, "writes": 1}]},
}
DEFAULTS: DatabaseDefaults = DatabaseDefaults(
    settings=DatabaseDefaultsSettings(
        values={"replication": True, "data_persistence": "aof"},
        persistence_values=PERSISTENCE_VALUES,
        overrides=[DefaultsOverride(when=OverrideSelector(environment="DEV"), values={"replication": False})],
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
    database: NewDatabase = DEFAULTS.fill_in(
        cluster=cluster(environment="PROD"), requested=REQUESTED, active_active=False
    )

    assert (database.replication, database.data_persistence) == (True, "aof")


def test_an_override_applies_where_its_labels_match() -> None:
    assert (
        DEFAULTS.fill_in(
            cluster=cluster(environment="DEV"), requested=REQUESTED, active_active=False
        ).replication
        is False
    )


def test_the_request_beats_every_default() -> None:
    requested: NewDatabase = NewDatabase(name="orders", memory_size=104857600, replication=True)

    assert (
        DEFAULTS.fill_in(
            cluster=cluster(environment="DEV"), requested=requested, active_active=False
        ).replication
        is True
    )


def test_a_later_override_beats_an_earlier_one() -> None:
    defaults: DatabaseDefaults = DatabaseDefaults(
        settings=DatabaseDefaultsSettings(
            values={},
            persistence_values={},
            overrides=[
                DefaultsOverride(
                    when=OverrideSelector(environment="DEV"), values={"shards_placement": "dense"}
                ),
                DefaultsOverride(when=OverrideSelector(site="dc1"), values={"shards_placement": "sparse"}),
            ],
        )
    )

    assert (
        defaults.fill_in(
            cluster=cluster(environment="DEV"), requested=REQUESTED, active_active=False
        ).shards_placement
        == "sparse"
    )


def test_an_override_applies_only_when_all_its_labels_match() -> None:
    defaults: DatabaseDefaults = DatabaseDefaults(
        settings=DatabaseDefaultsSettings(
            values={"replication": True},
            persistence_values={},
            overrides=[
                DefaultsOverride(
                    when=OverrideSelector(environment="DEV", site="dc2"), values={"replication": False}
                )
            ],
        )
    )

    assert (
        defaults.fill_in(
            cluster=cluster(environment="DEV"), requested=REQUESTED, active_active=False
        ).replication
        is True
    )


def test_a_field_sent_as_null_keeps_the_default() -> None:
    requested: NewDatabase = NewDatabase(name="orders", memory_size=104857600, replication=None)

    assert (
        DEFAULTS.fill_in(
            cluster=cluster(environment="DEV"), requested=requested, active_active=False
        ).replication
        is False
    )


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
                persistence_values={},
                overrides=[DefaultsOverride(when=OverrideSelector(environment="DEV"), values=values)],
            ),
            clusters=[],
        )


def test_every_override_selector_field_is_a_placement_label() -> None:
    assert set(OverrideSelector.model_fields) == set(
        placement_labels(cluster=cluster(environment="DEV"), active_active=False)
    )


@pytest.mark.parametrize(
    argnames=("active_active", "eviction_policy"), argvalues=[(False, "volatile-lru"), (True, "noeviction")]
)
def test_an_active_active_override_applies_only_to_active_active(
    active_active: bool, eviction_policy: str
) -> None:
    defaults: DatabaseDefaults = DatabaseDefaults(
        settings=DatabaseDefaultsSettings(
            values={"eviction_policy": "volatile-lru"},
            persistence_values={},
            overrides=[
                DefaultsOverride(
                    when=OverrideSelector(active_active=True), values={"eviction_policy": "noeviction"}
                )
            ],
        )
    )

    filled: NewDatabase = defaults.fill_in(
        cluster=cluster(environment="PROD"), requested=REQUESTED, active_active=active_active
    )

    assert filled.eviction_policy == eviction_policy


@pytest.mark.parametrize(
    argnames=("data_persistence", "aof_policy", "snapshot_policy"),
    argvalues=[
        pytest.param(None, "appendfsync-every-sec", None, id="default-aof"),
        pytest.param("snapshot", None, [SnapshotRule(secs=3600, writes=1)], id="snapshot"),
        pytest.param("disabled", None, None, id="disabled"),
    ],
)
def test_only_the_settings_of_the_chosen_persistence_mode_are_filled_in(
    data_persistence: str | None, aof_policy: str | None, snapshot_policy: list[SnapshotRule] | None
) -> None:
    requested: NewDatabase = NewDatabase.model_validate(
        obj={"name": "orders", "memory_size": 104857600, "data_persistence": data_persistence}
    )

    filled: NewDatabase = DEFAULTS.fill_in(
        cluster=cluster(environment="PROD"), requested=requested, active_active=False
    )

    assert (filled.aof_policy, filled.snapshot_policy) == (aof_policy, snapshot_policy)


def test_a_requested_persistence_setting_beats_the_default_of_its_mode() -> None:
    requested: NewDatabase = NewDatabase.model_validate(
        obj={
            "name": "orders",
            "memory_size": 104857600,
            "data_persistence": "snapshot",
            "snapshot_policy": [{"secs": 60, "writes": 100}],
        }
    )

    filled: NewDatabase = DEFAULTS.fill_in(
        cluster=cluster(environment="PROD"), requested=requested, active_active=False
    )

    assert filled.snapshot_policy == [SnapshotRule(secs=60, writes=100)]


def defaults_with_override(*, values: dict[str, JsonValue]) -> DatabaseDefaults:
    return database_defaults_from(
        settings=DatabaseDefaultsSettings(
            values={"data_persistence": "aof"},
            persistence_values=PERSISTENCE_VALUES,
            overrides=[DefaultsOverride(when=OverrideSelector(environment="PROD"), values=values)],
        ),
        clusters=[cluster(environment="PROD")],
    )


def test_an_override_may_set_only_the_policy_of_the_default_mode() -> None:
    defaults: DatabaseDefaults = defaults_with_override(values={"aof_policy": "appendfsync-always"})

    assert defaults.fill_in(
        cluster=cluster(environment="PROD"), requested=REQUESTED, active_active=False
    ).aof_policy == ("appendfsync-always")


def test_an_override_with_the_policy_of_another_mode_stops_at_startup() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        defaults_with_override(values={"snapshot_policy": [{"secs": 60, "writes": 1}]})


def test_an_override_that_turns_persistence_off_drops_the_base_policy_at_startup() -> None:
    database_defaults_from(
        settings=DatabaseDefaultsSettings(
            values={"data_persistence": "aof", "aof_policy": "appendfsync-every-sec"},
            persistence_values={},
            overrides=[
                DefaultsOverride(
                    when=OverrideSelector(environment="DEV"), values={"data_persistence": "disabled"}
                )
            ],
        ),
        clusters=[cluster(environment="DEV")],
    )


def test_overrides_that_are_valid_alone_but_clash_on_one_cluster_stop_at_startup() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        database_defaults_from(
            settings=DatabaseDefaultsSettings(
                values={},
                persistence_values={},
                overrides=[
                    DefaultsOverride(
                        when=OverrideSelector(environment="PROD"),
                        values={"sharding": True, "shard_key_regex": [{"regex": "(?<tag>.*)"}]},
                    ),
                    DefaultsOverride(when=OverrideSelector(site="dc1"), values={"sharding": False}),
                ],
            ),
            clusters=[cluster(environment="PROD")],
        )


def test_overrides_that_conflict_only_on_an_active_active_dev_site_stop_at_startup() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        database_defaults_from(
            settings=DatabaseDefaultsSettings(
                values={"data_persistence": "aof"},
                persistence_values={},
                overrides=[
                    DefaultsOverride(
                        when=OverrideSelector(environment="DEV"), values={"data_persistence": "snapshot"}
                    ),
                    DefaultsOverride(
                        when=OverrideSelector(active_active=True), values={"aof_policy": "appendfsync-always"}
                    ),
                ],
            ),
            clusters=[cluster(environment="DEV")],
        )


def test_a_request_that_clashes_with_the_defaults_is_a_configuration_error() -> None:
    sharded: DatabaseDefaults = DatabaseDefaults(
        settings=DatabaseDefaultsSettings(
            values={
                "sharding": True,
                "shards_count": 2,
                "shard_key_regex": [{"regex": ".*\\{(?<tag>.*)\\}.*"}],
            },
            persistence_values=PERSISTENCE_VALUES,
            overrides=[],
        )
    )

    with pytest.raises(expected_exception=ConfigurationError, match=r"only together with sharding true$"):
        sharded.fill_in(
            cluster=cluster(environment="DEV"),
            requested=NewDatabase(name="orders", memory_size=104857600, sharding=False),
            active_active=False,
        )
