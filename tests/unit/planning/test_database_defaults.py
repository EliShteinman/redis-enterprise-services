import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.config.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.databases.new_database import NewDatabase, SnapshotRule
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults, database_defaults_from

PERSISTENCE_VALUES: dict[str, dict[str, JsonValue]] = {
    "aof": {"aof_policy": "appendfsync-every-sec"},
    "snapshot": {"snapshot_policy": [{"secs": 3600, "writes": 1}]},
}
DEFAULTS: DatabaseDefaults = DatabaseDefaults(
    settings=DatabaseDefaultsSettings(
        database={"replication": True, "data_persistence": "aof"}, persistence_values=PERSISTENCE_VALUES
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
        database_overrides=database or {},
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
        database_defaults_from(
            settings=DatabaseDefaultsSettings(database=values, persistence_values={}), clusters=[]
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
    return database_defaults_from(
        settings=DatabaseDefaultsSettings(
            database=database or {"data_persistence": "aof"}, persistence_values=PERSISTENCE_VALUES
        ),
        clusters=[configured],
    )


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
