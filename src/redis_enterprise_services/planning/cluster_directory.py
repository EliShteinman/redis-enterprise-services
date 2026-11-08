from redis_enterprise_services.config.cluster_inventory import ClusterEntry, ClusterType
from redis_enterprise_services.planning.site_placement import SitePlacement


class ClusterDirectory:
    def __init__(self, *, clusters: list[ClusterEntry]) -> None:
        self._clusters: list[ClusterEntry] = clusters

    def of_type_at_site(self, *, placement: SitePlacement, cluster_type: ClusterType) -> list[ClusterEntry]:
        return [
            cluster
            for cluster in self._clusters
            if cluster.type == cluster_type
            and cluster.network == placement.network
            and cluster.environment == placement.environment
            and cluster.site == placement.site
        ]
