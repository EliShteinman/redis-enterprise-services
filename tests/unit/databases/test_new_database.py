import pytest
from pydantic import JsonValue, ValidationError

from redis_enterprise_services.databases.new_database import DatabaseOptions, SnapshotRule


@pytest.mark.parametrize(
    argnames="options",
    argvalues=[
        pytest.param({"aof_policy": "appendfsync-always"}, id="aof-policy-without-mode"),
        pytest.param(
            {"data_persistence": "snapshot", "aof_policy": "appendfsync-always"}, id="aof-policy-on-snapshot"
        ),
        pytest.param(
            {"data_persistence": "aof", "snapshot_policy": [{"secs": 60, "writes": 1}]}, id="snapshot-on-aof"
        ),
    ],
)
def test_a_persistence_setting_of_another_mode_is_refused(options: dict[str, JsonValue]) -> None:
    with pytest.raises(expected_exception=ValidationError):
        DatabaseOptions.model_validate(obj=options)


def test_a_persistence_setting_with_its_mode_is_accepted() -> None:
    options: DatabaseOptions = DatabaseOptions.model_validate(
        obj={"data_persistence": "snapshot", "snapshot_policy": [{"secs": 60, "writes": 1}]}
    )

    assert options.snapshot_policy == [SnapshotRule(secs=60, writes=1)]


@pytest.mark.parametrize(
    argnames="options",
    argvalues=[
        pytest.param({"sharding": False, "shards_count": 2}, id="several shards with sharding off"),
        pytest.param(
            {"sharding": False, "shard_key_regex": [{"regex": "(?<tag>.*)"}]}, id="rules with sharding off"
        ),
    ],
)
def test_sharding_settings_with_sharding_off_are_refused(options: dict[str, JsonValue]) -> None:
    with pytest.raises(expected_exception=ValidationError):
        DatabaseOptions.model_validate(obj=options)


@pytest.mark.parametrize(
    argnames="options",
    argvalues=[
        pytest.param({"sharding": True}, id="sharding alone"),
        pytest.param({"shards_count": 2}, id="several shards alone"),
        pytest.param({"shard_key_regex": [{"regex": "(?<tag>.*)"}]}, id="rules alone"),
    ],
)
def test_a_partial_sharding_request_is_accepted_for_the_defaults_to_complete(
    options: dict[str, JsonValue],
) -> None:
    DatabaseOptions.model_validate(obj=options)


def test_sharding_with_its_rules_and_several_shards_is_accepted() -> None:
    DatabaseOptions.model_validate(
        obj={"sharding": True, "shard_key_regex": [{"regex": "(?<tag>.*)"}], "shards_count": 2}
    )
