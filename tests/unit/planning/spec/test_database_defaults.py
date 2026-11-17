import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.config.clusters.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import (
    ActiveActiveDefaults,
    DatabaseDefaultsSettings,
    DatabaseKindDefaults,
)
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.databases.new_database import NewDatabase, SnapshotRule
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.spec.crdb_spec import CrdbSpec
from redis_enterprise_services.planning.spec.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.spec.database_defaults_validation import (
    reject_invalid_defaults_on_any_cluster,
)

ADMIN: ClusterCredentialsSettings = ClusterCredentialsSettings(username="admin", password=SecretStr("secret"))
DEFAULT_USER_PASSWORD: SecretStr = SecretStr("default-user-secret")

PERSISTENCE_VALUES: dict[str, dict[str, JsonValue]] = {
    "aof": {"aof_policy": "appendfsync-every-sec"},
    "snapshot": {"snapshot_policy": [{"secs": 3600, "writes": 1}]},
}
SHARDING_VALUES: dict[str, JsonValue] = {"shard_key_regex": [{"regex": ".*\\{(?<tag>.*)\\}.*"}]}
CRDB: CrdbCreationSettings = CrdbCreationSettings(causal_consistency=False, encryption=False, compression=3)
REQUESTED: NewDatabase = NewDatabase(name="orders", memory_size=104857600)


def defaults_settings(
    *,
    database: dict[str, JsonValue],
    persistence_values: dict[str, dict[str, JsonValue]] | None = None,
    active_active_database: dict[str, JsonValue] | None = None,
    sharding_values: dict[str, JsonValue] | None = None,
) -> DatabaseDefaultsSettings:
    return DatabaseDefaultsSettings(
        single_site=DatabaseKindDefaults(
            database=database,
            persistence_values=PERSISTENCE_VALUES if persistence_values is None else persistence_values,
            sharding_values=SHARDING_VALUES if sharding_values is None else sharding_values,
        ),
        active_active=ActiveActiveDefaults(
            database=active_active_database or {},
            persistence_values=PERSISTENCE_VALUES,
            sharding_values=SHARDING_VALUES,
            crdb=CRDB,
        ),
    )


DEFAULTS: DatabaseDefaults = DatabaseDefaults(
    settings=defaults_settings(database={"replication": True, "data_persistence": "aof"})
)


def cluster(
    *,
    database: dict[str, JsonValue] | None = None,
    active_active_database: dict[str, JsonValue] | None = None,
    crdb: dict[str, JsonValue] | None = None,
) -> ConfiguredCluster:
    return ConfiguredCluster(
        fqdn="c1",
        network="net-a",
        environment="PROD",
        site="ny",
        type="generic",
        api_url="https://c1:9443",
        database_override_levels=[database] if database else [],
        active_active_database_override_levels=[active_active_database] if active_active_database else [],
        crdb_overrides=crdb or {},
        credentials=ADMIN,
        default_user_password=DEFAULT_USER_PASSWORD,
    )


def test_the_defaults_fill_what_the_request_left_out() -> None:
    database: NewDatabase = DEFAULTS.fill_in(cluster=cluster(), requested=REQUESTED, active_active=False)

    assert (database.replication, database.data_persistence) == (True, "aof")


def test_a_value_set_on_the_cluster_beats_the_default() -> None:
    filled: NewDatabase = DEFAULTS.fill_in(
        cluster=cluster(database={"replication": False}), requested=REQUESTED, active_active=False
    )

    assert filled.replication is False


def test_the_request_beats_every_default() -> None:
    requested: NewDatabase = NewDatabase(name="orders", memory_size=104857600, replication=True)

    assert (
        DEFAULTS.fill_in(
            cluster=cluster(database={"replication": False}), requested=requested, active_active=False
        ).replication
        is True
    )


def test_a_field_sent_as_null_keeps_the_default() -> None:
    requested: NewDatabase = NewDatabase(name="orders", memory_size=104857600, replication=None)

    assert DEFAULTS.fill_in(cluster=cluster(), requested=requested, active_active=False).replication is True


@pytest.mark.parametrize(
    argnames=("active_active", "eviction_policy"), argvalues=[(False, "volatile-lru"), (True, "noeviction")]
)
def test_the_active_active_defaults_apply_only_to_active_active(
    active_active: bool, eviction_policy: str
) -> None:
    defaults: DatabaseDefaults = DatabaseDefaults(
        settings=defaults_settings(
            database={"eviction_policy": "volatile-lru"},
            active_active_database={"eviction_policy": "noeviction"},
        )
    )

    filled: NewDatabase = defaults.fill_in(
        cluster=cluster(), requested=REQUESTED, active_active=active_active
    )

    assert filled.eviction_policy == eviction_policy


def test_a_single_site_default_never_reaches_an_active_active_database() -> None:
    defaults: DatabaseDefaults = DatabaseDefaults(settings=defaults_settings(database={"replication": False}))

    filled: NewDatabase = defaults.fill_in(cluster=cluster(), requested=REQUESTED, active_active=True)

    assert filled.replication is None


def test_the_active_active_values_of_the_cluster_apply_to_active_active() -> None:
    filled: NewDatabase = DEFAULTS.fill_in(
        cluster=cluster(active_active_database={"replication": False}),
        requested=REQUESTED,
        active_active=True,
    )

    assert filled.replication is False


@pytest.mark.parametrize(
    argnames="values",
    argvalues=[
        pytest.param({"replication": "maybe"}, id="invalid value"),
        pytest.param({"name": "fixed"}, id="field outside the options"),
    ],
)
def test_defaults_that_are_not_valid_stop_at_startup(values: dict[str, JsonValue]) -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        reject_invalid_defaults_on_any_cluster(settings=defaults_settings(database=values), clusters=[])


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

    filled: NewDatabase = DEFAULTS.fill_in(cluster=cluster(), requested=requested, active_active=False)

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

    filled: NewDatabase = DEFAULTS.fill_in(cluster=cluster(), requested=requested, active_active=False)

    assert filled.snapshot_policy == [SnapshotRule(secs=60, writes=100)]


def defaults_checked_on(
    *, configured: ConfiguredCluster, database: dict[str, JsonValue] | None = None
) -> DatabaseDefaults:
    settings: DatabaseDefaultsSettings = defaults_settings(database=database or {"data_persistence": "aof"})
    reject_invalid_defaults_on_any_cluster(settings=settings, clusters=[configured])
    return DatabaseDefaults(settings=settings)


def test_a_cluster_may_set_the_policy_of_the_default_mode() -> None:
    configured: ConfiguredCluster = cluster(database={"aof_policy": "appendfsync-always"})

    filled: NewDatabase = defaults_checked_on(configured=configured).fill_in(
        cluster=configured, requested=REQUESTED, active_active=False
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
        pytest.param(
            cluster(
                active_active_database={"data_persistence": "snapshot", "aof_policy": "appendfsync-always"}
            ),
            id="clash-only-on-active-active",
        ),
        pytest.param(cluster(crdb={"compression": 9}), id="invalid-crdb-value"),
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

    filled: NewDatabase = defaults.fill_in(cluster=configured, requested=REQUESTED, active_active=False)

    assert (filled.data_persistence, filled.aof_policy) == ("disabled", None)


def test_the_crdb_values_of_the_coordinator_beat_the_crdb_defaults() -> None:
    assert DEFAULTS.crdb_settings(cluster=cluster(crdb={"compression": 6}), requested=None).compression == 6


def test_a_requested_crdb_value_beats_the_configured_one() -> None:
    assert (
        DEFAULTS.crdb_settings(
            cluster=cluster(crdb={"compression": 6}), requested=CrdbSpec(compression=1)
        ).compression
        == 1
    )


def test_a_crdb_field_left_out_of_the_request_comes_from_config() -> None:
    assert DEFAULTS.crdb_settings(
        cluster=cluster(crdb={"compression": 6}), requested=CrdbSpec(causal_consistency=True)
    ) == CrdbCreationSettings(causal_consistency=True, encryption=False, compression=6)


SHARDED: dict[str, JsonValue] = {
    "sharding": True,
    "shards_count": 2,
    "shard_key_regex": [{"regex": "(?<tag>.*)"}],
}


def filled(*, request: dict[str, JsonValue], database: dict[str, JsonValue] | None = None) -> NewDatabase:
    defaults: DatabaseDefaults = DatabaseDefaults(
        settings=defaults_settings(database=database or {}, persistence_values={})
    )
    requested: NewDatabase = NewDatabase.model_validate(
        obj={"name": "orders", "memory_size": 104857600, **request}
    )
    return defaults.fill_in(cluster=cluster(), requested=requested, active_active=False)


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
            {"sharding": True}, (True, 1, [".*\\{(?<tag>.*)\\}.*"]), id="sharding gets the default rules"
        ),
        pytest.param(
            {"shard_key_regex": [{"regex": "(?<k>.*)"}]},
            (True, 1, ["(?<k>.*)"]),
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

    assert sharding_of(defaults.fill_in(cluster=configured, requested=REQUESTED, active_active=False)) == (
        False,
        1,
        None,
    )


def test_sharding_values_without_rules_stop_at_startup() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        reject_invalid_defaults_on_any_cluster(
            settings=defaults_settings(database={}, sharding_values={}), clusters=[]
        )


def test_a_startup_error_names_the_set_of_defaults_it_comes_from() -> None:
    with pytest.raises(expected_exception=ConfigurationError, match=r"database_defaults\.active_active"):
        reject_invalid_defaults_on_any_cluster(
            settings=defaults_settings(
                database={}, active_active_database={"eviction_policy": "not-a-policy"}
            ),
            clusters=[],
        )


UNSHARDED: dict[str, JsonValue] = {"sharding": False, "shards_count": 1}


@pytest.mark.parametrize(
    argnames=("request_values", "expected"),
    argvalues=[
        pytest.param({"shards_count": 4}, (True, 4, [".*\\{(?<tag>.*)\\}.*"]), id="several shards"),
        pytest.param({"shard_key_regex": [{"regex": "(?<k>.*)"}]}, (True, 1, ["(?<k>.*)"]), id="own rules"),
    ],
)
def test_a_request_turns_sharding_on_over_defaults_that_turn_it_off(
    request_values: dict[str, JsonValue], expected: tuple[object, ...]
) -> None:
    assert sharding_of(filled(request=request_values, database=UNSHARDED)) == expected


def test_a_cluster_level_with_several_shards_turns_sharding_on_over_defaults_that_turn_it_off() -> None:
    configured: ConfiguredCluster = cluster(database={"shards_count": 3})
    defaults: DatabaseDefaults = defaults_checked_on(configured=configured, database=UNSHARDED)

    assert sharding_of(defaults.fill_in(cluster=configured, requested=REQUESTED, active_active=False))[
        :2
    ] == (
        True,
        3,
    )


def test_a_lower_tree_level_turns_sharding_off_under_a_higher_level_that_turns_it_on() -> None:
    configured: ConfiguredCluster = cluster().model_copy(
        update={"database_override_levels": [SHARDED, {}, {}, {"sharding": False}]}
    )
    defaults: DatabaseDefaults = defaults_checked_on(configured=configured, database=UNSHARDED)

    assert sharding_of(defaults.fill_in(cluster=configured, requested=REQUESTED, active_active=False)) == (
        False,
        1,
        None,
    )


def leveled_cluster(*levels: dict[str, JsonValue]) -> ConfiguredCluster:
    return cluster().model_copy(update={"database_override_levels": list(levels)})


def filled_on(*, configured: ConfiguredCluster, request: dict[str, JsonValue]) -> NewDatabase:
    defaults: DatabaseDefaults = defaults_checked_on(configured=configured, database=UNSHARDED)
    requested: NewDatabase = NewDatabase.model_validate(
        obj={"name": "orders", "memory_size": 104857600, **request}
    )
    return defaults.fill_in(cluster=configured, requested=requested, active_active=False)


@pytest.mark.parametrize(
    argnames=("levels", "request_values", "expected"),
    argvalues=[
        pytest.param(
            ({"shards_count": 4}, {"sharding": False}),
            {"sharding": True},
            (True, 1, [".*\\{(?<tag>.*)\\}.*"]),
            id="dropped shards leave one shard",
        ),
        pytest.param(
            ({"shards_count": 4},), {"shards_count": 1}, (False, 1, None), id="one shard sends sharding off"
        ),
        pytest.param(
            ({"shard_key_regex": None},),
            {"shards_count": 3},
            (True, 3, [".*\\{(?<tag>.*)\\}.*"]),
            id="null rules are unset",
        ),
        pytest.param(
            ({"sharding": "false"},),
            {"shards_count": 3},
            (True, 3, [".*\\{(?<tag>.*)\\}.*"]),
            id="text false is false",
        ),
    ],
)
def test_every_sharding_setting_is_sent_explicitly(
    levels: tuple[dict[str, JsonValue], ...],
    request_values: dict[str, JsonValue],
    expected: tuple[object, ...],
) -> None:
    assert sharding_of(filled_on(configured=leveled_cluster(*levels), request=request_values)) == expected


def test_a_level_that_contradicts_itself_stops_startup_even_when_a_lower_level_hides_it() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        defaults_checked_on(
            configured=leveled_cluster({"sharding": False, "shards_count": 4}, {"sharding": False}),
            database=UNSHARDED,
        )


def test_sharding_values_that_turn_sharding_off_stop_startup() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        reject_invalid_defaults_on_any_cluster(
            settings=defaults_settings(database={}, sharding_values={"sharding": False}),
            clusters=[],
        )


def test_active_active_sites_resolve_their_sharding_alike_whatever_their_levels_drop() -> None:
    dropping: ConfiguredCluster = cluster().model_copy(
        update={"active_active_database_override_levels": [{"shards_count": 4}, {"sharding": False}]}
    )
    plain: ConfiguredCluster = cluster()
    defaults: DatabaseDefaults = DatabaseDefaults(
        settings=defaults_settings(database={}, active_active_database=UNSHARDED)
    )
    requested: NewDatabase = NewDatabase(name="orders", memory_size=104857600, sharding=True)

    assert sharding_of(
        defaults.fill_in(cluster=dropping, requested=requested, active_active=True)
    ) == sharding_of(defaults.fill_in(cluster=plain, requested=requested, active_active=True))
