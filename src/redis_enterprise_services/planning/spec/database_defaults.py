import logging

from pydantic import JsonValue

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.databases.new_database import PERSISTENCE_MODE_BY_FIELD, NewDatabase

logger: logging.Logger = logging.getLogger(name=__name__)

DATA_PERSISTENCE_FIELD: str = "data_persistence"
SHARDING_FIELD: str = "sharding"
SHARD_KEY_REGEX_FIELD: str = "shard_key_regex"
SHARDS_COUNT_FIELD: str = "shards_count"


class DatabaseDefaults:
    def __init__(self, *, settings: DatabaseDefaultsSettings) -> None:
        self._settings: DatabaseDefaultsSettings = settings

    def fill_in(self, *, cluster: ConfiguredCluster, requested: NewDatabase) -> NewDatabase:
        values: dict[str, JsonValue] = merged_default_values(settings=self._settings, cluster=cluster)
        logger.debug(msg=f"database_defaults on cluster {cluster.fqdn}: {values}")
        requested_values: dict[str, JsonValue] = requested.model_dump(exclude_none=True)
        values = {
            **defaults_fitting_the_requested_sharding(defaults=values, requested=requested_values),
            **requested_values,
        }
        return NewDatabase.model_validate(
            obj=with_persistence_settings_of_its_mode(
                values=values, persistence_values=self._settings.persistence_values
            )
        )


def merged_default_values(
    *, settings: DatabaseDefaultsSettings, cluster: ConfiguredCluster
) -> dict[str, JsonValue]:
    return {**settings.database, **cluster.database_overrides}


def with_persistence_settings_of_its_mode(
    *, values: dict[str, JsonValue], persistence_values: dict[str, dict[str, JsonValue]]
) -> dict[str, JsonValue]:
    mode: JsonValue = values.get(DATA_PERSISTENCE_FIELD)
    of_this_mode: dict[str, JsonValue] = {
        field: value for field, value in values.items() if PERSISTENCE_MODE_BY_FIELD.get(field, mode) == mode
    }
    mode_defaults: dict[str, JsonValue] = persistence_values.get(mode, {}) if isinstance(mode, str) else {}
    return {**mode_defaults, **of_this_mode}


def defaults_fitting_the_requested_sharding(
    *, defaults: dict[str, JsonValue], requested: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    if requested.get(SHARDING_FIELD) is not False:
        return defaults
    return {
        field: value for field, value in defaults.items() if not is_sharding_only(field=field, value=value)
    }


def is_sharding_only(*, field: str, value: JsonValue) -> bool:
    if field == SHARD_KEY_REGEX_FIELD:
        return True
    return field == SHARDS_COUNT_FIELD and isinstance(value, int) and value > 1
