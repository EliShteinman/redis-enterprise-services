from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from redis_enterprise_services.config.config_model import ConfigModel

type Environment = Literal["DEV", "PROD", "TEST"]
type ClusterType = Literal["generic", "dedicated"]


class ClusterEntry(ConfigModel):
    name: str = Field(min_length=1)
    network: str
    environment: Environment
    site: str = Field(min_length=1)
    type: ClusterType
    api_url: str = Field(pattern=r"^https?://.*[^/]$")


def unique_clusters(clusters: list[ClusterEntry]) -> list[ClusterEntry]:
    keys: list[tuple[str, str, str, str]] = [
        (cluster.network, cluster.environment, cluster.site, cluster.name) for cluster in clusters
    ]
    repeated: set[tuple[str, str, str, str]] = {key for key in keys if keys.count(key) > 1}
    if repeated:
        raise ValueError(f"clusters configured more than once: {sorted(repeated)}")
    return clusters


type ClusterList = Annotated[list[ClusterEntry], AfterValidator(unique_clusters)]
