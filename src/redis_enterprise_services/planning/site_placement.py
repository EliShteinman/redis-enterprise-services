from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from redis_enterprise_services.config.cluster_inventory import ClusterType, Environment


class ClusterChoice(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    type: ClusterType = Field(
        description="generic: the service picks a cluster at the site. "
        "dedicated: the cluster named in `name`.",
        examples=["generic"],
    )
    name: str | None = Field(
        default=None,
        description="Only with dedicated: the cluster's name in the service configuration. "
        "Not sent with generic.",
        examples=["cluster-a"],
    )

    @model_validator(mode="after")
    def name_only_for_dedicated(self) -> Self:
        if (self.type == "dedicated") != (self.name is not None):
            raise ValueError("a dedicated cluster has a name, and a generic one does not")
        return self


class SitePlacement(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    network: str = Field(
        description="The network the cluster is in, as named in the service configuration.",
        examples=["net-a"],
    )
    site: str = Field(description="The site (data center) of the cluster.", examples=["dc1"])
    environment: Environment = Field(description="The environment of the cluster.", examples=["PROD"])
    cluster: ClusterChoice = Field(description="Which cluster at the site.")

    def describe(self) -> str:
        cluster: str = self.cluster.name if self.cluster.name is not None else self.cluster.type
        return f"{self.network}/{self.environment}/{self.site}/{cluster}"
