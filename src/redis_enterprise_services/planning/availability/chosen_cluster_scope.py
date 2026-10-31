from redis_enterprise_services.config.clusters_settings import ClusterEntry


class ChosenClusterScope:
    def clusters(self, *, chosen: ClusterEntry) -> list[ClusterEntry]:
        return [chosen]
