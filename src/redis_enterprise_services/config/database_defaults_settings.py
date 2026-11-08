from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from redis_enterprise_services.config.clusters_settings import ClusterType, Environment
from redis_enterprise_services.config.network_name import NetworkName


class DefaultsMatch(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    network: NetworkName | None = None
    environment: Environment | None = None
    site: str | None = None
    type: ClusterType | None = None
    cluster: str | None = None

    @model_validator(mode="after")
    def matches_on_something(self) -> Self:
        if not self.model_dump(exclude_none=True):
            raise ValueError("an override matches on at least one label")
        return self


class DefaultsOverride(BaseModel):
    when: DefaultsMatch
    values: dict[str, JsonValue] = Field(min_length=1)


class DatabaseDefaultsSettings(BaseModel):
    values: dict[str, JsonValue]
    overrides: list[DefaultsOverride]
