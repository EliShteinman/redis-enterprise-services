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
    reject_repeated_field(field="name", values=[cluster.name for cluster in clusters])
    reject_repeated_field(field="api_url", values=[cluster.api_url for cluster in clusters])
    return clusters


def reject_repeated_field(*, field: str, values: list[str]) -> None:
    repeated: set[str] = repeated_values(values=values)
    if repeated:
        raise ValueError(f"cluster {field} configured more than once: {sorted(repeated)}")


type ConfiguredClusters = Annotated[list[ConfiguredCluster], AfterValidator(reject_repeated_clusters)]
