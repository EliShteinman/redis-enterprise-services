import logging

from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.cluster_inventory import ClusterEntry
from redis_enterprise_services.config.database_defaults_settings import (
    DatabaseDefaultsSettings,
    OverrideClusterSelector,
)
from redis_enterprise_services.databases.new_database import DatabaseOptions, NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseDefaults:
    def __init__(self, *, settings: DatabaseDefaultsSettings) -> None:
        validate_values(settings=settings)
        self._settings: DatabaseDefaultsSettings = settings

    def complete(self, *, cluster: ClusterEntry, requested: NewDatabase) -> NewDatabase:
        values: dict[str, JsonValue] = dict(self._settings.values)
        for override in self._settings.overrides:
            if applies(match=override.when, cluster=cluster):
                logger.debug(msg=f"defaults for {override.when} apply to {requested.name}")
                values.update(override.values)
        values.update(requested.model_dump(exclude_none=True))
        return NewDatabase.model_validate(obj=values)


def applies(*, match: OverrideClusterSelector, cluster: ClusterEntry) -> bool:
    labels: dict[str, str] = {
        "network": cluster.network,
        "environment": cluster.environment,
        "site": cluster.site,
        "type": cluster.type,
        "cluster_name": cluster.name,
    }
    return match.model_dump(exclude_none=True).items() <= labels.items()


def validate_values(*, settings: DatabaseDefaultsSettings) -> None:
    for values in [settings.values, *(override.values for override in settings.overrides)]:
        try:
            DatabaseOptions.model_validate(obj=values)
        except ValidationError as error:
            raise ConfigurationError(
                message=f"database defaults {sorted(values)} are not valid: {error}"
            ) from error
