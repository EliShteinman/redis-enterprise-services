from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.config.cluster_inventory import Environment


class SitePlacement(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    environment: Environment = Field(description="The environment of the cluster.", examples=["PROD"])
    network: str = Field(
        description="The network the cluster is in, as named in the service configuration.",
        examples=["net-a"],
    )
    site: str = Field(
        description="The site of the cluster, as named in the service configuration.",
        examples=["NY"],
    )
    cluster: str = Field(
        min_length=1,
        description="generic: the service picks a generic cluster at the site. "
        "Any other value: the FQDN of a dedicated cluster, as written in the service configuration.",
        examples=["generic"],
    )

    def describe(self) -> str:
        return f"{self.environment}/{self.network}/{self.site}/{self.cluster}"
