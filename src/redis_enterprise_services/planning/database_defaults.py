import logging

from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.config.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.databases.new_database import DatabaseOptions, NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError

logger: logging.Logger = logging.getLogger(name=__name__)

CLUSTER_LABELS: tuple[str, ...] = ("network", "environment", "site", "type", "cluster")


class DatabaseDefaults:
    def __init__(self, *, settings: DatabaseDefaultsSettings) -> None:
        validate_layers(settings=settings)
        self._settings: DatabaseDefaultsSettings = settings

    def complete(self, *, cluster: ClusterEntry, requested: NewDatabase) -> NewDatabase:
        labels: dict[str, str] = cluster_labels(cluster=cluster)
        values: dict[str, JsonValue] = dict(self._settings.values)
        for override in self._settings.overrides:
            if override.when.items() <= labels.items():
                logger.debug(msg=f"defaults for {override.when} apply to {requested.name}")
                values.update(override.values)
        values.update(requested.model_dump(exclude_unset=True))
        return NewDatabase.model_validate(obj=values)


def cluster_labels(*, cluster: ClusterEntry) -> dict[str, str]:
    values: tuple[str, ...] = (cluster.network, cluster.environment, cluster.site, cluster.type, cluster.name)
    return dict(zip(CLUSTER_LABELS, values, strict=True))


def validate_layers(*, settings: DatabaseDefaultsSettings) -> None:
    layers: list[dict[str, JsonValue]] = [
        settings.values,
        *(override.values for override in settings.overrides),
    ]
    for override in settings.overrides:
        unknown: set[str] = set(override.when) - set(CLUSTER_LABELS)
        if unknown:
            raise ConfigurationError(message=f"database defaults match on unknown labels {sorted(unknown)}")
    for values in layers:
        try:
            DatabaseOptions.model_validate(obj=values)
        except ValidationError as error:
            raise ConfigurationError(
                message=f"database defaults {sorted(values)} are not valid: {error}"
            ) from error
