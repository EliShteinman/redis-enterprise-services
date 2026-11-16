from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import (
    DatabaseDefaultsSettings,
    DatabaseKind,
    DatabaseKindDefaults,
)
from redis_enterprise_services.databases.new_database import PERSISTENCE_MODE_BY_FIELD, DatabaseOptions
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.spec.database_defaults import (
    DATA_PERSISTENCE_FIELD,
    issue_text,
    merged_default_values,
    override_values_on_cluster,
    with_persistence_settings_of_its_mode,
)


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
    merged: dict[str, JsonValue] = merged_default_values(defaults=defaults, kind=kind, cluster=cluster)
    try:
        reject_persistence_settings_of_another_mode(
            base=defaults.database, override=override_values_on_cluster(cluster=cluster, kind=kind)
        )
        reject_invalid_options(
            values=with_persistence_settings_of_its_mode(
                values=merged, persistence_values=defaults.persistence_values
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
    for values in [defaults.database, *persistence_defaults]:
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
            message=f"database defaults {sorted(values)} are not valid: "
            f"{'; '.join(issue_text(issue=issue) for issue in error.errors(include_input=False))}"
        ) from error
