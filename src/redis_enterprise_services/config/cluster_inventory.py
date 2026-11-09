from typing import Annotated, Literal, Self
from urllib.parse import SplitResult, urlsplit

from pydantic import AfterValidator, Field, model_validator

from redis_enterprise_services.config.base_url import BaseUrl
from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.repeated_values import reject_repeated

type Environment = Literal["DEV", "PROD", "TEST"]
type ClusterType = Literal["generic", "dedicated"]

GENERIC_CLUSTER: ClusterType = "generic"
DEFAULT_PORT_BY_SCHEME: dict[str, int] = {"http": 80, "https": 443}


class ConfiguredCluster(ConfigModel):
    name: str = Field(min_length=1)
    network: str = Field(min_length=1)
    environment: Environment
    site: str = Field(min_length=1)
    type: ClusterType
    api_url: BaseUrl

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
    reject_repeated(
        what="cluster api_urls", values=[comparable_url(url=cluster.api_url) for cluster in clusters]
    )
    return clusters


def comparable_url(*, url: str) -> str:
    parts: SplitResult = urlsplit(url)
    scheme: str = parts.scheme.lower()
    port: int = parts.port or DEFAULT_PORT_BY_SCHEME[scheme]
    return f"{scheme}://{(parts.hostname or '').lower()}:{port}{parts.path}"


type ConfiguredClusters = Annotated[list[ConfiguredCluster], AfterValidator(reject_repeated_clusters)]
