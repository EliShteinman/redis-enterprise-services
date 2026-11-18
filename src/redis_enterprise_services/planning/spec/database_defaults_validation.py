from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.databases.new_database import (
    PERSISTENCE_MODE_BY_FIELD,
    SHARD_KEY_REGEX_FIELD,
    SHARDING_FIELD,
    SHARDS_COUNT_FIELD,
    DatabaseOptions,
)
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.spec.database_defaults import (
    DATA_PERSISTENCE_FIELD,
    merged_default_values,
    override_values_on_cluster,
    with_persistence_settings_of_its_mode,
)
from redis_enterprise_services.planning.spec.database_level_values import typed_level_values
from redis_enterprise_services.planning.spec.sharding_resolution import (
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
    try:
        merged: dict[str, JsonValue] = merged_default_values(settings=settings, cluster=cluster)
        reject_persistence_settings_of_another_mode(
            base=typed_level_values(values=settings.database),
            override=override_values_on_cluster(cluster=cluster),
        )
        completed: dict[str, JsonValue] = with_sharding_completed(
            values=merged, sharding_values=settings.sharding_values
        )
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
    reject_sharding_values_that_do_not_complete_sharding(sharding_values=settings.sharding_values)
    sharded_defaults: dict[str, JsonValue] = {**settings.sharding_values, SHARDING_FIELD: True}
    for values in [settings.database, *persistence_defaults, sharded_defaults]:
        reject_invalid_options(values=values)


def reject_sharding_values_that_do_not_complete_sharding(*, sharding_values: dict[str, JsonValue]) -> None:
    if SHARDING_FIELD in sharding_values:
        raise ConfigurationError(
            message="database_defaults.sharding_values does not set sharding, it completes a sharded database"
        )
    missing: list[str] = sorted(
        field for field in (SHARD_KEY_REGEX_FIELD, SHARDS_COUNT_FIELD) if sharding_values.get(field) is None
    )
    if missing:
        raise ConfigurationError(message=f"database_defaults.sharding_values needs {missing}")


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
