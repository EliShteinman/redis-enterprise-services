import logging

from pydantic import JsonValue, ValidationError
from pydantic_core import ErrorDetails

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import (
    DatabaseDefaultsSettings,
    DatabaseKind,
    DatabaseKindDefaults,
)
from redis_enterprise_services.databases.new_database import PERSISTENCE_MODE_BY_FIELD, NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError

logger: logging.Logger = logging.getLogger(name=__name__)

DATA_PERSISTENCE_FIELD: str = "data_persistence"


class DatabaseDefaults:
    def __init__(self, *, settings: DatabaseDefaultsSettings) -> None:
        self._settings: DatabaseDefaultsSettings = settings

    def fill_in(
        self, *, cluster: ConfiguredCluster, requested: NewDatabase, active_active: bool
    ) -> NewDatabase:
        kind: DatabaseKind = DatabaseKind.of(active_active=active_active)
        defaults: DatabaseKindDefaults = self._settings.of_kind(kind=kind)
        values: dict[str, JsonValue] = merged_default_values(defaults=defaults, kind=kind, cluster=cluster)
        logger.debug(msg=f"database_defaults.{kind} on cluster {cluster.fqdn}: {values}")
        values.update(requested.model_dump(exclude_none=True))
        try:
            return NewDatabase.model_validate(
                obj=with_persistence_settings_of_its_mode(
                    values=values, persistence_values=defaults.persistence_values
                )
            )
        except ValidationError as error:
            raise ConfigurationError(
                message=f"the request together with the database_defaults.{kind} values of cluster "
                f"{cluster.fqdn} is not valid: "
                f"{'; '.join(issue_text(issue=issue) for issue in error.errors(include_input=False))}"
            ) from error


def issue_text(*, issue: ErrorDetails) -> str:
    cause: object = issue.get("ctx", {}).get("error", issue["msg"])
    location: str = ".".join(str(part) for part in issue["loc"])
    return f"{location}: {cause}" if location else f"{cause}"


def merged_default_values(
    *, defaults: DatabaseKindDefaults, kind: DatabaseKind, cluster: ConfiguredCluster
) -> dict[str, JsonValue]:
    return {**defaults.database, **override_values_on_cluster(cluster=cluster, kind=kind)}


def override_values_on_cluster(*, cluster: ConfiguredCluster, kind: DatabaseKind) -> dict[str, JsonValue]:
    if kind == DatabaseKind.ACTIVE_ACTIVE:
        return cluster.active_active_database_overrides
    return cluster.database_overrides


def with_persistence_settings_of_its_mode(
    *, values: dict[str, JsonValue], persistence_values: dict[str, dict[str, JsonValue]]
) -> dict[str, JsonValue]:
    mode: JsonValue = values.get(DATA_PERSISTENCE_FIELD)
    of_this_mode: dict[str, JsonValue] = {
        field: value for field, value in values.items() if PERSISTENCE_MODE_BY_FIELD.get(field, mode) == mode
    }
    mode_defaults: dict[str, JsonValue] = persistence_values.get(mode, {}) if isinstance(mode, str) else {}
    return {**mode_defaults, **of_this_mode}
