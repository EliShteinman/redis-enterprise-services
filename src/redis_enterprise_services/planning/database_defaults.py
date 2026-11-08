import logging

from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.database_defaults_settings import (
    DatabaseDefaultsSettings,
    OverrideClusterSelector,
)
from redis_enterprise_services.databases.new_database import DatabaseOptions, NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseDefaults:
    def __init__(self, *, settings: DatabaseDefaultsSettings) -> None:
        self._settings: DatabaseDefaultsSettings = settings

    def fill_in(self, *, cluster: ConfiguredCluster, requested: NewDatabase) -> NewDatabase:
        values: dict[str, JsonValue] = merged_default_values(settings=self._settings, cluster=cluster)
        values.update(requested.model_dump(exclude_none=True))
        return NewDatabase.model_validate(obj=values)


def database_defaults_from(*, settings: DatabaseDefaultsSettings) -> DatabaseDefaults:
    reject_invalid_default_values(settings=settings)
    return DatabaseDefaults(settings=settings)


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


def reject_invalid_default_values(*, settings: DatabaseDefaultsSettings) -> None:
    for values in [settings.values, *(override.values for override in settings.overrides)]:
        try:
            DatabaseOptions.model_validate(obj=values)
        except ValidationError as error:
            raise ConfigurationError(
                message=f"database defaults {sorted(values)} are not valid: {error}"
            ) from error
