from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.availability.name_check_scope import NameCheckScope


class ChosenClusterScope(NameCheckScope):
    def clusters_to_check(self, *, chosen: ConfiguredCluster) -> list[ConfiguredCluster]:
        return [chosen]
