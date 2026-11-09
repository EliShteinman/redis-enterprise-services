from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.config.cluster_inventory import Environment


class SitePlacement(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    network: str = Field(
        description="The network the cluster is in, as named in the service configuration.",
        examples=["net-a"],
    )
    site: str = Field(description="The site (data center) of the cluster.", examples=["dc1"])
    environment: Environment = Field(description="The environment of the cluster.", examples=["PROD"])
    cluster: str = Field(
        min_length=1,
        description="generic: the service picks a cluster at the site. "
        "Any other value: the name of a dedicated cluster in the service configuration.",
        examples=["generic"],
    )

    def describe(self) -> str:
        return f"{self.network}/{self.environment}/{self.site}/{self.cluster}"
