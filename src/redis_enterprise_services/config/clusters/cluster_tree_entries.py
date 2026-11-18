from typing import Literal, Self

from pydantic import Field, model_validator

from redis_enterprise_services.config.clusters.cluster_fqdn import ClusterFqdn
from redis_enterprise_services.config.clusters.cluster_inventory import GENERIC_CLUSTER, ClusterType
from redis_enterprise_services.config.clusters.level_values import EnvironmentOrNetworkValues, LevelValues


class ClusterEntry(LevelValues):
    type: ClusterType


class SiteEntry(LevelValues):
    clusters: dict[ClusterFqdn, ClusterEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_a_dedicated_cluster_at_the_generic_fqdn(self) -> Self:
        for fqdn, cluster in self.clusters.items():
            if cluster.type != GENERIC_CLUSTER and fqdn == GENERIC_CLUSTER:
                raise ValueError(
                    f"a dedicated cluster cannot have the FQDN {GENERIC_CLUSTER}: a request names it by FQDN"
                )
        return self


class NetworkEntry(EnvironmentOrNetworkValues):
    sites: dict[str, SiteEntry] = Field(min_length=1)


class EnvironmentEntry(EnvironmentOrNetworkValues):
    networks: dict[str, NetworkEntry] = Field(min_length=1)


type TreeEnvironment = Literal["dev", "prod", "test"]
type EnvironmentEntries = dict[TreeEnvironment, EnvironmentEntry]
