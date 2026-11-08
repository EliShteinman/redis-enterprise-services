from typing import Self

from pydantic import Field, JsonValue, model_validator

from redis_enterprise_services.config.clusters_settings import ClusterType, Environment
from redis_enterprise_services.config.config_model import ConfigModel


class DefaultsMatch(ConfigModel):
    network: str | None = None
    environment: Environment | None = None
    site: str | None = Field(default=None, min_length=1)
    type: ClusterType | None = None
    cluster: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def requires_at_least_one_label(self) -> Self:
        if not self.model_dump(exclude_none=True):
            raise ValueError("an override matches on at least one label")
        return self


class DefaultsOverride(ConfigModel):
    when: DefaultsMatch
    values: dict[str, JsonValue] = Field(min_length=1)


class DatabaseDefaultsSettings(ConfigModel):
    values: dict[str, JsonValue]
    overrides: list[DefaultsOverride]
