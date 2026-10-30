from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, model_validator

from redis_enterprise_services.config.clusters_settings import ClusterType, Environment


class ClusterChoice(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    type: ClusterType
    name: str | None = None

    @model_validator(mode="after")
    def name_only_for_dedicated(self) -> Self:
        if (self.type == "dedicated") != (self.name is not None):
            raise ValueError("a dedicated cluster has a name, and a generic one does not")
        return self


class SiteTarget(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    network: str
    site: str
    environment: Environment
    cluster: ClusterChoice

    def describe(self) -> str:
        cluster: str = self.cluster.name if self.cluster.name is not None else self.cluster.type
        return f"{self.network}/{self.environment}/{self.site}/{cluster}"
