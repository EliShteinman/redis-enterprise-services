from typing import Self

from pydantic import Field, JsonValue, model_validator

from redis_enterprise_services.config.cluster_inventory import ClusterType, Environment
from redis_enterprise_services.config.config_model import ConfigModel


class OverrideClusterSelector(ConfigModel):
    network: str | None = None
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
    when: OverrideClusterSelector
    values: dict[str, JsonValue] = Field(min_length=1)


class DatabaseDefaultsSettings(ConfigModel):
    values: dict[str, JsonValue]
    overrides: list[DefaultsOverride]
