from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import (
    DatabaseDefaultsSettings,
    DatabaseKind,
    DatabaseKindDefaults,
)
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
from redis_enterprise_services.planning.spec.validation_issues import issues_text


def reject_invalid_defaults_on_any_cluster(
    *, settings: DatabaseDefaultsSettings, clusters: list[ConfiguredCluster]
) -> None:
    for kind in DatabaseKind:
        defaults: DatabaseKindDefaults = settings.of_kind(kind=kind)
        reject_invalid_default_values_of_kind(defaults=defaults, kind=kind)
        for cluster in clusters:
            reject_invalid_values_on_cluster(defaults=defaults, kind=kind, cluster=cluster)


def reject_invalid_default_values_of_kind(*, defaults: DatabaseKindDefaults, kind: DatabaseKind) -> None:
    try:
        reject_invalid_default_values(defaults=defaults)
    except ConfigurationError as error:
        raise ConfigurationError(message=f"database_defaults.{kind}: {error.message}") from error


def reject_invalid_values_on_cluster(
    *, defaults: DatabaseKindDefaults, kind: DatabaseKind, cluster: ConfiguredCluster
) -> None:
    try:
        merged: dict[str, JsonValue] = merged_default_values(defaults=defaults, kind=kind, cluster=cluster)
        reject_persistence_settings_of_another_mode(
            base=typed_level_values(values=defaults.database),
            override=override_values_on_cluster(cluster=cluster, kind=kind),
        )
        completed: dict[str, JsonValue] = with_sharding_completed(
            values=merged, sharding_values=defaults.sharding_values
        )
        reject_invalid_options(
            values=with_persistence_settings_of_its_mode(
                values=completed, persistence_values=defaults.persistence_values
            )
        )
    except ConfigurationError as error:
        raise ConfigurationError(
            message=f"the database_defaults.{kind} values that apply together on cluster {cluster.fqdn}: "
            f"{error.message}"
        ) from error


def reject_invalid_default_values(*, defaults: DatabaseKindDefaults) -> None:
    persistence_defaults: list[dict[str, JsonValue]] = [
        {DATA_PERSISTENCE_FIELD: mode, **values} for mode, values in defaults.persistence_values.items()
    ]
    reject_sharding_values_that_do_not_complete_sharding(sharding_values=defaults.sharding_values)
    sharded_defaults: dict[str, JsonValue] = {**defaults.sharding_values, SHARDING_FIELD: True}
    for values in [defaults.database, *persistence_defaults, sharded_defaults]:
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
            message=f"database defaults {sorted(values)} are not valid: {issues_text(error=error)}"
        ) from error
