from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.databases.new_database import (
    PERSISTENCE_MODE_BY_FIELD,
    SHARDING_FIELD,
    DatabaseOptions,
)
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.spec.database_defaults import (
    DATA_PERSISTENCE_FIELD,
    merged_default_values,
    override_values_on_cluster,
    with_persistence_settings_of_its_mode,
)
from redis_enterprise_services.planning.spec.sharding_resolution import (
    reject_sharding_without_its_rules,
    with_sharding_completed,
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
            base=settings.database, override=override_values_on_cluster(cluster=cluster)
        )
        completed: dict[str, JsonValue] = with_sharding_completed(
            values=merged, sharding_values=settings.sharding_values
        )
        reject_sharding_without_its_rules(values=completed)
        reject_invalid_options(
            values=with_persistence_settings_of_its_mode(
                values=completed, persistence_values=settings.persistence_values
            )
        )
    except ConfigurationError as error:
        raise ConfigurationError(
            message=f"the database_defaults values that apply together on cluster {cluster.fqdn}: "
            f"{error.message}"
        ) from error


def reject_invalid_default_values(*, settings: DatabaseDefaultsSettings) -> None:
    persistence_defaults: list[dict[str, JsonValue]] = [
        {DATA_PERSISTENCE_FIELD: mode, **values} for mode, values in settings.persistence_values.items()
    ]
    sharded_defaults: dict[str, JsonValue] = {SHARDING_FIELD: True, **settings.sharding_values}
    reject_sharding_without_its_rules(values=sharded_defaults)
    for values in [settings.database, *persistence_defaults, sharded_defaults]:
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
