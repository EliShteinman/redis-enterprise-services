from redis_enterprise_services.config.cluster_inventory import ClusterEntry


class ChosenClusterScope:
    def clusters(self, *, chosen: ClusterEntry) -> list[ClusterEntry]:
        return [chosen]
