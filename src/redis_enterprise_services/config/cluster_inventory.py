from collections.abc import Hashable
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.repeated_values import repeated_values

type Environment = Literal["DEV", "PROD", "TEST"]
type ClusterType = Literal["generic", "dedicated"]


class ConfiguredCluster(ConfigModel):
    name: str = Field(min_length=1)
    network: str
    environment: Environment
    site: str = Field(min_length=1)
    type: ClusterType
    api_url: str = Field(pattern=r"^https?://.*[^/]$")


def reject_repeated_clusters(clusters: list[ConfiguredCluster]) -> list[ConfiguredCluster]:
    reject_repeated(
        what="clusters",
        values=[(cluster.network, cluster.environment, cluster.site, cluster.name) for cluster in clusters],
    )
    reject_repeated(what="cluster api_urls", values=[cluster.api_url for cluster in clusters])
    return clusters


def reject_repeated[T: Hashable](*, what: str, values: list[T]) -> None:
    repeated: set[T] = repeated_values(values=values)
    if repeated:
        raise ValueError(f"{what} configured more than once: {sorted(repeated, key=str)}")


type ConfiguredClusters = Annotated[list[ConfiguredCluster], AfterValidator(reject_repeated_clusters)]
