from redis_enterprise_services.config.clusters_settings import ClusterEntry, ClusterType
from redis_enterprise_services.planning.site_target import SiteTarget


class ClusterDirectory:
    def __init__(self, *, clusters: list[ClusterEntry]) -> None:
        self._clusters: list[ClusterEntry] = clusters

    def at_site(self, *, target: SiteTarget, cluster_type: ClusterType) -> list[ClusterEntry]:
        return [
            cluster
            for cluster in self._clusters
            if cluster.type == cluster_type
            and cluster.network == target.network
            and cluster.environment == target.environment
            and cluster.site == target.site
        ]
