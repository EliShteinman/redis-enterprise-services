from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel

from redis_enterprise_services.config.network_name import NetworkName

type Environment = Literal["DEV", "PROD", "TEST"]
type ClusterType = Literal["generic", "dedicated"]


class ClusterEntry(BaseModel):
    name: str
    network: NetworkName
    environment: Environment
    site: str
    type: ClusterType
    api_url: str


def unique_clusters(clusters: list[ClusterEntry]) -> list[ClusterEntry]:
    keys: list[tuple[str, str, str, str]] = [
        (cluster.network, cluster.environment, cluster.site, cluster.name) for cluster in clusters
    ]
    repeated: set[tuple[str, str, str, str]] = {key for key in keys if keys.count(key) > 1}
    if repeated:
        raise ValueError(f"clusters configured more than once: {sorted(repeated)}")
    return clusters


type ClusterList = Annotated[list[ClusterEntry], AfterValidator(unique_clusters)]
