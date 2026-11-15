import logging

from pydantic import JsonValue, ValidationError
from pydantic_core import ErrorDetails

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.database_defaults_settings import (
    DatabaseDefaultsSettings,
    DatabaseKindDefaults,
    OverrideSelector,
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

    def fill_in(
        self, *, cluster: ConfiguredCluster, requested: NewDatabase, active_active: bool
    ) -> NewDatabase:
        defaults: DatabaseKindDefaults = defaults_of_kind(
            settings=self._settings, active_active=active_active
        )
        values: dict[str, JsonValue] = merged_default_values(defaults=defaults, cluster=cluster)
        values.update(requested.model_dump(exclude_none=True))
        try:
            return NewDatabase.model_validate(
                obj=with_persistence_settings_of_its_mode(
                    values=values, persistence_values=defaults.persistence_values
                )
            )
        except ValidationError as error:
            raise ConfigurationError(
                message=f"the request together with the database defaults of cluster {cluster.name} is not "
                f"valid: {'; '.join(issue_text(issue=issue) for issue in error.errors(include_input=False))}"
            ) from error


def defaults_of_kind(*, settings: DatabaseDefaultsSettings, active_active: bool) -> DatabaseKindDefaults:
    return settings.active_active if active_active else settings


def issue_text(*, issue: ErrorDetails) -> str:
    cause: object = issue.get("ctx", {}).get("error", issue["msg"])
    location: str = ".".join(str(part) for part in issue["loc"])
    return f"{location}: {cause}" if location else f"{cause}"


def database_defaults_from(
    *, settings: DatabaseDefaultsSettings, clusters: list[ConfiguredCluster]
) -> DatabaseDefaults:
    for active_active in (False, True):
        defaults: DatabaseKindDefaults = defaults_of_kind(settings=settings, active_active=active_active)
        reject_invalid_default_values(defaults=defaults)
        for cluster in clusters:
            reject_invalid_values_on_cluster(defaults=defaults, cluster=cluster, active_active=active_active)
    return DatabaseDefaults(settings=settings)


def reject_invalid_values_on_cluster(
    *, defaults: DatabaseKindDefaults, cluster: ConfiguredCluster, active_active: bool
) -> None:
    merged: dict[str, JsonValue] = merged_default_values(defaults=defaults, cluster=cluster)
    try:
        reject_persistence_settings_of_another_mode(
            base=defaults.values, override=override_values_on_cluster(defaults=defaults, cluster=cluster)
        )
        reject_invalid_options(
            values=with_persistence_settings_of_its_mode(
                values=merged, persistence_values=defaults.persistence_values
            )
        )
    except ConfigurationError as error:
        raise ConfigurationError(
            message=f"the database defaults that apply together on cluster {cluster.name} "
            f"(active_active={active_active}): {error.message}"
        ) from error


def merged_default_values(
    *, defaults: DatabaseKindDefaults, cluster: ConfiguredCluster
) -> dict[str, JsonValue]:
    return {**defaults.values, **override_values_on_cluster(defaults=defaults, cluster=cluster)}


def override_values_on_cluster(
    *, defaults: DatabaseKindDefaults, cluster: ConfiguredCluster
) -> dict[str, JsonValue]:
    labels: dict[str, str] = placement_labels(cluster=cluster)
    values: dict[str, JsonValue] = {}
    for override in defaults.overrides:
        if selector_matches(selector=override.when, labels=labels):
            logger.debug(msg=f"defaults for {override.when} apply on cluster {cluster.name}")
            values.update(override.values)
    return values


def selector_matches(*, selector: OverrideSelector, labels: dict[str, str]) -> bool:
    return selector.model_dump(exclude_none=True).items() <= labels.items()


def placement_labels(*, cluster: ConfiguredCluster) -> dict[str, str]:
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


def reject_invalid_default_values(*, defaults: DatabaseKindDefaults) -> None:
    persistence_defaults: list[dict[str, JsonValue]] = [
        {DATA_PERSISTENCE_FIELD: mode, **values} for mode, values in defaults.persistence_values.items()
    ]
    for values in [defaults.values, *persistence_defaults]:
        reject_invalid_options(values=values)
    for override in defaults.overrides:
        reject_persistence_settings_of_another_mode(base=defaults.values, override=override.values)
        reject_invalid_options(
            values=with_persistence_settings_of_its_mode(
                values={**defaults.values, **override.values}, persistence_values=defaults.persistence_values
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
            message=f"database defaults {sorted(values)} are not valid: "
            f"{'; '.join(issue_text(issue=issue) for issue in error.errors(include_input=False))}"
        ) from error
