import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.config.clusters.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.databases.new_database import NewDatabase, SnapshotRule
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.spec.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.spec.database_defaults_validation import (
    reject_invalid_defaults_on_any_cluster,
)

PERSISTENCE_VALUES: dict[str, dict[str, JsonValue]] = {
    "aof": {"aof_policy": "appendfsync-every-sec"},
    "snapshot": {"snapshot_policy": [{"secs": 3600, "writes": 1}]},
}
SHARDING_VALUES: dict[str, JsonValue] = {"shard_key_regex": [{"regex": ".*\\{(?<tag>.*)\\}.*"}]}
DEFAULTS: DatabaseDefaults = DatabaseDefaults(
    settings=DatabaseDefaultsSettings(
        database={"replication": True, "data_persistence": "aof"},
        persistence_values=PERSISTENCE_VALUES,
        sharding_values=SHARDING_VALUES,
    )
)
REQUESTED: NewDatabase = NewDatabase(name="orders", memory_size=104857600)


def cluster(*, database: dict[str, JsonValue] | None = None) -> ConfiguredCluster:
    return ConfiguredCluster(
        fqdn="c1",
        network="net-a",
        environment="PROD",
        site="ny",
        type="generic",
        api_url="https://c1:9443",
        credentials=ClusterCredentialsSettings(username="admin", password=SecretStr("secret")),
        default_user_password=SecretStr("default-user-secret"),
        database_override_levels=[database] if database else [],
    )


def test_the_defaults_fill_what_the_request_left_out() -> None:
    database: NewDatabase = DEFAULTS.fill_in(cluster=cluster(), requested=REQUESTED)

    assert (database.replication, database.data_persistence) == (True, "aof")


def test_a_value_set_on_the_cluster_beats_the_default() -> None:
    filled: NewDatabase = DEFAULTS.fill_in(
        cluster=cluster(database={"replication": False}), requested=REQUESTED
    )

    assert filled.replication is False


def test_the_request_beats_every_default() -> None:
    requested: NewDatabase = NewDatabase(name="orders", memory_size=104857600, replication=True)

    assert DEFAULTS.fill_in(cluster=cluster(database={"replication": False}), requested=requested).replication


def test_a_field_sent_as_null_keeps_the_default() -> None:
    requested: NewDatabase = NewDatabase(name="orders", memory_size=104857600, replication=None)

    assert DEFAULTS.fill_in(cluster=cluster(), requested=requested).replication is True


@pytest.mark.parametrize(
    argnames="values",
    argvalues=[
        pytest.param({"replication": "maybe"}, id="invalid value"),
        pytest.param({"name": "fixed"}, id="field outside the options"),
    ],
)
def test_defaults_that_are_not_valid_stop_at_startup(values: dict[str, JsonValue]) -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        reject_invalid_defaults_on_any_cluster(
            settings=DatabaseDefaultsSettings(
                database=values, persistence_values={}, sharding_values=SHARDING_VALUES
            ),
            clusters=[],
        )


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

    filled: NewDatabase = DEFAULTS.fill_in(cluster=cluster(), requested=requested)

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

    filled: NewDatabase = DEFAULTS.fill_in(cluster=cluster(), requested=requested)

    assert filled.snapshot_policy == [SnapshotRule(secs=60, writes=100)]


def defaults_checked_on(
    *, configured: ConfiguredCluster, database: dict[str, JsonValue] | None = None
) -> DatabaseDefaults:
    settings: DatabaseDefaultsSettings = DatabaseDefaultsSettings(
        database=database or {"data_persistence": "aof"},
        persistence_values=PERSISTENCE_VALUES,
        sharding_values=SHARDING_VALUES,
    )
    reject_invalid_defaults_on_any_cluster(settings=settings, clusters=[configured])
    return DatabaseDefaults(settings=settings)


def test_a_cluster_may_set_the_policy_of_the_default_mode() -> None:
    configured: ConfiguredCluster = cluster(database={"aof_policy": "appendfsync-always"})

    filled: NewDatabase = defaults_checked_on(configured=configured).fill_in(
        cluster=configured, requested=REQUESTED
    )

    assert filled.aof_policy == "appendfsync-always"


@pytest.mark.parametrize(
    argnames="configured",
    argvalues=[
        pytest.param(
            cluster(database={"snapshot_policy": [{"secs": 60, "writes": 1}]}), id="other-mode-policy"
        ),
        pytest.param(
            cluster(database={"sharding": False, "shard_key_regex": [{"regex": "(?<tag>.*)"}]}),
            id="clashing-values",
        ),
    ],
)
def test_values_on_a_cluster_that_cannot_apply_stop_at_startup(configured: ConfiguredCluster) -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        defaults_checked_on(configured=configured)


def test_a_cluster_that_turns_persistence_off_drops_the_default_policy() -> None:
    configured: ConfiguredCluster = cluster(database={"data_persistence": "disabled"})
    defaults: DatabaseDefaults = defaults_checked_on(
        configured=configured, database={"data_persistence": "aof", "aof_policy": "appendfsync-always"}
    )

    filled: NewDatabase = defaults.fill_in(cluster=configured, requested=REQUESTED)

    assert (filled.data_persistence, filled.aof_policy) == ("disabled", None)


SHARDED: dict[str, JsonValue] = {
    "sharding": True,
    "shards_count": 2,
    "shard_key_regex": [{"regex": "(?<tag>.*)"}],
}


def filled(*, request: dict[str, JsonValue], database: dict[str, JsonValue] | None = None) -> NewDatabase:
    defaults: DatabaseDefaults = DatabaseDefaults(
        settings=DatabaseDefaultsSettings(
            database=database or {}, persistence_values={}, sharding_values=SHARDING_VALUES
        )
    )
    requested: NewDatabase = NewDatabase.model_validate(
        obj={"name": "orders", "memory_size": 104857600, **request}
    )
    return defaults.fill_in(cluster=cluster(), requested=requested)


def sharding_of(database: NewDatabase) -> tuple[object, ...]:
    regex: list[str] | None = (
        None if database.shard_key_regex is None else [r.regex for r in database.shard_key_regex]
    )
    return database.sharding, database.shards_count, regex


@pytest.mark.parametrize(
    argnames=("request_values", "expected"),
    argvalues=[
        pytest.param(
            {"shards_count": 4}, (True, 4, [".*\\{(?<tag>.*)\\}.*"]), id="several shards turn sharding on"
        ),
        pytest.param(
            {"sharding": True}, (True, None, [".*\\{(?<tag>.*)\\}.*"]), id="sharding gets the default rules"
        ),
        pytest.param(
            {"shard_key_regex": [{"regex": "(?<k>.*)"}]},
            (True, None, ["(?<k>.*)"]),
            id="own rules turn sharding on",
        ),
        pytest.param({"sharding": False}, (False, 1, None), id="sharding off sends one shard"),
    ],
)
def test_a_request_completes_its_sharding_from_the_defaults(
    request_values: dict[str, JsonValue], expected: tuple[object, ...]
) -> None:
    assert sharding_of(filled(request=request_values)) == expected


def test_a_request_that_turns_sharding_off_drops_the_sharded_defaults() -> None:
    assert sharding_of(filled(request={"sharding": False}, database=SHARDED)) == (False, 1, None)


def test_a_request_that_leaves_sharding_out_keeps_the_sharded_defaults() -> None:
    assert sharding_of(filled(request={}, database=SHARDED)) == (True, 2, ["(?<tag>.*)"])


def test_a_cluster_that_turns_sharding_off_starts_and_drops_the_sharded_defaults() -> None:
    configured: ConfiguredCluster = cluster(database={"sharding": False})
    defaults: DatabaseDefaults = defaults_checked_on(configured=configured, database=SHARDED)

    assert sharding_of(defaults.fill_in(cluster=configured, requested=REQUESTED)) == (False, 1, None)


def test_sharding_values_without_rules_stop_at_startup() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        reject_invalid_defaults_on_any_cluster(
            settings=DatabaseDefaultsSettings(database={}, persistence_values={}, sharding_values={}),
            clusters=[],
        )
