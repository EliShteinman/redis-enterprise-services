import logging

from pydantic import JsonValue

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.databases.new_database import PERSISTENCE_MODE_BY_FIELD, NewDatabase

logger: logging.Logger = logging.getLogger(name=__name__)

DATA_PERSISTENCE_FIELD: str = "data_persistence"


class DatabaseDefaults:
    def __init__(self, *, settings: DatabaseDefaultsSettings) -> None:
        self._settings: DatabaseDefaultsSettings = settings

    def fill_in(self, *, cluster: ConfiguredCluster, requested: NewDatabase) -> NewDatabase:
        values: dict[str, JsonValue] = merged_default_values(settings=self._settings, cluster=cluster)
        logger.debug(msg=f"database_defaults on cluster {cluster.fqdn}: {values}")
        values.update(requested.model_dump(exclude_none=True))
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
