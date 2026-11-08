from redis_enterprise_services.config.cluster_inventory import ClusterEntry


class ChosenClusterScope:
    def clusters_to_check(self, *, chosen: ClusterEntry) -> list[ClusterEntry]:
        return [chosen]
