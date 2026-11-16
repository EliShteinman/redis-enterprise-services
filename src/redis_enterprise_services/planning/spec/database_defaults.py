import logging

from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.databases.new_database import (
    PERSISTENCE_MODE_BY_FIELD,
    DatabaseOptions,
    NewDatabase,
)
from redis_enterprise_services.exceptions.configuration import ConfigurationError

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


def reject_invalid_defaults_on_any_cluster(
    *, settings: DatabaseDefaultsSettings, clusters: list[ConfiguredCluster]
) -> None:
    reject_invalid_default_values(settings=settings)
    for cluster in clusters:
        reject_invalid_values_on_cluster(settings=settings, cluster=cluster)


def reject_invalid_values_on_cluster(
    *, settings: DatabaseDefaultsSettings, cluster: ConfiguredCluster
) -> None:
    merged: dict[str, JsonValue] = merged_default_values(settings=settings, cluster=cluster)
    try:
        reject_persistence_settings_of_another_mode(
            base=settings.database, override=cluster.database_overrides
        )
        reject_invalid_options(
            values=with_persistence_settings_of_its_mode(
                values=merged, persistence_values=settings.persistence_values
            )
        )
    except ConfigurationError as error:
        raise ConfigurationError(
            message=f"the database_defaults values that apply together on cluster {cluster.fqdn}: "
            f"{error.message}"
        ) from error


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


def reject_invalid_default_values(*, settings: DatabaseDefaultsSettings) -> None:
    persistence_defaults: list[dict[str, JsonValue]] = [
        {DATA_PERSISTENCE_FIELD: mode, **values} for mode, values in settings.persistence_values.items()
    ]
    for values in [settings.database, *persistence_defaults]:
        reject_invalid_options(values=values)


def reject_persistence_settings_of_another_mode(
    *, base: dict[str, JsonValue], override: dict[str, JsonValue]
) -> None:
    mode: JsonValue = {**base, **override}.get(DATA_PERSISTENCE_FIELD)
    foreign: list[str] = sorted(
        field for field in override if PERSISTENCE_MODE_BY_FIELD.get(field, mode) != mode
    )
    if foreign:
        raise ConfigurationError(
            message=f"database values on a cluster set {foreign}, which do not apply to persistence {mode}"
        )


def reject_invalid_options(*, values: dict[str, JsonValue]) -> None:
    try:
        DatabaseOptions.model_validate(obj=values)
    except ValidationError as error:
        raise ConfigurationError(
            message=f"database defaults {sorted(values)} are not valid: {error}"
        ) from error
