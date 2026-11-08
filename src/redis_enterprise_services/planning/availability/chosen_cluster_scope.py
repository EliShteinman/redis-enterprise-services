from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster


class ChosenClusterScope:
    def clusters_to_check(self, *, chosen: ConfiguredCluster) -> list[ConfiguredCluster]:
        return [chosen]
