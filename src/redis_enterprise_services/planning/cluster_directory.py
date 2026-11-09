from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.site_placement import SitePlacement


class ClusterDirectory:
    def __init__(self, *, clusters: list[ConfiguredCluster]) -> None:
        self._clusters: list[ConfiguredCluster] = clusters

    def candidates_for(self, *, placement: SitePlacement) -> list[ConfiguredCluster]:
        return [cluster for cluster in self._clusters if fits_placement(cluster=cluster, placement=placement)]


def fits_placement(*, cluster: ConfiguredCluster, placement: SitePlacement) -> bool:
    at_site: bool = (
        cluster.network == placement.network
        and cluster.environment == placement.environment
        and cluster.site == placement.site
        and cluster.type == placement.cluster.type
    )
    return at_site and (placement.cluster.type == "generic" or cluster.name == placement.cluster.name)
