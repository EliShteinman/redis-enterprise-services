from enum import StrEnum
from typing import Self

from pydantic import Field, JsonValue, model_validator

from redis_enterprise_services.config.cluster_inventory import ClusterType, Environment
from redis_enterprise_services.config.config_model import ConfigModel


class OverrideSelector(ConfigModel):
    network: str | None = Field(default=None, min_length=1)
    environment: Environment | None = None
    site: str | None = Field(default=None, min_length=1)
    type: ClusterType | None = None
    cluster_name: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def reject_empty_selector(self) -> Self:
        if not self.model_dump(exclude_none=True):
            raise ValueError("an override matches on at least one label")
        return self


class DefaultsOverride(ConfigModel):
    when: OverrideSelector
    values: dict[str, JsonValue] = Field(min_length=1)


class DatabaseKindDefaults(ConfigModel):
    values: dict[str, JsonValue]
    persistence_values: dict[str, dict[str, JsonValue]]
    overrides: list[DefaultsOverride]


class DatabaseKind(StrEnum):
    SINGLE_SITE = "single_site"
    ACTIVE_ACTIVE = "active_active"

    @classmethod
    def of(cls, *, active_active: bool) -> DatabaseKind:
        return cls.ACTIVE_ACTIVE if active_active else cls.SINGLE_SITE


class DatabaseDefaultsSettings(ConfigModel):
    single_site: DatabaseKindDefaults
    active_active: DatabaseKindDefaults

    def of_kind(self, *, kind: DatabaseKind) -> DatabaseKindDefaults:
        match kind:
            case DatabaseKind.SINGLE_SITE:
                return self.single_site
            case DatabaseKind.ACTIVE_ACTIVE:
                return self.active_active
