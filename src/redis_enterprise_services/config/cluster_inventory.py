from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, model_validator

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.repeated_values import reject_repeated

type Environment = Literal["DEV", "PROD", "TEST"]
type ClusterType = Literal["generic", "dedicated"]

GENERIC_CLUSTER: ClusterType = "generic"


class ConfiguredCluster(ConfigModel):
    name: str = Field(min_length=1)
    network: str = Field(min_length=1)
    environment: Environment
    site: str = Field(min_length=1)
    type: ClusterType
    api_url: str = Field(pattern=r"^https?://.*[^/]$")

    @model_validator(mode="after")
    def reject_a_dedicated_cluster_named_generic(self) -> Self:
        if self.type != GENERIC_CLUSTER and self.name == GENERIC_CLUSTER:
            raise ValueError(
                f"a dedicated cluster cannot be named {GENERIC_CLUSTER}, a request asks for it by name"
            )
        return self


def reject_repeated_clusters(clusters: list[ConfiguredCluster]) -> list[ConfiguredCluster]:
    reject_repeated(
        what="clusters",
        values=[(cluster.network, cluster.environment, cluster.site, cluster.name) for cluster in clusters],
    )
    reject_repeated(what="cluster api_urls", values=[cluster.api_url for cluster in clusters])
    return clusters


type ConfiguredClusters = Annotated[list[ConfiguredCluster], AfterValidator(reject_repeated_clusters)]
