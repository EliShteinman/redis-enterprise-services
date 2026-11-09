from redis_enterprise_services.config.cluster_inventory import GENERIC_CLUSTER, ConfiguredCluster
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
    )
    return at_site and is_requested_cluster(cluster=cluster, requested=placement.cluster)


def is_requested_cluster(*, cluster: ConfiguredCluster, requested: str) -> bool:
    if requested == GENERIC_CLUSTER:
        return cluster.type == GENERIC_CLUSTER
    return cluster.type != GENERIC_CLUSTER and cluster.name == requested
