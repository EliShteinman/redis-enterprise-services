import logging

from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import (
    DatabaseDefaultsSettings,
    DatabaseKind,
    DatabaseKindDefaults,
)
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.databases.new_database import PERSISTENCE_MODE_BY_FIELD, NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.spec.crdb_spec import CrdbSpec
from redis_enterprise_services.planning.spec.sharding_resolution import (
    layered_database_values,
    reject_sharding_without_its_rules,
    with_sharding_completed,
)
from redis_enterprise_services.planning.spec.validation_issues import issues_text

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
        values = with_sharding_completed(
            values=layered_database_values(layers=[values, requested.model_dump(exclude_none=True)]),
            sharding_values=defaults.sharding_values,
        )
        try:
            reject_sharding_without_its_rules(values=values)
            return NewDatabase.model_validate(
                obj=with_persistence_settings_of_its_mode(
                    values=values, persistence_values=defaults.persistence_values
                )
            )
        except ValidationError as error:
            raise ConfigurationError(
                message=f"the request together with the database_defaults.{kind} values of cluster "
                f"{cluster.fqdn} is not valid: {issues_text(error=error)}"
            ) from error

    def crdb_settings(
        self, *, cluster: ConfiguredCluster, requested: CrdbSpec | None
    ) -> CrdbCreationSettings:
        return crdb_settings_on_cluster(
            settings=self._settings, cluster=cluster, requested_values=values_sent_in(requested=requested)
        )


def merged_default_values(
    *, defaults: DatabaseKindDefaults, kind: DatabaseKind, cluster: ConfiguredCluster
) -> dict[str, JsonValue]:
    return layered_database_values(
        layers=[defaults.database, *override_levels_on_cluster(cluster=cluster, kind=kind)]
    )


def override_levels_on_cluster(
    *, cluster: ConfiguredCluster, kind: DatabaseKind
) -> list[dict[str, JsonValue]]:
    if kind == DatabaseKind.ACTIVE_ACTIVE:
        return cluster.active_active_database_override_levels
    return cluster.database_override_levels


def override_values_on_cluster(*, cluster: ConfiguredCluster, kind: DatabaseKind) -> dict[str, JsonValue]:
    return {
        name: value
        for level in override_levels_on_cluster(cluster=cluster, kind=kind)
        for name, value in level.items()
    }


def values_sent_in(*, requested: CrdbSpec | None) -> dict[str, JsonValue]:
    return {} if requested is None else requested.model_dump(mode="json", exclude_none=True)


def crdb_settings_on_cluster(
    *, settings: DatabaseDefaultsSettings, cluster: ConfiguredCluster, requested_values: dict[str, JsonValue]
) -> CrdbCreationSettings:
    try:
        return CrdbCreationSettings.model_validate(
            obj={**settings.active_active.crdb.model_dump(), **cluster.crdb_overrides, **requested_values}
        )
    except ValidationError as error:
        raise ConfigurationError(
            message=f"the request together with the database_defaults.active_active.crdb values of cluster "
            f"{cluster.fqdn} is not valid: {issues_text(error=error)}"
        ) from error


def with_persistence_settings_of_its_mode(
    *, values: dict[str, JsonValue], persistence_values: dict[str, dict[str, JsonValue]]
) -> dict[str, JsonValue]:
    mode: JsonValue = values.get(DATA_PERSISTENCE_FIELD)
    of_this_mode: dict[str, JsonValue] = {
        field: value for field, value in values.items() if PERSISTENCE_MODE_BY_FIELD.get(field, mode) == mode
    }
    mode_defaults: dict[str, JsonValue] = persistence_values.get(mode, {}) if isinstance(mode, str) else {}
    return {**mode_defaults, **of_this_mode}
