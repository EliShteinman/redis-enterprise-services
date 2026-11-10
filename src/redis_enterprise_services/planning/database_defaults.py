import logging

from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.database_defaults_settings import (
    DatabaseDefaultsSettings,
    OverrideClusterSelector,
)
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
        values.update(requested.model_dump(exclude_none=True))
        return NewDatabase.model_validate(
            obj=with_persistence_settings_of_its_mode(
                values=values, persistence_values=self._settings.persistence_values
            )
        )


def database_defaults_from(
    *, settings: DatabaseDefaultsSettings, clusters: list[ConfiguredCluster]
) -> DatabaseDefaults:
    reject_invalid_default_values(settings=settings)
    for cluster in clusters:
        reject_invalid_values_on_cluster(settings=settings, cluster=cluster)
    return DatabaseDefaults(settings=settings)


def reject_invalid_values_on_cluster(
    *, settings: DatabaseDefaultsSettings, cluster: ConfiguredCluster
) -> None:
    merged: dict[str, JsonValue] = merged_default_values(settings=settings, cluster=cluster)
    try:
        reject_persistence_settings_of_another_mode(base={}, override=merged)
        reject_invalid_options(
            values=with_persistence_settings_of_its_mode(
                values=merged, persistence_values=settings.persistence_values
            )
        )
    except ConfigurationError as error:
        raise ConfigurationError(
            message=f"the database defaults that apply together on cluster {cluster.name}: {error.message}"
        ) from error


def merged_default_values(
    *, settings: DatabaseDefaultsSettings, cluster: ConfiguredCluster
) -> dict[str, JsonValue]:
    values: dict[str, JsonValue] = dict(settings.values)
    for override in settings.overrides:
        if selector_matches(selector=override.when, cluster=cluster):
            logger.debug(msg=f"defaults for {override.when} apply to cluster {cluster.name}")
            values.update(override.values)
    return values


def selector_matches(*, selector: OverrideClusterSelector, cluster: ConfiguredCluster) -> bool:
    return selector.model_dump(exclude_none=True).items() <= cluster_labels(cluster=cluster).items()


def cluster_labels(*, cluster: ConfiguredCluster) -> dict[str, str]:
    return {
        "network": cluster.network,
        "environment": cluster.environment,
        "site": cluster.site,
        "type": cluster.type,
        "cluster_name": cluster.name,
    }


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
    for values in [settings.values, *persistence_defaults]:
        reject_invalid_options(values=values)
    for override in settings.overrides:
        reject_persistence_settings_of_another_mode(base=settings.values, override=override.values)
        reject_invalid_options(
            values=with_persistence_settings_of_its_mode(
                values={**settings.values, **override.values}, persistence_values=settings.persistence_values
            )
        )


def reject_persistence_settings_of_another_mode(
    *, base: dict[str, JsonValue], override: dict[str, JsonValue]
) -> None:
    mode: JsonValue = {**base, **override}.get(DATA_PERSISTENCE_FIELD)
    foreign: list[str] = sorted(
        field for field in override if PERSISTENCE_MODE_BY_FIELD.get(field, mode) != mode
    )
    if foreign:
        raise ConfigurationError(
            message=f"database defaults override sets {foreign}, which do not apply to persistence {mode}"
        )


def reject_invalid_options(*, values: dict[str, JsonValue]) -> None:
    try:
        DatabaseOptions.model_validate(obj=values)
    except ValidationError as error:
        raise ConfigurationError(
            message=f"database defaults {sorted(values)} are not valid: {error}"
        ) from error
