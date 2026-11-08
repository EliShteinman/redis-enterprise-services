from typing import Protocol

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster


class NameCheckScope(Protocol):
    def clusters_to_check(self, *, chosen: ConfiguredCluster) -> list[ConfiguredCluster]: ...
