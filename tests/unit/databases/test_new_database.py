import pytest
from pydantic import JsonValue, ValidationError

from redis_enterprise_services.databases.new_database import DatabaseOptions


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

    assert options.data_persistence == "snapshot"
